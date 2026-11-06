"""Run with MORPHY_INTEGRATION_DSN pointing at a disposable migrated control plane.
Supabase identity is injected at its dependency boundary; PostgreSQL is real.
"""
import asyncio
import base64
import os
import uuid
from urllib.parse import urlsplit
import asyncpg
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.engine.api import identity
from app.engine.security import compile_query, encrypt_uri, decrypt_uri, check_uri
from sqlglot.errors import SqlglotError
from unittest.mock import AsyncMock, Mock
from types import SimpleNamespace
from fastapi import HTTPException
import app.engine.api as engine_api


def test_identity_uses_supabase_session_verification(monkeypatch):
    user = uuid.uuid4()
    response = Mock(status_code=200)
    response.json.return_value = {"id": str(user)}
    session = AsyncMock()
    session.get.return_value = response
    context = AsyncMock()
    context.__aenter__.return_value = session
    monkeypatch.setattr(engine_api.httpx, "AsyncClient", Mock(return_value=context))
    config = SimpleNamespace(supabase_url="https://project.supabase.co", supabase_key="public")
    assert asyncio.run(identity("Bearer token", config)) == user
    session.get.assert_awaited_with("https://project.supabase.co/auth/v1/user",
                                  headers={"apikey": "public", "Authorization": "Bearer token"})
    response.status_code = 401
    with pytest.raises(HTTPException) as error:
        asyncio.run(identity("Bearer expired", config))
    assert error.value.status_code == 401


def test_encryption_and_endpoint_binding():
    key = os.urandom(32)
    d = uuid.uuid4()
    ciphertext = encrypt_uri("postgresql://secret", key, d)
    assert b"postgresql" not in ciphertext
    assert decrypt_uri(ciphertext, key, d) == "postgresql://secret"
    with pytest.raises(Exception):
        decrypt_uri(ciphertext, key, uuid.uuid4())
    with pytest.raises(ValueError):
        check_uri("postgresql://u:p@unknown:5432/db", {"127.0.0.1:5432"})


def test_policy_compilation():
    schema = {"orders": {"id": "INT", "amount": "NUMERIC", "region": "TEXT"}}
    policy = {"mode": "QUERY_ONLY", "table_columns": {"orders": ["id", "amount"]},
              "row_rules": [{"table": "orders", "column": "region", "op": "eq", "value": "APAC"}]}
    sql = compile_query("SELECT * FROM orders WHERE 1=1 OR amount>0", schema, policy)
    assert '"public"."orders"' in sql
    assert "'APAC'" in sql
    assert "LIMIT 1000" in sql
    for query in ["DELETE FROM orders", "SELECT pg_sleep(10) FROM orders",
                  "SELECT region FROM orders", "SELECT * FROM orders FOR UPDATE",
                  "SELECT public.lower('a') FROM orders", "SELECT * INTO tmp FROM orders"]:
        with pytest.raises((ValueError, PermissionError, SqlglotError)):
            compile_query(query, schema, policy)
    with pytest.raises(PermissionError):
        compile_query("SELECT id FROM orders", schema, {**policy, "mode": "VIEW_ONLY"})


