"""Read-only connections to one allowlisted MySQL or MariaDB database."""

import asyncio
import re
import ssl
from contextlib import asynccontextmanager
from urllib.parse import parse_qs, unquote, urlsplit

import aiomysql
from pymysql.constants import CLIENT


DIALECTS = {"mysql", "mariadb"}
SCALAR_TYPES = {
    "tinyint", "smallint", "mediumint", "int", "bigint", "float", "double",
    "decimal", "char", "varchar", "tinytext", "text", "mediumtext", "longtext",
    "date", "datetime", "timestamp", "time", "year",
}
SYSTEM_DATABASES = {"information_schema", "performance_schema", "mysql", "sys"}


class ConfigurationError(ValueError):
    pass


class VerifiedConnection(aiomysql.Connection):
    async def _request_authentication(self):
        # aiomysql can otherwise continue authenticating without TLS when
        # the server omits CLIENT.SSL from its initial handshake.
        if not self.server_capabilities & CLIENT.SSL:
            raise OSError("The target does not support TLS.")
        await super()._request_authentication()


class QuietCursor(aiomysql.Cursor):
    async def _show_warnings(self, conn):
        # Server diagnostics, especially EXPLAIN notes, may contain row values.
        return


class QuietStreamingCursor(aiomysql.SSCursor, QuietCursor):
    pass


def database_name(uri):
    return unquote(urlsplit(uri).path[1:])


def check_uri(uri, allowed_hosts, dialect):
    try:
        parts = urlsplit(uri)
        port = parts.port or 3306
        database = database_name(uri)
    except ValueError:
        raise ValueError("Provide a valid MySQL or MariaDB connection URI.") from None
    if (
        parts.scheme != dialect or not parts.hostname or not parts.username
        or not parts.password or parts.fragment or not re.fullmatch(r"[\w$-]{1,64}", database, re.ASCII)
        or database.lower() in SYSTEM_DATABASES
    ):
        raise ValueError(f"Provide a {dialect} URI with a user, password and application database.")
    if f"{parts.hostname}:{port}" not in allowed_hosts:
        raise ValueError("This database host and port are outside the server connection allowlist.")
    params = parse_qs(parts.query, keep_blank_values=True)
    sslmode = params.get("sslmode", ["verify-full"])
    loopback = parts.hostname in {"127.0.0.1", "::1"}
    if set(params) - {"sslmode"} or (
        sslmode != ["verify-full"] and not (sslmode == ["disable"] and loopback)
    ):
        raise ValueError("Use sslmode=verify-full. Disabling TLS is limited to loopback.")


@asynccontextmanager
async def connection(uri, dialect):
    parts = urlsplit(uri)
    tls = parse_qs(parts.query).get("sslmode") != ["disable"]
    driver = VerifiedConnection if tls else aiomysql.Connection
    conn = driver(
        host=parts.hostname,
        port=parts.port or 3306,
        user=unquote(parts.username),
        password=unquote(parts.password),
        db=database_name(uri),
        charset="utf8mb4",
        ssl=ssl.create_default_context() if tls else None,
        local_infile=False,
        cursorclass=QuietCursor,
    )
    conn.client_flag &= ~CLIENT.MULTI_STATEMENTS
    try:
        async with asyncio.timeout(8):
            await conn._connect()
        async with asyncio.timeout(10):
            mariadb = "mariadb" in conn.get_server_info().lower()
            if mariadb != (dialect == "mariadb"):
                raise ConfigurationError("The server family does not match the registered connector.")
            async with conn.cursor() as cursor:
                if tls:
                    await cursor.execute("SHOW SESSION STATUS LIKE 'Ssl_cipher'")
                    cipher = await cursor.fetchone()
                    if not cipher or not cipher[1]:
                        raise OSError("The server did not negotiate TLS.")
                await cursor.execute(
                    "SET SESSION sql_mode='ONLY_FULL_GROUP_BY,STRICT_TRANS_TABLES,NO_ENGINE_SUBSTITUTION'"
                )
                await cursor.execute(
                    "SET SESSION max_statement_time=8" if mariadb
                    else "SET SESSION max_execution_time=8000"
                )
                await cursor.execute("SET SESSION lock_wait_timeout=2")
                await cursor.execute("START TRANSACTION READ ONLY")
            yield conn
    except aiomysql.Error:
        raise OSError("The MySQL-family target rejected the request.") from None
    finally:
        conn.close()


async def reflect(conn):
    async with conn.cursor() as cursor:
        await cursor.execute("""
            SELECT c.TABLE_NAME,c.COLUMN_NAME,c.DATA_TYPE
            FROM information_schema.COLUMNS c
            JOIN information_schema.TABLES t
              ON CAST(t.TABLE_SCHEMA AS BINARY)=CAST(c.TABLE_SCHEMA AS BINARY)
             AND CAST(t.TABLE_NAME AS BINARY)=CAST(c.TABLE_NAME AS BINARY)
            WHERE CAST(c.TABLE_SCHEMA AS BINARY)=CAST(DATABASE() AS BINARY)
              AND t.TABLE_TYPE='BASE TABLE' AND t.ENGINE='InnoDB'
            ORDER BY c.TABLE_NAME,c.ORDINAL_POSITION
            LIMIT 4097
        """)
        rows = await cursor.fetchall()
    if len(rows) > 4096:
        raise ConfigurationError("Use a target database with at most 4,096 reflected columns.")
    schema = {}
    for table, column, datatype in rows:
        if datatype in SCALAR_TYPES:
            schema.setdefault(table, {})[column] = datatype
    return schema


async def foreign_keys(conn):
    async with conn.cursor() as cursor:
        await cursor.execute("""
            SELECT TABLE_NAME,COLUMN_NAME,REFERENCED_TABLE_NAME,REFERENCED_COLUMN_NAME
            FROM information_schema.KEY_COLUMN_USAGE
            WHERE CAST(TABLE_SCHEMA AS BINARY)=CAST(DATABASE() AS BINARY)
              AND CAST(REFERENCED_TABLE_SCHEMA AS BINARY)=CAST(DATABASE() AS BINARY)
            ORDER BY TABLE_NAME,CONSTRAINT_NAME,ORDINAL_POSITION
            LIMIT 4096
        """)
        return await cursor.fetchall()


async def execute(conn, sql):
    # The enclosing connection closes immediately on a timeout or size limit.
    cursor = await conn.cursor(QuietStreamingCursor)
    await cursor.execute(sql)
    columns = [column[0] for column in cursor.description]
    rows, size = [], 0
    while batch := await cursor.fetchmany(25):
        for row in batch:
            size += sum(len(str(value).encode("utf-8")) for value in row)
            if size > 2_000_000:
                return None
            rows.append(list(row))
    return columns, rows


async def validate_plan(conn, sql):
    try:
        async with conn.cursor() as cursor:
            await cursor.execute("EXPLAIN " + sql)
    except aiomysql.Error:
        raise ValueError("MySQL-family plan validation rejected the draft.") from None
