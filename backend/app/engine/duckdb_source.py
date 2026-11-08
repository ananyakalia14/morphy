"""Query a trusted, operator-provisioned DuckDB snapshot."""

import os
import re
from contextlib import contextmanager
from pathlib import Path
from threading import Timer

from .security import compile_query


URI = re.compile(r"duckdb:///([a-zA-Z0-9][a-zA-Z0-9_-]{0,63}\.duckdb)")
SCALAR_TYPE = re.compile(
    r"(?:BOOLEAN|U?TINYINT|U?SMALLINT|U?INTEGER|U?BIGINT|FLOAT|DOUBLE|"
    r"DECIMAL\([0-9]+,[0-9]+\)|VARCHAR|DATE|TIMESTAMP|TIMESTAMP WITH TIME ZONE|UUID)"
)


class NotConfigured(RuntimeError):
    pass


class SnapshotMissing(RuntimeError):
    pass


class ResultTooLarge(RuntimeError):
    pass


def snapshot_path(uri, database_id):
    match = URI.fullmatch(uri)
    if not match:
        raise ValueError("Use duckdb:///filename.duckdb with a simple filename.")
    configured_root = os.getenv("MORPHY_DUCKDB_ROOT")
    if not configured_root:
        raise NotConfigured("Configure the local DuckDB snapshot folder on the engine.")
    root = Path(configured_root)
    if not root.is_absolute() or not root.is_dir():
        raise NotConfigured("The local DuckDB snapshot folder must be an existing absolute path.")
    expected = root.resolve() / str(database_id) / match[1]
    if expected.resolve() != expected or not expected.is_file():
        raise SnapshotMissing(f"Provision the snapshot in the DuckDB folder for source {database_id}.")
    return expected


@contextmanager
def connection(path):
    try:
        import duckdb
    except ImportError:
        raise NotConfigured("Install the engine's optional DuckDB requirements.") from None

    conn = None
    timer = None
    try:
        conn = duckdb.connect(
            str(path), read_only=True,
            config={
                "enable_external_access": "false",
                "allow_unsigned_extensions": "false",
                "allow_community_extensions": "false",
                "allow_persistent_secrets": "false",
                "autoinstall_known_extensions": "false",
                "autoload_known_extensions": "false",
                "memory_limit": "128MB",
                "max_temp_directory_size": "0B",
                "threads": "2",
                "lock_configuration": "true",
            },
        )
        timer = Timer(10, conn.interrupt)
        timer.daemon = True
        timer.start()
        yield conn
    except duckdb.Error:
        raise OSError("DuckDB could not complete the request on this snapshot.") from None
    finally:
        if timer is not None:
            timer.cancel()
            timer.join()
        if conn is not None:
            conn.close()


def reflect(conn):
    if conn.execute("""
        SELECT EXISTS(SELECT 1 FROM duckdb_functions()
            WHERE database_name=current_database()
              AND function_type IN ('macro','table_macro'))
    """).fetchone()[0]:
        raise OSError("Use a DuckDB snapshot without persistent macros.")
    columns = conn.execute("""
        SELECT lower(c.table_name), lower(c.column_name), c.data_type
        FROM information_schema.columns c
        JOIN information_schema.tables t USING(table_catalog,table_schema,table_name)
        WHERE c.table_catalog=current_database() AND c.table_schema='main'
          AND t.table_type='BASE TABLE'
        ORDER BY c.table_name,c.ordinal_position LIMIT 4097
    """).fetchall()
    if len(columns) > 4096:
        raise ValueError("Use a DuckDB snapshot with at most 4,096 reflected columns.")
    schema = {}
    for table, column, datatype in columns:
        if SCALAR_TYPE.fullmatch(datatype):
            schema.setdefault(table, {})[column] = datatype
    return schema


def inspect(path, *, include_edges=False):
    with connection(path) as conn:
        schema = reflect(conn)
        edges = []
        if include_edges:
            links = conn.execute("""
                SELECT table_name,constraint_column_names,referenced_table,referenced_column_names
                FROM duckdb_constraints()
                WHERE database_name=current_database() AND schema_name='main'
                  AND constraint_type='FOREIGN KEY'
                LIMIT 4096
            """).fetchall()
            edges = [
                (source.lower(), a.lower(), target.lower(), b.lower())
                for source, columns, target, references in links
                for a, b in zip(columns, references, strict=True)
            ]
        return schema, edges


def execute(path, policy, submitted_sql):
    with connection(path) as conn:
        schema = reflect(conn)
        sql = compile_query(submitted_sql, schema, policy, dialect="duckdb")
        cursor = conn.execute(sql)
        columns = [column[0] for column in cursor.description]
        rows, size = [], 0
        while batch := cursor.fetchmany(25):
            for row in batch:
                size += sum(len(str(value).encode("utf-8")) for value in row)
                if size > 2_000_000:
                    raise ResultTooLarge
                rows.append(list(row))
        return {"columns": columns, "rows": rows, "row_count": len(rows), "sql": sql}


def validate_plan(path, sql):
    try:
        with connection(path) as conn:
            conn.execute("EXPLAIN " + sql).fetchall()
    except OSError:
        raise ValueError("DuckDB plan validation rejected the draft.") from None
