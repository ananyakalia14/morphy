import json
import time
import uuid
import asyncpg
import httpx
from cryptography.exceptions import InvalidTag
from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.routing import APIRoute
from pydantic import BaseModel, Field, SecretStr
from sqlglot.errors import SqlglotError
from .config import Settings
from . import mysql
from .security import check_uri, encrypt_uri, decrypt_uri, compile_query
from .postgres import connection, reflect
from .nl2sql import draft
from .cache import generation_key, read_draft, store_draft
from .imported import read_csv, execute_csv, parquet_to_csv
from .csv_queries import ColumnClarification, analytics_sql, question_examples
from starlette.concurrency import run_in_threadpool
from fastapi import Request
import sqlite3


class EngineRoute(APIRoute):
    def get_route_handler(self):
        handler = super().get_route_handler()

        async def guarded(request):
            try:
                return await handler(request)
            except mysql.ConfigurationError as error:
                raise HTTPException(422, str(error)) from error
            except (asyncpg.PostgresError, OSError, TimeoutError):
                raise HTTPException(
                    502,
                    "The database or control plane is unavailable. Check the server configuration.",
                )

        return guarded


router = APIRouter(prefix="/api/engine", tags=["Live query engine"], route_class=EngineRoute)
REMOTE_DIALECTS = {"postgres", *mysql.DIALECTS}


def remote_connection(uri, kind):
    return mysql.connection(uri, kind) if kind in mysql.DIALECTS else connection(uri)


def remote_reflection(target, kind):
    return mysql.reflect(target) if kind in mysql.DIALECTS else reflect(target)


def compiler_options(uri, kind):
    if kind in mysql.DIALECTS:
        return {"dialect": "mysql", "source_schema": mysql.database_name(uri)}
    return {"dialect": "sqlite" if kind == "csv-v1" else "postgres"}


def check_remote_uri(uri, allowed_hosts, dialect):
    if dialect in mysql.DIALECTS:
        mysql.check_uri(uri, allowed_hosts, dialect)
    else:
        check_uri(uri, allowed_hosts)


def settings():
    try:
        return Settings.load()
    except (ValueError, KeyError):
        raise HTTPException(
            503,
            "Configure the live engine server environment before connecting databases.",
        )


async def identity(authorization: str = Header(default=""), config=Depends(settings)):
    if not authorization.startswith("Bearer ") or len(authorization) > 12000:
        raise HTTPException(401, "Sign in to use the live engine.")
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            response = await client.get(
                config.supabase_url + "/auth/v1/user",
                headers={"apikey": config.supabase_key, "Authorization": authorization},
            )
        if response.status_code != 200:
            raise HTTPException(401, "Your session is invalid or expired.")
        return uuid.UUID(response.json()["id"])
    except (httpx.HTTPError, KeyError, ValueError):
        raise HTTPException(503, "Session verification is temporarily unavailable.")


async def control(config):
    return await asyncpg.connect(config.control_dsn, timeout=8, command_timeout=8)


class ConnectInput(BaseModel):
    uri: SecretStr = Field(min_length=8, max_length=2048)


class QueryInput(BaseModel):
    sql: str = Field(min_length=1, max_length=12000)