@pytest.mark.skipif(not os.getenv("MORPHY_INTEGRATION_DSN"), reason="Disposable PostgreSQL control plane required")
def test_live_postgres_round_trip(monkeypatch):
    dsn = os.environ["MORPHY_INTEGRATION_DSN"]
    owner, outsider = uuid.uuid4(), uuid.uuid4()
    target_name = "morphy_engine_" + uuid.uuid4().hex[:10]
    parsed = urlsplit(dsn)
    target_dsn = dsn.rsplit("/", 1)[0] + "/" + target_name
    async def setup():
        conn = await asyncpg.connect(dsn)
        try:
            await conn.execute('CREATE DATABASE "' + target_name + '"')
            await conn.execute("INSERT INTO auth.users(id) VALUES($1),($2)", owner, outsider)
            await conn.execute("INSERT INTO public.profiles(id,username,display_name) VALUES($1,$2,'Engine owner'),($3,$4,'Outsider')",
                               owner, "owner_"+owner.hex[:10], outsider, "other_"+outsider.hex[:10])
            await conn.execute("SELECT set_config('request.jwt.claim.sub',$1,false)", str(owner))
            org = await conn.fetchval("SELECT public.create_workspace('Engine integration')")
            database = await conn.fetchval("SELECT public.register_database($1,'Live test','postgres')", org)
            role = await conn.fetchval("SELECT role_id FROM public.memberships WHERE org_id=$1 AND user_id=$2", org, owner)
            imported = await conn.fetchval("SELECT public.register_database($1,'Imported test','sqlite')", org)
            await conn.execute("""SELECT public.save_permission($1,$2,$3,null,'QUERY_ONLY',
              '{"records":["region","customer"]}','[{"table":"records","column":"region","op":"eq","value":"APAC"}]')""", org, imported, role)
            await conn.execute("""SELECT public.save_permission($1,$2,$3,null,'QUERY_ONLY',
              '{"orders":["id","amount","region"]}','[{"table":"orders","column":"region","op":"eq","value":"APAC"}]')""", org, database, role)
        finally:
            await conn.close()
        target = await asyncpg.connect(target_dsn)
        await target.execute("CREATE TABLE public.orders(id int,amount numeric,region text); INSERT INTO public.orders VALUES(1,20,'APAC'),(2,999,'EMEA')")
        await target.close()
        return org, database, imported
    org, database, imported = asyncio.run(setup())
    monkeypatch.setenv("MORPHY_SUPABASE_URL", "http://127.0.0.1:55421")
    monkeypatch.setenv("MORPHY_SUPABASE_PUBLIC_KEY", "test-public")
    monkeypatch.setenv("MORPHY_CONTROL_DSN", dsn)
    monkeypatch.setenv("MORPHY_ENCRYPTION_KEY", base64.urlsafe_b64encode(os.urandom(32)).decode())
    monkeypatch.setenv("MORPHY_TARGET_HOSTS", f"{parsed.hostname}:{parsed.port or 5432}")
    current_user = [owner]
    app.dependency_overrides[identity] = lambda: current_user[0]
    try:
        with TestClient(app) as client:
            path = f"/api/engine/databases/{database}"
            response = client.put(path+"/connection", json={"uri": target_dsn})
            assert response.status_code == 200, response.text
            assert client.get(path+"/schema").json()["tables"] == {"orders": {"id": "int4", "amount": "numeric", "region": "text"}}
            response = client.post(path+"/query", json={"sql": "SELECT SUM(amount) AS total FROM orders WHERE 1=1 OR amount=999"})
            assert response.status_code == 200, response.text
            assert float(response.json()["rows"][0][0]) == 20
            for sql in [
                "WITH orders AS (SELECT amount FROM orders) SELECT SUM(amount) FROM orders",
                "SELECT SUM(amount) FROM (SELECT amount FROM orders WHERE region='EU' OR 1=1) x",
                "SELECT SUM(amount) FROM orders UNION SELECT SUM(amount) FROM orders",
            ]:
                scoped = client.post(path+"/query",json={"sql":sql})
                assert scoped.status_code == 200, scoped.text
                assert float(scoped.json()["rows"][0][0]) == 20
            if os.getenv("MORPHY_TEST_OLLAMA") == "1":
                generated = client.post(path+"/generate", json={"question":"What is the sum of all order amounts? Return one total."})
                assert generated.status_code == 200, generated.text
                executed = client.post(path+"/query", json={"sql":generated.json()["sql"]})
                assert executed.status_code == 200, executed.text
                assert float(executed.json()["rows"][0][0]) == 20
            assert client.post(path+"/query", json={"sql": "SELECT email FROM orders"}).status_code == 422
            csv_path = f"/api/engine/databases/{imported}"
            uploaded = client.put(csv_path+"/import",content=b"region,customer,email\nAPAC,001,a@example.test\nEU,002,b@example.test")
            assert uploaded.status_code == 200, uploaded.text
            assert client.get(csv_path+"/schema").json()["tables"] == {"records":{"customer":"TEXT","region":"TEXT"}}
            assert client.post(csv_path+"/query",json={"sql":"SELECT customer FROM records"}).json()["rows"] == [["001"]]
            assert client.post(csv_path+"/query",json={"sql":"SELECT email FROM records"}).status_code == 422
            assert client.put(csv_path+"/import",content=b"id,id\n1,2").status_code == 422
            assert client.post(csv_path+"/query",json={"sql":"SELECT customer FROM records"}).json()["rows"] == [["001"]]
            current_user[0] = outsider
            assert client.put(csv_path+"/import",content=b"id\n1").status_code == 403
            assert client.post(path+"/query", json={"sql": "SELECT * FROM orders"}).status_code == 403
            assert client.put(path+"/connection", json={"uri": target_dsn}).status_code == 403
    finally:
        app.dependency_overrides.pop(identity, None)
        async def cleanup():
            conn = await asyncpg.connect(dsn)
            await conn.execute("DELETE FROM public.organizations WHERE id=$1", org)
            await conn.execute("DELETE FROM auth.users WHERE id IN ($1,$2)", owner, outsider)
            await conn.execute('DROP DATABASE "'+target_name+'"')
            await conn.close()
        asyncio.run(cleanup())

