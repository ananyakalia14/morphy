"""Local sample query service. This API only exposes a synthetic dataset."""
from collections import deque
from contextlib import contextmanager
import logging
import os
import asyncio
from types import SimpleNamespace
import httpx
import sqlite3
import time
import uuid

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
import sqlglot
from sqlglot import exp
from sqlglot.optimizer.qualify import qualify

app = FastAPI(title="MORPHY governed query engine", version="0.3.0")
from .engine.api import router as engine_router
from .engine.nl2sql import draft

app.include_router(engine_router)
log = logging.getLogger("morphy")
SCHEMA = {
    "orders": {"id": "INT", "customer_id": "INT", "product": "TEXT",
               "amount": "REAL", "region": "TEXT", "status": "TEXT", "ordered_at": "TEXT"},
    "customers": {"id": "INT", "name": "TEXT", "region": "TEXT", "plan": "TEXT"},
}
EXAMPLES = {
    "Revenue by product": "SELECT product, ROUND(SUM(amount), 2) AS revenue FROM orders WHERE status = 'paid' GROUP BY product ORDER BY revenue DESC",
    "Monthly revenue": "SELECT SUBSTR(ordered_at, 1, 7) AS month, ROUND(SUM(amount), 2) AS revenue FROM orders WHERE status = 'paid' GROUP BY month ORDER BY month",
    "Top customers": "SELECT c.name, c.plan, ROUND(SUM(o.amount), 2) AS revenue FROM orders o JOIN customers c ON o.customer_id = c.id WHERE o.status = 'paid' GROUP BY c.id, c.name, c.plan ORDER BY revenue DESC",
    "Recent orders": "SELECT id, product, amount, region, status, ordered_at FROM orders ORDER BY ordered_at DESC",
}
FUNCTIONS = {"sum", "count", "avg", "min", "max", "round", "lower", "upper", "length", "substr", "substring", "coalesce", "abs"}
AUDIT = deque(maxlen=100)


@contextmanager
def sample_database():
    # A fresh database per request avoids shared mutations and file access.
    connection = sqlite3.connect(":memory:")
    try:
        connection.executescript("""
            CREATE TABLE customers(id INTEGER, name TEXT, region TEXT, plan TEXT, email TEXT);
            CREATE TABLE orders(id INTEGER, customer_id INTEGER, product TEXT, amount REAL,
                region TEXT, status TEXT, ordered_at TEXT);
        """)
        connection.executemany("INSERT INTO customers VALUES(?,?,?,?,?)", [
            (1, "Studio Koto", "APAC", "enterprise", "private@example.test"),
            (2, "Northstar Labs", "APAC", "growth", "private@example.test"),
            (3, "Orbit Systems", "EMEA", "enterprise", "private@example.test"),
            (4, "Paper & Pixels", "APAC", "starter", "private@example.test"),
            (5, "Westward Co.", "AMER", "growth", "private@example.test"),
        ])
        connection.executemany("INSERT INTO orders VALUES(?,?,?,?,?,?,?)", [
            (101, 1, "Analytics", 2400, "APAC", "paid", "2026-08-10"),
            (102, 2, "Workspace", 960, "APAC", "paid", "2026-08-17"),
            (103, 3, "Analytics", 7800, "EMEA", "paid", "2026-08-22"),
            (104, 1, "Connectors", 1250, "APAC", "paid", "2026-09-05"),
            (105, 4, "Workspace", 320, "APAC", "pending", "2026-09-13"),
            (106, 2, "Analytics", 1850, "APAC", "paid", "2026-09-18"),
            (107, 5, "Connectors", 4200, "AMER", "paid", "2026-10-01"),
            (108, 1, "Workspace", 1100, "APAC", "paid", "2026-10-06"),
            (109, 4, "Connectors", 480, "APAC", "paid", "2026-10-12"),
            (110, 2, "Workspace", 960, "APAC", "paid", "2026-10-21"),
            (111, 4, "Analytics", 760, "APAC", "pending", "2026-11-02"),
            (112, 1, "Analytics", 2650, "APAC", "paid", "2026-11-04"),
        ])
        connection.commit()
        connection.execute("PRAGMA query_only = ON")
        yield connection
    finally:
        connection.close()


class QueryInput(BaseModel):
    sql: str = Field(min_length=1, max_length=8000)