class QuestionInput(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    include_clarification: bool = False
    require_template: bool = False


async def authorized_target(database_id, user, config, *, viewing_panel=False):
    conn = await control(config)
    try:
        async with conn.transaction():
            await conn.execute(
                "SELECT set_config('request.jwt.claim.sub',$1,true)", str(user)
            )
            raw = await conn.fetchval(
                "SELECT public.effective_permission($1)", database_id
            )
            policy = json.loads(raw) if isinstance(raw, str) else raw
            permitted_modes = {"QUERY_ONLY", "SCHEMA_EDIT"}
            if viewing_panel:
                permitted_modes.add("VIEW_ONLY")
            if not policy or policy.get("mode") not in permitted_modes:
                raise HTTPException(
                    403, "Your current database policy does not allow queries."
                )
            row = await conn.fetchrow(
                """
                SELECT t.org_id,t.dialect,s.encrypted_credential,s.key_version FROM public.target_databases t
                JOIN morphy_private.connection_secrets s ON s.database_id=t.id
                WHERE t.id=$1 AND t.dialect=ANY($2::text[])
            """,
                database_id,
                [*REMOTE_DIALECTS, "sqlite"],
            )
            if not row:
                raise HTTPException(
                    409, "An administrator must configure this source first."
                )
            expected_version = "csv-v1" if row["dialect"] == "sqlite" else "aesgcm-v1"
            if row["key_version"] != expected_version:
                raise HTTPException(
                    409,
                    "This connection needs to be saved again using the current engine.",
                )
            try:
                uri = decrypt_uri(
                    row["encrypted_credential"], config.encryption_key, database_id
                )
            except InvalidTag:
                raise HTTPException(
                    503,
                    "The connection key does not match. Check the server encryption key.",
                )
            if expected_version == "aesgcm-v1":
                try:
                    check_remote_uri(uri, config.target_hosts, row["dialect"])
                except ValueError:
                    raise HTTPException(409, "This source must be configured again.") from None
            kind = row["dialect"] if row["dialect"] in mysql.DIALECTS else expected_version
            return uri, policy, row["org_id"], kind
    finally:
        await conn.close()


async def require_admin(conn, database_id, user, dialects):
    row = await conn.fetchrow(
        """
        SELECT t.org_id,t.dialect FROM public.target_databases t
        JOIN public.organizations o ON o.id=t.org_id
        JOIN public.memberships m ON m.org_id=o.id AND m.user_id=$2
        JOIN public.roles r ON r.id=m.role_id
        WHERE t.id=$1 AND t.dialect=ANY($3::text[]) AND r.builtin AND r.name='ADMIN'
        FOR UPDATE OF o
    """,
        database_id,
        user,
        list(dialects),
    )
    if not row:
        raise HTTPException(
            403, "An organization administrator must configure the connection."
        )
    return row


@router.put("/databases/{database_id}/connection")
async def connect(
    database_id: uuid.UUID,
    payload: ConnectInput,
    user=Depends(identity),
    config=Depends(settings),
):
    conn = await control(config)
    try:
        async with conn.transaction():
            # Serialize with policy and ownership changes in the control plane.
            row = await require_admin(conn, database_id, user, REMOTE_DIALECTS)
            uri = payload.uri.get_secret_value()
            dialect = row["dialect"]
            check_remote_uri(uri, config.target_hosts, dialect)
            async with remote_connection(uri, dialect) as target:
                schema = await remote_reflection(target, dialect)
            encrypted = encrypt_uri(uri, config.encryption_key, database_id)
            await conn.execute(
                """
                INSERT INTO morphy_private.connection_secrets(database_id,encrypted_credential,key_version)
                VALUES($1,$2,'aesgcm-v1') ON CONFLICT(database_id) DO UPDATE
                SET encrypted_credential=excluded.encrypted_credential,key_version=excluded.key_version
            """,
                database_id,
                encrypted,
            )
            await conn.execute(
                "INSERT INTO public.audit_events(org_id,actor_id,action,subject_id) VALUES($1,$2,'connection.saved',$3)",
                row["org_id"],
                user,
                database_id,
            )
            return {"status": "connected", "tables": len(schema), "schema": schema}
    except ValueError as error:
        raise HTTPException(422, str(error))
    except (asyncpg.PostgresError, OSError, TimeoutError):
        raise HTTPException(
            502,
            "The database connection or control plane is unavailable. Check the server settings and read-only database credentials.",
        )
    finally:
        await conn.close()


@router.get("/databases/{database_id}/schema")
async def schema(
    database_id: uuid.UUID, user=Depends(identity), config=Depends(settings)
):
    uri, policy, _, kind = await authorized_target(database_id, user, config)
    if kind == "csv-v1":
        reflected, _ = await run_in_threadpool(read_csv, uri)
    else:
        async with remote_connection(uri, kind) as target:
            reflected = await remote_reflection(target, kind)
    allowed = {
        t: {c: reflected[t][c] for c in cols if c in reflected[t]}
        for t, cols in policy["table_columns"].items()
        if t in reflected
    }
    return {
        "dialect": kind if kind in mysql.DIALECTS else compiler_options(uri, kind)["dialect"],
        "tables": {t: cols for t, cols in allowed.items() if cols},
        **(
            {"question_examples": question_examples(allowed.get("records", {}))}
            if kind == "csv-v1" else {}
        ),
    }


async def audit_query(config, org, user, database_id):
    audit = await control(config)
    try:
        await audit.execute(
            "INSERT INTO public.audit_events(org_id,actor_id,action,subject_id) VALUES($1,$2,'query.started',$3)",
            org,
            user,
            database_id,
        )
    finally:
        await audit.close()


@router.post("/databases/{database_id}/query")
async def query(
    database_id: uuid.UUID,
    payload: QueryInput,
    user=Depends(identity),
    config=Depends(settings),
):
    target = await authorized_target(database_id, user, config)
    return await execute_sql(database_id, user, config, target, payload.sql)


@router.post("/dashboards/{dashboard_id}/panels/{query_id}/render")
async def render_panel(
    dashboard_id: uuid.UUID,
    query_id: uuid.UUID,
    user=Depends(identity),
    config=Depends(settings),
):
    conn = await control(config)
    try:
        async with conn.transaction():
            await conn.execute(
                "SELECT set_config('request.jwt.claim.sub',$1,true)", str(user)
            )
            # Both the panel and its underlying saved definition must be visible
            # under the caller's RLS context. SQL comes exclusively from storage.
            await conn.execute("SET LOCAL ROLE authenticated")
            panel = await conn.fetchrow(
                """
                SELECT p.database_id,q.sql_text FROM public.dashboard_panels p
                JOIN public.saved_queries q ON q.id=p.query_id
                WHERE p.dashboard_id=$1 AND p.query_id=$2
            """,
                dashboard_id,
                query_id,
            )
    finally:
        await conn.close()
    if not panel:
        raise HTTPException(404, "Panel unavailable.")
    database_id = panel["database_id"]
    uri, policy, org, kind = await authorized_target(
        database_id, user, config, viewing_panel=True
    )
    # Authorize this stored statement only. Preserve the viewer's entire
    # column map and all row predicates when compiling the panel.
    if policy["mode"] == "VIEW_ONLY":
        policy = {**policy, "mode": "QUERY_ONLY"}
    return await execute_sql(
        database_id, user, config, (uri, policy, org, kind), panel["sql_text"]
    )


async def execute_sql(database_id, user, config, target_info, submitted_sql):
    uri, policy, org, kind = target_info
    started = time.perf_counter()
    try:
        if kind == "csv-v1":
            await audit_query(config, org, user, database_id)
            result = await run_in_threadpool(execute_csv, uri, policy, submitted_sql)
            return {
                **result,
                "elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
            }
        async with remote_connection(uri, kind) as target:
            reflected = await remote_reflection(target, kind)
            sql = compile_query(submitted_sql, reflected, policy, **compiler_options(uri, kind))
            # Fail closed if the durable query-intent audit cannot be written.
            await audit_query(config, org, user, database_id)
            if kind in mysql.DIALECTS:
                result = await mysql.execute(target, sql)
                if result is None:
                    raise HTTPException(413, "The result exceeds 2 MB. Select fewer columns or rows.")
                columns, rows = result
                return {
                    "columns": columns,
                    "rows": rows,
                    "row_count": len(rows),
                    "sql": sql,
                    "elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
                }
            # Bound response memory as well as row count.
            records = []
            size = 0
            statement = await target.prepare(sql)
            async for row in statement.cursor(prefetch=25):
                values = list(row.values())
                size += sum(len(str(v)) for v in values)
                if size > 2_000_000:
                    raise HTTPException(
                        413, "The result exceeds 2 MB. Select fewer columns or rows."
                    )
                records.append(values)
            return {
                "columns": [a.name for a in statement.get_attributes()],
                "rows": records,
                "row_count": len(records),
                "sql": sql,
                "elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
            }
    except PermissionError as error:
        raise HTTPException(403, str(error))
    except (ValueError, SqlglotError, sqlite3.Error):
        raise HTTPException(
            422, "The SQL could not be validated against your permitted schema."
        )
    except (asyncpg.PostgresError, OSError, TimeoutError):
        raise HTTPException(
            502,
            "The query could not complete. Check the database and simplify the query.",
        )


@router.post("/databases/{database_id}/generate")
async def generate(
    database_id: uuid.UUID,
    payload: QuestionInput,
    user=Depends(identity),
    config=Depends(settings),
):
    uri, policy, _, kind = await authorized_target(database_id, user, config)
    if kind == "csv-v1":
        reflected, _ = await run_in_threadpool(read_csv, uri)
        edges = []
    elif kind in mysql.DIALECTS:
        async with remote_connection(uri, kind) as target:
            reflected = await mysql.reflect(target)
            edges = await mysql.foreign_keys(target)
    else:
        async with connection(uri) as target:
            reflected = await reflect(target)
            edges = await target.fetch("""
                SELECT a.relname, ac.attname, b.relname, bc.attname
                FROM pg_constraint k JOIN pg_class a ON a.oid=k.conrelid
                JOIN pg_class b ON b.oid=k.confrelid
                CROSS JOIN LATERAL unnest(k.conkey,k.confkey) pair(src,dst)
                JOIN pg_attribute ac ON ac.attrelid=k.conrelid AND ac.attnum=pair.src
                JOIN pg_attribute bc ON bc.attrelid=k.confrelid AND bc.attnum=pair.dst
                WHERE k.contype='f' AND a.relnamespace='public'::regnamespace
                AND b.relnamespace='public'::regnamespace
            """)
    try:
        compile_options = compiler_options(uri, kind)
        dialect = compile_options["dialect"]
        if kind == "csv-v1":
            columns = set(reflected["records"]).intersection(
                policy["table_columns"].get("records", [])
            )
            try:
                sql = analytics_sql(
                    payload.question, columns, exact_columns=payload.require_template
                )
            except ColumnClarification as error:
                if payload.include_clarification:
                    return {
                        "kind": "clarification",
                        "message": str(error),
                        "choices": error.choices,
                    }
                raise HTTPException(422, str(error)) from error
            except ValueError as error:
                raise HTTPException(422, str(error)) from error
            if sql is not None:
                compile_query(sql, reflected, policy, dialect=dialect)
                return {
                    "sql": sql,
                    "provider": "morphy-template",
                    "requires_execution": True,
                    "attempts": 0,
                    "cache": "miss",
                }
        if payload.require_template:
            raise HTTPException(
                422, "That column is unavailable for this question. Ask again to refresh the choices."
            )
        key = generation_key(
            database_id, payload.question, config.ollama_model, reflected, policy, edges,
            **compile_options,
        )
        cached = await read_draft(key)
        if cached:
            compile_query(cached, reflected, policy, **compile_options)
            return {
                "sql": cached,
                "provider": config.ollama_model,
                "requires_execution": True,
                "attempts": 0,
                "cache": "hit",
            }

        async def check_plan(compiled):
            if kind in mysql.DIALECTS:
                async with remote_connection(uri, kind) as target:
                    await mysql.validate_plan(target, compiled)
            if dialect == "postgres":
                try:
                    async with connection(uri) as target:
                        await target.prepare(compiled)
                except asyncpg.PostgresError as error:
                    raise ValueError(
                        "PostgreSQL validation: " + str(error.sqlstate)
                    ) from error

        result = await draft(
            config, payload.question, reflected, policy, edges, check_plan,
            result_dialect=dialect,
            source_schema=compile_options.get("source_schema"),
            database_id=database_id,
        )
        await store_draft(key, result["sql"])
        return {**result, "cache": "miss"}
    except httpx.HTTPError:
        raise HTTPException(
            503, "Local model unavailable. Check Ollama and the configured model."
        )
    except (KeyError, ValueError, PermissionError, SqlglotError):
        raise HTTPException(
            422,
            "No valid permitted query could be generated. Narrow the question or use the SQL editor.",
        )


@router.put("/databases/{database_id}/import")
async def import_csv(
    database_id: uuid.UUID,
    request: Request,
    user=Depends(identity),
    config=Depends(settings),
):
    contents = bytearray()
    async for chunk in request.stream():
        if len(contents) + len(chunk) > 1_048_576:
            raise HTTPException(413, "Choose a CSV or Parquet file up to 1 MB.")
        contents.extend(chunk)
    conn = await control(config)
    try:
        async with conn.transaction():
            row = await require_admin(conn, database_id, user, ("sqlite",))
            parquet = request.headers.get("content-type", "").split(";")[0].strip().lower() == "application/vnd.apache.parquet"
            if parquet:
                try:
                    text = await run_in_threadpool(parquet_to_csv, bytes(contents))
                except ImportError:
                    raise HTTPException(503, "Install the server's requirements-parquet.txt to enable Parquet imports.")
            else:
                text = contents.decode("utf-8-sig")
            reflected, records = await run_in_threadpool(read_csv, text)
            blob = encrypt_uri(text, config.encryption_key, database_id)
            await conn.execute(
                """
                INSERT INTO morphy_private.connection_secrets(database_id,encrypted_credential,key_version)
                VALUES($1,$2,'csv-v1') ON CONFLICT(database_id) DO UPDATE
                SET encrypted_credential=excluded.encrypted_credential,key_version=excluded.key_version
            """,
                database_id,
                blob,
            )
            await conn.execute(
                "INSERT INTO public.audit_events(org_id,actor_id,action,subject_id) VALUES($1,$2,$3,$4)",
                row["org_id"],
                user,
                "parquet.imported" if parquet else "csv.imported",
                database_id,
            )
            return {
                "table": "records",
                "columns": list(reflected["records"]),
                "rows": len(records),
            }
    except (ValueError, UnicodeError) as error:
        raise HTTPException(422, str(error))
    finally:
        await conn.close()
