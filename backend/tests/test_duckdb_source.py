import asyncio
import base64
import json
import os
import uuid
from unittest.mock import AsyncMock, Mock

import asyncpg
import pytest
from fastapi.testclient import TestClient
from sqlglot.errors import SqlglotError

from app.engine import api, duckdb_source
from app.engine.nl2sql import Glossary
from app.main import app


URI = "duckdb:///orders.duckdb"
POLICY = {
    "mode": "QUERY_ONLY",
    "table_columns": {"orders": ["id", "amount", "region"]},
    "row_rules": [{"table": "orders", "column": "region", "op": "eq", "value": "APAC"}],
}


def provision(root, database_id):
    duckdb = pytest.importorskip("duckdb")
    folder = root / str(database_id)
    folder.mkdir()
    file = folder / "orders.duckdb"
    with duckdb.connect(str(file)) as conn:
        conn.execute("""
            CREATE TABLE Categories(id INTEGER PRIMARY KEY);
            INSERT INTO Categories VALUES (1);
            CREATE TABLE Orders(
                id INTEGER PRIMARY KEY, amount DECIMAL(9,2), region VARCHAR COLLATE NOCASE,
                private_note VARCHAR, category_id INTEGER REFERENCES Categories(id)
            );
            INSERT INTO Orders VALUES
                (1,20,'APAC','private',1), (2,999,'apac','private',1), (3,200,'EMEA','private',1);
            CREATE VIEW hidden_view AS SELECT private_note FROM Orders;
        """)
    return file


def test_duckdb_paths_are_source_scoped(tmp_path, monkeypatch):
    monkeypatch.setenv("MORPHY_DUCKDB_ROOT", str(tmp_path))
    source = uuid.uuid4()
    folder = tmp_path / str(source)
    folder.mkdir()
    file = folder / "orders.duckdb"
    file.touch()
    assert duckdb_source.snapshot_path(URI, source) == file
    with pytest.raises(duckdb_source.SnapshotMissing):
        duckdb_source.snapshot_path(URI, uuid.uuid4())
    for path in ("duckdb:///../orders.duckdb", "duckdb://host/orders.duckdb", "duckdb:///%2e%2e/orders.duckdb"):
        with pytest.raises(ValueError):
            duckdb_source.snapshot_path(path, source)
    link = folder / "linked.duckdb"
    try:
        link.symlink_to(file)
    except OSError:
        pytest.skip("This system does not allow creating symbolic links.")
    with pytest.raises(duckdb_source.SnapshotMissing):
        duckdb_source.snapshot_path("duckdb:///linked.duckdb", source)


def test_duckdb_native_execution_respects_policy_and_external_access(tmp_path):
    file = provision(tmp_path, uuid.uuid4())
    before = file.read_bytes()
    schema, edges = duckdb_source.inspect(file, include_edges=True)
    assert set(schema) == {"orders", "categories"}
    assert edges == [("orders", "category_id", "categories", "id")]
    result = duckdb_source.execute(file, POLICY, "SELECT SUM(amount) FROM orders WHERE TRUE OR id=2")
    assert result["rows"] == [[20]]
    for sql in (
        "SELECT private_note FROM orders",
        "SELECT * FROM hidden_view",
        "SELECT * FROM read_csv('secret.csv')",
        "ATTACH 'another.duckdb' AS another",
        "DELETE FROM orders",
    ):
        with pytest.raises((ValueError, PermissionError, SqlglotError)):
            duckdb_source.execute(file, POLICY, sql)
    with pytest.raises(OSError):
        with duckdb_source.connection(file) as conn:
            conn.execute("SELECT * FROM read_csv('secret.csv')")
    assert file.read_bytes() == before