def governed_sql(sql: str) -> str:
    statements = sqlglot.parse(sql, read="sqlite")
    if len(statements) != 1 or not isinstance(statements[0], exp.Select):
        raise ValueError("Submit one SELECT statement.")
    tree = statements[0]
    if tree.args.get("with_") or any(tree.find_all(exp.Subquery, exp.Union, exp.Intersect, exp.Except, exp.Into)):
        raise ValueError("This sample workspace supports flat SELECTs and joins. CTEs and nested queries will arrive with the full engine.")
    tables = list(tree.find_all(exp.Table))
    if not tables or len(tables) > 4:
        raise ValueError("Select from one to four sample tables.")
    for table in tables:
        if table.name not in SCHEMA or table.db or table.catalog:
            raise ValueError("Only the sample orders and customers tables are available.")
    for function in tree.find_all(exp.Func):
        if isinstance(function, (exp.And, exp.Or)):
            continue
        name = function.name if isinstance(function, exp.Anonymous) else function.sql_name()
        if name.lower() not in FUNCTIONS:
            raise ValueError("That SQL function is unavailable in the sample workspace.")
    # Resolve aliases and expand stars against the allowed schema, excluding email.
    tree = qualify(tree, dialect="sqlite", schema=SCHEMA, validate_qualify_columns=True)
    for column in tree.find_all(exp.Column):
        if column.name.lower() == "email":
            raise ValueError("The email column is restricted.")
    # Restrict each source BEFORE joins, aggregation and user WHERE expressions.
    # A user OR predicate cannot widen these independently filtered subqueries.
    for table in list(tree.find_all(exp.Table)):
        name, alias = table.name, table.alias_or_name
        source = exp.select(*[exp.column(c) for c in SCHEMA[name]]).from_(name)
        source = source.where(exp.column("region").eq(exp.Literal.string("APAC")))
        table.replace(source.subquery(alias))
    # An outer cap also covers user-supplied negative or excessive LIMIT values.
    return exp.select("*").from_(tree.subquery("governed")).limit(100).sql(dialect="sqlite", pretty=True)


@app.get("/api/sample/schema")
def schema():
    return {"name": "Commerce / sample", "dialect": "SQLite", "tables": SCHEMA,
            "examples": list(EXAMPLES), "policy": {"region": "APAC", "mode": "QUERY_ONLY",
            "restricted_columns": ["customers.email"], "max_rows": 100},
            "generation": "Curated examples + SQL editor"}


class QuestionInput(BaseModel):
    question: str = Field(min_length=1, max_length=200)

model_slot = asyncio.Semaphore(1)


@app.post("/api/sample/ask")
async def ask_sample(payload: QuestionInput):
    if model_slot.locked():
        raise HTTPException(429, "The local model is answering another question. Try again shortly.")
    config = SimpleNamespace(ollama_url=os.getenv("MORPHY_OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/"),
                             ollama_model=os.getenv("MORPHY_OLLAMA_MODEL", "qwen2.5-coder:7b"))
    policy = {"mode": "QUERY_ONLY", "table_columns": {t:list(cols) for t,cols in SCHEMA.items()}, "row_rules": []}
    try:
        async with model_slot:
            generated = await draft(config, payload.question, SCHEMA, policy,
                                    [("orders","customer_id","customers","id")])
        sql = sqlglot.transpile(generated["sql"], read="postgres", write="sqlite")[0]
        governed_sql(sql)
        return {**generated, "sql":sql}
    except httpx.HTTPError:
        raise HTTPException(503, "Ollama is unavailable. Start the local model or select a curated example.")
    except (KeyError, TypeError, ValueError, PermissionError, sqlglot.errors.SqlglotError):
        raise HTTPException(422, "The model could not produce a permitted query. Try a more specific question.")


@app.post("/api/sample/generate")
def generate(payload: QuestionInput):
    # Explicit example matching keeps the sample useful without an LLM dependency.
    sql = EXAMPLES.get(payload.question)
    if not sql:
        raise HTTPException(422, "Choose one of the example questions or write SQL in the editor.")
    return {"sql": sql, "provider": "curated example"}


@app.post("/api/sample/query")
def query(payload: QueryInput):
    started = time.perf_counter()
    request_id = uuid.uuid4().hex[:12]
    try:
        compiled = governed_sql(payload.sql)
        with sample_database() as connection:
            deadline = time.monotonic() + 2
            connection.set_progress_handler(lambda: int(time.monotonic() > deadline), 1000)
            def authorize(action, arg1, arg2, database, source):
                if action == sqlite3.SQLITE_READ:
                    return sqlite3.SQLITE_OK if arg1 in SCHEMA and (not arg2 or arg2 in SCHEMA[arg1]) else sqlite3.SQLITE_DENY
                if action in (sqlite3.SQLITE_SELECT, sqlite3.SQLITE_RECURSIVE):
                    return sqlite3.SQLITE_OK
                if action == sqlite3.SQLITE_FUNCTION:
                    return sqlite3.SQLITE_OK if (arg2 or "").lower() in FUNCTIONS else sqlite3.SQLITE_DENY
                return sqlite3.SQLITE_DENY
            connection.set_authorizer(authorize)
            cursor = connection.execute(compiled)
            result = cursor.fetchall()
            columns = [c[0] for c in cursor.description]
        elapsed = round((time.perf_counter() - started) * 1000, 2)
        AUDIT.append({"id": request_id, "status": "executed", "rows": len(result)})
        return {"id": request_id, "columns": columns, "rows": result, "sql": compiled,
                "elapsed_ms": elapsed, "row_count": len(result), "row_cap": 100}
    except (ValueError, sqlglot.errors.SqlglotError, sqlite3.Error) as error:
        AUDIT.append({"id": request_id, "status": "blocked"})
        log.info("Sample query blocked %s: %s", request_id, type(error).__name__)
        raise HTTPException(422, str(error)) from error


@app.get("/api/health")
def health():
    return {"status": "ready", "service": "sample", "version": app.version}
