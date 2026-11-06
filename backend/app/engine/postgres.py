from contextlib import asynccontextmanager
import asyncpg

# Only ordinary public tables and built-in scalar types are exposed in v1.
TYPES = {
    "int2",
    "int4",
    "int8",
    "float4",
    "float8",
    "numeric",
    "text",
    "varchar",
    "bpchar",
    "bool",
    "date",
    "timestamp",
    "timestamptz",
    "uuid",
}


@asynccontextmanager
async def connection(uri):
    conn = await asyncpg.connect(uri, timeout=8, command_timeout=10)
    try:
        async with conn.transaction(readonly=True):
            await conn.execute("SET LOCAL statement_timeout = '10s'")
            await conn.execute("SET LOCAL lock_timeout = '2s'")
            await conn.execute("SET LOCAL search_path = pg_catalog")
            yield conn
    finally:
        await conn.close(timeout=3)


async def reflect(conn):
    rows = await conn.fetch("""
      SELECT c.table_name, c.column_name, c.udt_name
      FROM information_schema.columns c
      JOIN information_schema.tables t USING(table_catalog,table_schema,table_name)
      WHERE c.table_schema='public' AND t.table_type='BASE TABLE'
      AND has_table_privilege(format('%I.%I',c.table_schema,c.table_name),'SELECT')
      ORDER BY c.table_name,c.ordinal_position
    """)
    schema = {}
    for row in rows:
        if row["udt_name"] in TYPES:
            schema.setdefault(row["table_name"], {})[row["column_name"]] = row[
                "udt_name"
            ]
    return schema
