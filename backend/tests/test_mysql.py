import asyncio
import base64
import json
import os
import uuid
from unittest.mock import AsyncMock, Mock
from urllib.parse import urlsplit

import asyncpg
import pytest
from fastapi.testclient import TestClient
from sqlglot.errors import SqlglotError

from app.engine import api, mysql
from app.engine.nl2sql import Glossary
from app.engine.security import compile_query
from app.main import app


def test_mysql_uri_is_bound_to_family_and_allowlist():
    mysql.check_uri("mysql://user:pass@db.example/morphy", {"db.example:3306"}, "mysql")
    for uri in (
        "mariadb://user:pass@db.example/morphy",
        "mysql://user:pass@db.example/sys",
        "mysql://user:pass@db.example/morphy?sslmode=disable",
        "mysql://user:pass@db.example/morphy?local_infile=1",
        "mysql://user:pass@elsewhere.example/morphy",
        "mysql://user:pass@db.example/morphy%2Fother",
    ):
        with pytest.raises(ValueError):
            mysql.check_uri(uri, {"db.example:3306"}, "mysql")


def test_mysql_tls_requirement_refuses_downgrade_before_authentication(monkeypatch):
    parent_auth = AsyncMock()
    monkeypatch.setattr(mysql.aiomysql.Connection, "_request_authentication", parent_auth)
    async def check():
        connection = mysql.VerifiedConnection()
        connection.server_capabilities = 0
        with pytest.raises(OSError, match="TLS"):
            await connection._request_authentication()

    asyncio.run(check())
    parent_auth.assert_not_awaited()


@pytest.mark.parametrize("sql", [
    "SELECT id INTO OUTFILE 'test' FROM orders",
    "SELECT LOAD_FILE('/etc/passwd') FROM orders",
    "SELECT @user_variable FROM orders",
    "SELECT @@version FROM orders",
    "SELECT id FROM other.orders",
    "SELECT /*+ MAX_EXECUTION_TIME(0) */ id FROM orders",
])
def test_mysql_governed_compiler_blocks_target_escape(sql):
    with pytest.raises((ValueError, PermissionError, SqlglotError)):
        compile_query(
            sql, {"orders": {"id": "int"}},
            {"mode": "QUERY_ONLY", "table_columns": {"orders": ["id"]}},
            dialect="mysql", source_schema="morphy_fixture",
        )


@pytest.mark.skipif(
    not os.getenv("MORPHY_INTEGRATION_DSN") or not os.getenv("MORPHY_TEST_MYSQL_URI"),
    reason="Disposable PostgreSQL and MySQL-family fixtures required",
)
def test_mysql_family_api_round_trip(monkeypatch):
    dsn, uri = os.environ["MORPHY_INTEGRATION_DSN"], os.environ["MORPHY_TEST_MYSQL_URI"]
    parsed = urlsplit(uri)
    owner, outsider = uuid.uuid4(), uuid.uuid4()

    async def setup():
        conn = await asyncpg.connect(dsn)
        try:
            async with conn.transaction():
                await conn.execute("INSERT INTO auth.users(id) VALUES($1),($2)", owner, outsider)
                await conn.execute(
                    "INSERT INTO public.profiles(id,username,display_name) VALUES($1,$2,'Connector owner')",
                    owner, "owner_" + owner.hex[:12],
                )
                await conn.execute("SELECT set_config('request.jwt.claim.sub',$1,true)", str(owner))
                org = await conn.fetchval("SELECT public.create_workspace('Connector test')")
                database = await conn.fetchval(
                    "SELECT public.register_database($1,'Connector orders',$2)", org, parsed.scheme,
                )
                role = await conn.fetchval(
                    "SELECT role_id FROM public.memberships WHERE org_id=$1 AND user_id=$2", org, owner,
                )
                await conn.execute(
                    """SELECT public.save_permission($1,$2,$3,null,'QUERY_ONLY',
                    '{"orders":["id","amount","region"]}','[{"table":"orders","column":"region","op":"eq","value":"APAC"}]')""",
                    org, database, role,
                )
                return org, database
        finally:
            await conn.close()

    async def cleanup(org):
        conn = await asyncpg.connect(dsn)
        try:
            await conn.execute("DELETE FROM public.organizations WHERE id=$1", org)
            await conn.execute("DELETE FROM auth.users WHERE id IN ($1,$2)", owner, outsider)
        finally:
            await conn.close()

    org, database = asyncio.run(setup())
    monkeypatch.setenv("MORPHY_SUPABASE_URL", "http://127.0.0.1:55421")
    monkeypatch.setenv("MORPHY_SUPABASE_PUBLIC_KEY", "test-public")
    monkeypatch.setenv("MORPHY_CONTROL_DSN", dsn)
    monkeypatch.setenv("MORPHY_ENCRYPTION_KEY", base64.urlsafe_b64encode(os.urandom(32)).decode())
    monkeypatch.setenv("MORPHY_TARGET_HOSTS", f"{parsed.hostname}:{parsed.port}")
    current = [owner]
    monkeypatch.setitem(app.dependency_overrides, api.identity, lambda: current[0])
    schema_expected = {"orders": {"id": "int", "amount": "decimal", "region": "varchar"}}
    glossary = Glossary(schema_expected, [])
    candidate = f'SELECT SUM({glossary.columns["orders"]["amount"]}) AS total FROM {glossary.tables["orders"]}'
    model = AsyncMock()
    model.post.return_value = Mock(json=lambda: {"message": {"content": json.dumps({"sql": candidate})}})
    context = AsyncMock()
    context.__aenter__.return_value = model
    monkeypatch.setattr("app.engine.nl2sql.httpx.AsyncClient", Mock(return_value=context))
    path = f"/api/engine/databases/{database}"
    try:
        with TestClient(app) as client:
            connected = client.put(path + "/connection", json={"uri": uri})
            assert connected.status_code == 200, connected.text
            assert set(connected.json()["schema"]) == {"orders"}
            schema = client.get(path + "/schema")
            assert schema.json() == {
                "dialect": parsed.scheme, "tables": schema_expected,
            }
            draft = client.post(path + "/generate", json={"question": "Total amount"})
            assert draft.status_code == 200, draft.text
            result = client.post(path + "/query", json={"sql": draft.json()["sql"]})
            assert result.status_code == 200, result.text
            assert result.json()["rows"] == [[20.0]]
            assert client.post(path + "/query", json={"sql": "SELECT private_note FROM orders"}).status_code == 422
            current[0] = outsider
            assert client.get(path + "/schema").status_code == 403
            assert client.put(path + "/connection", json={"uri": uri}).status_code == 403
            assert client.post(path + "/query", json={"sql": "SELECT id FROM orders"}).status_code == 403
    finally:
        asyncio.run(cleanup(org))
