"""Local execution agreement evaluation for trusted Spider/BIRD-style datasets.

Run from backend with python -m app.engine.evaluate --help.
"""

import argparse
import asyncio
from collections import Counter
import json
import os
from pathlib import Path
import sqlite3
import time
from types import SimpleNamespace

import httpx
import sqlglot
from sqlglot import exp
from .nl2sql import draft
from .security import compile_query


def dataset_database(root, database_id):
    if (
        not isinstance(database_id, str)
        or not database_id
        or Path(database_id).name != database_id
    ):
        raise ValueError("Each case needs a plain db_id.")
    root = root.resolve()
    path = (root / database_id / (database_id + ".sqlite")).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise ValueError(
            "The case database must exist inside the supplied database directory."
        )
    return path


def reflected_schema(conn):
    schema, edges = {}, []
    for _, name, kind, *_ in conn.execute("PRAGMA table_list").fetchall():
        if kind != "table" or name.startswith("sqlite_"):
            continue
        quoted = exp.to_identifier(name, quoted=True).sql(dialect="sqlite")
        schema[name] = {
            row[1]: row[2] or "TEXT"
            for row in conn.execute(f"PRAGMA table_info({quoted})")
        }
        for row in conn.execute(f"PRAGMA foreign_key_list({quoted})"):
            if row[4]:  # Explicit referenced columns only.
                edges.append((name, row[3], row[2], row[4]))
    return schema, edges


def result_rows(conn, sql, schema, policy, reference=False):
    validated = compile_query(sql, schema, policy, dialect="sqlite")
    # Reference queries use the validated inner tree with 1001 rows to detect
    # cases beyond the production engine's cap instead of scoring truncation.
    if reference:
        validated = (
            sqlglot.parse_one(validated, read="sqlite")
            .limit(1001)
            .sql(dialect="sqlite")
        )
    deadline = time.monotonic() + 10
    conn.set_progress_handler(lambda: int(time.monotonic() > deadline), 1000)
    return conn.execute(validated).fetchall()


def agreement(reference, predicted, ordered):
    if ordered:
        return reference == predicted
    return Counter(reference) == Counter(predicted)


async def evaluate_case(case, root, config):
    started = time.perf_counter()
    record = {"db_id": case.get("db_id"), "question": case.get("question")}
    conn = None
    try:
        if not isinstance(case.get("question"), str) or not case["question"].strip():
            raise ValueError("Missing question.")
        reference = case.get("query", case.get("SQL"))
        if not isinstance(reference, str) or not reference.strip():
            raise ValueError("Missing query or SQL reference.")
        path = dataset_database(root, case.get("db_id"))
        conn = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)
        conn.execute("PRAGMA query_only=ON")
        conn.execute("PRAGMA trusted_schema=OFF")
        conn.execute("BEGIN")
        schema, edges = reflected_schema(conn)
        policy = {
            "mode": "QUERY_ONLY",
            "table_columns": {t: list(c) for t, c in schema.items()},
            "row_rules": [],
        }
        expected = result_rows(conn, reference, schema, policy, reference=True)
        if len(expected) > 1000:
            return {
                **record,
                "status": "excluded_row_cap",
                "reason": "Reference exceeds the 1000-row engine cap.",
            }
        generated = await draft(config, case["question"], schema, policy, edges)
        candidate = sqlglot.transpile(
            generated["sql"], read="postgres", write="sqlite"
        )[0]
        actual = result_rows(conn, candidate, schema, policy)
        ordered = bool(sqlglot.parse_one(reference, read="sqlite").args.get("order"))
        record.update(
            status="correct" if agreement(expected, actual, ordered) else "mismatch",
            sql=candidate,
            attempts=generated["attempts"],
            expected_rows=len(expected),
            actual_rows=len(actual),
        )
    except (
        ValueError,
        PermissionError,
        sqlite3.Error,
        sqlglot.errors.SqlglotError,
        httpx.HTTPError,
        KeyError,
        TypeError,
    ) as error:
        record.update(status="error", error_type=type(error).__name__)
    finally:
        if conn:
            conn.close()
    record["elapsed_ms"] = round((time.perf_counter() - started) * 1000, 2)
    return record


async def run(args):
    cases = json.loads(args.dataset.read_text(encoding="utf-8"))
    if not isinstance(cases, list):
        raise ValueError("Dataset must be a JSON array.")
    selected = cases[args.offset : args.offset + args.limit]
    if not selected or any(not isinstance(c, dict) for c in selected):
        raise ValueError("Select at least one case represented by a JSON object.")
    config = SimpleNamespace(
        ollama_url=args.ollama_url.rstrip("/"), ollama_model=args.model
    )
    results = []
    for case in selected:
        result = await evaluate_case(case, args.databases, config)
        results.append(result)
        print(
            f'{len(results)}/{len(selected)} {result["db_id"]}: {result["status"]}',
            flush=True,
        )
    counts = Counter(r["status"] for r in results)
    scored = len(results) - counts["excluded_row_cap"]
    report = {
        "evaluation": "MORPHY local execution agreement",
        "model": args.model,
        "selected": len(results),
        "scored": scored,
        "counts": dict(counts),
        "agreement": counts["correct"] / scored if scored else None,
        "comparison": "Exact cell values and column order. Row order is significant when the reference has a top-level ORDER BY. Otherwise compare row multisets.",
        "limits": "Production SQL policy subset and 1000-row cap apply. This is a local diagnostic, not the official Spider/BIRD scoring protocol.",
        "cases": results,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f'Report saved. Scored {scored} cases, correct {counts["correct"]}.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--databases", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument(
        "--model", default=os.getenv("MORPHY_OLLAMA_MODEL", "qwen2.5-coder:7b")
    )
    parser.add_argument(
        "--ollama-url", default=os.getenv("MORPHY_OLLAMA_URL", "http://127.0.0.1:11434")
    )
    args = parser.parse_args()
    if args.limit < 1 or args.offset < 0:
        parser.error("Use a positive limit and a nonnegative offset.")
    try:
        asyncio.run(run(args))
    except (ValueError, OSError) as error:
        parser.exit(1, str(error) + "\n")


if __name__ == "__main__":
    main()
