import sqlite3
from contextlib import closing
import pytest
from sqlglot.errors import SqlglotError
from app.engine.security import compile_query
from app.engine.nl2sql import Glossary

SCHEMA = {"orders": {"id": "INT", "amount": "INT", "region": "TEXT", "secret": "TEXT"}}
POLICY = {
    "mode": "QUERY_ONLY",
    "table_columns": {"orders": ["id", "amount", "region"]},
    "row_rules": [{"table": "orders", "column": "region", "op": "eq", "value": "APAC"}],
}


@pytest.mark.parametrize(
    "sql,expected",
    [
        (
            "WITH orders AS (SELECT amount FROM orders) SELECT SUM(amount) FROM orders",
            [(20,)],
        ),
        (
            "SELECT SUM(amount) FROM (SELECT amount FROM orders WHERE 1=1 OR region='EU') x",
            [(20,)],
        ),
        ("SELECT id FROM orders UNION SELECT id FROM orders", [(1,)]),
        ("SELECT id FROM orders INTERSECT SELECT id FROM orders", [(1,)]),
        ("SELECT id FROM orders EXCEPT SELECT id FROM orders WHERE amount>100", [(1,)]),
        (
            "SELECT o.id FROM orders o WHERE EXISTS (SELECT 1 FROM orders x WHERE x.id=o.id)",
            [(1,)],
        ),
    ],
)
def test_every_source_is_filtered(sql, expected):
    compiled = compile_query(sql, SCHEMA, POLICY, dialect="sqlite")
    with closing(sqlite3.connect(":memory:")) as conn:
        conn.executescript(
            "CREATE TABLE orders(id int,amount int,region text,secret text); INSERT INTO orders VALUES(1,20,'APAC','private'),(2,999,'EU','private')"
        )
        assert conn.execute(compiled).fetchall() == expected


@pytest.mark.parametrize(
    "sql",
    [
        "WITH x AS (SELECT secret FROM orders) SELECT * FROM x",
        "SELECT id FROM orders UNION SELECT id FROM private",
        "WITH x AS (DELETE FROM orders RETURNING id) SELECT id FROM x",
        "WITH RECURSIVE x AS (SELECT id FROM orders) SELECT * FROM x",
        "SELECT id FROM orders WHERE EXISTS (SELECT secret FROM orders)",
    ],
)
def test_nested_escape_attempts_fail(sql):
    with pytest.raises((ValueError, PermissionError, SqlglotError)):
        compile_query(sql, SCHEMA, POLICY)


def test_restore_reused_aliases_in_nested_scopes():
    schema = {"orders": {"id": "INT"}, "customers": {"customer_id": "INT"}}
    g = Glossary(schema, [])
    t, c = g.tables, g.columns
    query = f'SELECT o.{c["orders"]["id"]} AS id FROM {t["orders"]} o WHERE EXISTS (SELECT 1 FROM {t["customers"]} o WHERE o.{c["customers"]["customer_id"]}=1)'
    restored = g.restore(query)
    policy = {
        "mode": "QUERY_ONLY",
        "table_columns": {"orders": ["id"], "customers": ["customer_id"]},
        "row_rules": [],
    }
    compile_query(restored, schema, policy)


def test_restore_correlated_column_once():
    schema = {"orders": {"id": "INT"}, "customers": {"customer_id": "INT"}}
    g = Glossary(schema, [])
    t, c = g.tables, g.columns
    query = f'SELECT o.{c["orders"]["id"]} AS id FROM {t["orders"]} o WHERE EXISTS (SELECT 1 FROM {t["customers"]} c WHERE c.{c["customers"]["customer_id"]}=o.{c["orders"]["id"]})'
    restored = g.restore(query)
    policy = {
        "mode": "QUERY_ONLY",
        "table_columns": {"orders": ["id"], "customers": ["customer_id"]},
        "row_rules": [],
    }
    compile_query(restored, schema, policy)
