"""Read a bounded, UTF-8 CSV as a single SQLite table named records."""

import csv
import io
import re
import sqlite3
import time
from contextlib import closing
from .security import compile_query


def read_csv(contents):
    reader = csv.reader(io.StringIO(contents, newline=""), strict=True)
    try:
        fields = next(reader, [])
        if not 1 <= len(fields) <= 64 or len(set(c.lower() for c in fields)) != len(
            fields
        ):
            raise ValueError("Use 1–64 uniquely named columns.")
        if any(not re.fullmatch(r"[a-zA-Z_][a-zA-Z_0-9]{0,62}", c) for c in fields):
            raise ValueError(
                "Column names may contain letters, digits and underscores."
            )
        data = []
        for row in reader:
            if not row:
                continue
            if (
                len(row) != len(fields)
                or len(data) >= 20000
                or any(len(v) > 16384 for v in row)
            ):
                raise ValueError(
                    "Each record must match the header. Limits are 20,000 rows and 16 KB per value."
                )
            data.append(tuple(None if v == "" else v for v in row))
    except csv.Error as error:
        raise ValueError("Invalid CSV quoting or field size.") from error
    # Preserve source strings exactly, including leading zeroes in identifiers.
    return {"records": dict.fromkeys(fields, "TEXT")}, data


def execute_csv(contents, policy, query):
    schema, rows = read_csv(contents)
    sql = compile_query(query, schema, policy, dialect="sqlite")
    with closing(sqlite3.connect(":memory:")) as conn:
        columns = schema["records"]
        definitions = ", ".join(f'"{c}" TEXT' for c in columns)
        conn.execute(f"CREATE TABLE records({definitions})")
        placeholders = ", ".join("?" for _ in columns)
        conn.executemany(f"INSERT INTO records VALUES({placeholders})", rows)
        conn.execute("PRAGMA query_only=ON")
        deadline = time.monotonic() + 10
        conn.set_progress_handler(lambda: int(time.monotonic() > deadline), 1000)
        cursor = conn.execute(sql)
        result, size = [], 0
        for row in cursor:
            size += sum(len(str(value).encode("utf-8")) for value in row)
            if size > 2_000_000:
                raise ValueError(
                    "The result exceeds 2 MB. Select fewer columns or rows."
                )
            result.append(row)
        return {
            "sql": sql,
            "columns": [c[0] for c in cursor.description],
            "rows": result,
            "row_count": len(result),
        }
