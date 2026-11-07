"""Read a bounded, UTF-8 CSV as a single SQLite table named records."""

import csv
import io
import math
import re
import sqlite3
import time
from contextlib import closing
from .security import compile_query


def numeric_text(value):
    if value is None or not re.fullmatch(
        r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?",
        str(value).strip(),
    ):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def parquet_to_csv(contents):
    """Normalize bounded, flat Parquet uploads to the existing encrypted format."""
    import pyarrow as pa
    import pyarrow.parquet as pq

    try:
        source = pq.ParquetFile(
            pa.BufferReader(contents),
            thrift_string_size_limit=1_048_576,
            thrift_container_size_limit=65536,
        )
        metadata = source.metadata
        if metadata.num_rows > 20000 or not 1 <= metadata.num_columns <= 64:
            raise ValueError("Parquet limits are 20,000 rows and 1–64 columns.")
        expanded = sum(
            metadata.row_group(i).total_byte_size
            for i in range(metadata.num_row_groups)
        )
        if expanded > 16_777_216:
            raise ValueError("Parquet expanded data must fit within 16 MB.")
        for field in source.schema_arrow:
            kind = field.type
            if not (
                pa.types.is_string(kind)
                or pa.types.is_integer(kind)
                or pa.types.is_boolean(kind)
                or pa.types.is_floating(kind)
                or pa.types.is_decimal(kind)
                or pa.types.is_date(kind)
                or pa.types.is_timestamp(kind)
                or pa.types.is_null(kind)
            ):
                raise ValueError(
                    "Use flat text, numeric, boolean, date or timestamp columns."
                )
        output = io.StringIO(newline="")
        writer = csv.writer(output)
        writer.writerow(source.schema_arrow.names)
        for batch in source.iter_batches(batch_size=256, use_threads=False):
            for row in zip(*(column.to_pylist() for column in batch.columns)):
                values = ["" if value is None else str(value) for value in row]
                if any(len(value) > 16384 for value in values):
                    raise ValueError("Parquet values must fit within 16 KB.")
                writer.writerow(values)
                if output.tell() > 1_048_576:
                    raise ValueError("Parquet normalized CSV must fit within 1 MB.")
        text = output.getvalue()
        if len(text.encode("utf-8")) > 1_048_576:
            raise ValueError("Parquet normalized CSV must fit within 1 MB.")
        read_csv(text)
        return text
    except (pa.ArrowException, OSError) as error:
        raise ValueError("Invalid or unsupported Parquet file.") from error


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
        conn.create_function("morphy_number", 1, numeric_text, deterministic=True)
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