@pytest.mark.skipif(not os.getenv("MORPHY_INTEGRATION_DSN"), reason="Disposable PostgreSQL required")
def test_duckdb_live_api_round_trip(tmp_path, monkeypatch):
    pytest.importorskip("duckdb")
    dsn = os.environ["MORPHY_INTEGRATION_DSN"]
    owner, outsider = uuid.uuid4(), uuid.uuid4()

    async def setup():
        conn = await asyncpg.connect(dsn)
        try:
            async with conn.transaction():
                await conn.execute("INSERT INTO auth.users(id) VALUES($1),($2)", owner, outsider)
                await conn.execute(
                    "INSERT INTO public.profiles(id,username,display_name) VALUES($1,$2,'DuckDB fixture')",
                    owner, "duck_" + owner.hex[:12],
                )
                await conn.execute("SELECT set_config('request.jwt.claim.sub',$1,true)", str(owner))
                org = await conn.fetchval("SELECT public.create_workspace('DuckDB connector test')")
                source = await conn.fetchval(
                    "SELECT public.register_database($1,'Snapshot','duckdb')", org,
                )
                role = await conn.fetchval(
                    "SELECT role_id FROM public.memberships WHERE org_id=$1 AND user_id=$2", org, owner,
                )
                await conn.execute(
                    "SELECT public.save_permission($1,$2,$3,null,'QUERY_ONLY',$4,$5)",
                    org, source, role, json.dumps(POLICY["table_columns"]), json.dumps(POLICY["row_rules"]),
                )
                return org, source
        finally:
            await conn.close()

    async def cleanup(org):
        conn = await asyncpg.connect(dsn)
        try:
            await conn.execute("DELETE FROM public.organizations WHERE id=$1", org)
            await conn.execute("DELETE FROM auth.users WHERE id IN ($1,$2)", owner, outsider)
        finally:
            await conn.close()

    org, source = asyncio.run(setup())
    try:
        monkeypatch.setenv("MORPHY_DUCKDB_ROOT", str(tmp_path))
        monkeypatch.setenv("MORPHY_SUPABASE_URL", "http://127.0.0.1:55421")
        monkeypatch.setenv("MORPHY_SUPABASE_PUBLIC_KEY", "test-public")
        monkeypatch.setenv("MORPHY_CONTROL_DSN", dsn)
        monkeypatch.setenv("MORPHY_ENCRYPTION_KEY", base64.urlsafe_b64encode(os.urandom(32)).decode())
        monkeypatch.setenv("MORPHY_TARGET_HOSTS", "127.0.0.1:5432")
        current = [owner]
        monkeypatch.setitem(app.dependency_overrides, api.identity, lambda: current[0])
        expected_schema = {"orders": {"id": "INTEGER", "amount": "DECIMAL(9,2)", "region": "VARCHAR"}}
        glossary = Glossary(expected_schema, [])
        candidate = f'SELECT SUM({glossary.columns["orders"]["amount"]}) AS total FROM {glossary.tables["orders"]}'
        model = AsyncMock()
        model.post.return_value = Mock(json=lambda: {"message": {"content": json.dumps({"sql": candidate})}})
        context = AsyncMock()
        context.__aenter__.return_value = model
        monkeypatch.setattr("app.engine.nl2sql.httpx.AsyncClient", Mock(return_value=context))
        path = f"/api/engine/databases/{source}"
        with TestClient(app) as client:
            assert client.put(path + "/connection", json={"uri": URI}).status_code == 409
            provision(tmp_path, source)
            connection = client.put(path + "/connection", json={"uri": URI})
            assert connection.status_code == 200, connection.text
            assert client.get(path + "/schema").json() == {"dialect": "duckdb", "tables": expected_schema}
            generated = client.post(path + "/generate", json={"question": "Total amount"})
            assert generated.status_code == 200, generated.text
            result = client.post(path + "/query", json={"sql": generated.json()["sql"]})
            assert result.status_code == 200, result.text
            assert result.json()["rows"] == [[20]]
            current[0] = outsider
            assert client.put(path + "/connection", json={"uri": URI}).status_code == 403
            assert client.post(path + "/query", json={"sql": "SELECT id FROM orders"}).status_code == 403
    finally:
        asyncio.run(cleanup(org))
