"""Result formatting for the MORPHY terminal."""

import csv
import io
import json
from typing import Any, Sequence


def format_table(columns: list[str], rows: list[list], row_count: int, elapsed_ms: float) -> str:
    """Format query results as a readable aligned table."""
    if not columns:
        return f"(empty result · {elapsed_ms} ms)"

    # Convert values to display strings, respecting NULLs.
    str_rows = []
    for row in rows:
        str_rows.append(["\u2205" if v is None else str(v) for v in row])

    # Compute column widths.
    widths = [len(c) for c in columns]
    for row in str_rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(cell))

    # Cap each column at 48 characters for readability.
    widths = [min(w, 48) for w in widths]

    def truncate(text: str, width: int) -> str:
        return text if len(text) <= width else text[: width - 1] + "\u2026"

    lines = []
    header = " \u2502 ".join(truncate(c, w).ljust(w) for c, w in zip(columns, widths))
    lines.append(header)
    lines.append("\u2500" * len(header))
    for row in str_rows:
        line = " \u2502 ".join(truncate(cell, w).ljust(w) for cell, w in zip(row, widths))
        lines.append(line)

    capped = " (capped)" if row_count >= 1000 else ""
    lines.append(f"\n{row_count} row{'s' if row_count != 1 else ''}{capped} · {elapsed_ms} ms")
    return "\n".join(lines)


def format_csv(columns: list[str], rows: list[list]) -> str:
    """Export query results as a standard RFC-4180 CSV string."""
    output = io.StringIO()
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(columns)
    for row in rows:
        writer.writerow(["" if cell is None else cell for cell in row])
    return output.getvalue()


def format_records_table(headers: list[str], items: list[dict[str, Any]], keys: list[str]) -> str:
    """Format an arbitrary list of objects as an aligned CLI table."""
    if not items:
        return "(none)"
    rows = [[str(item.get(k, "")) for k in keys] for item in items]
    return format_table(headers, rows, len(items), 0.0).split("\n\n")[0]


def format_schema(tables: dict) -> str:
    """Format schema metadata as an indented tree."""
    if not tables:
        return "(no permitted tables)"
    lines = []
    for table, columns in tables.items():
        lines.append(f"  {table}")
        if isinstance(columns, dict):
            for col, dtype in columns.items():
                lines.append(f"    {col}: {dtype}")
        elif isinstance(columns, list):
            for col in columns:
                lines.append(f"    {col}")
    return "\n".join(lines)


def format_examples(examples: list[str]) -> str:
    """Format example question titles."""
    if not examples:
        return "(no examples available)"
    return "\n".join(f"  • {title}" for title in examples)


def format_generation(gen: dict) -> str:
    """Format a generation response showing SQL and metadata."""
    lines = []
    lines.append(gen["sql"])
    meta = []
    if gen.get("provider"):
        meta.append(gen["provider"])
    if gen.get("attempts"):
        meta.append(f"{gen['attempts']} attempt{'s' if gen['attempts'] != 1 else ''}")
    if gen.get("cache"):
        meta.append(f"cache {gen['cache']}")
    if meta:
        lines.append(f"({' · '.join(meta)})")
    return "\n".join(lines)


def format_json(data: Any) -> str:
    """Pretty-print arbitrary data as JSON."""
    return json.dumps(data, indent=2, default=str)
