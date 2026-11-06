"""MORPHY governed query terminal.

Supports both interactive (REPL with prompt-toolkit) and noninteractive
(--sql) modes.  Install with ``python -m pip install -e ./cli``.
"""

import argparse
import sys
from uuid import UUID

from .client import MorphyClient, EngineError
from .formatting import format_table

import httpx


def main():
    parser = argparse.ArgumentParser(
        prog="morphy",
        description="MORPHY — governed natural-language database terminal",
        epilog=(
            "Examples:\n"
            "  morphy                            Open the sample REPL\n"
            "  morphy --database <UUID>          Query an organization database\n"
            "  morphy --sql 'SELECT 1'           Run one query and exit\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--url",
        default="http://127.0.0.1:8000",
        help="Engine base URL (default: http://127.0.0.1:8000)",
    )
    parser.add_argument(
        "--sql",
        metavar="QUERY",
        help="Run one read-only SQL query and exit",
    )
    parser.add_argument(
        "--database",
        type=UUID,
        metavar="UUID",
        help="Query an organization database using MORPHY_ACCESS_TOKEN",
    )
    args = parser.parse_args()

    try:
        client = MorphyClient(args.url, args.database)
    except SystemExit as exc:
        parser.error(str(exc))

    # Noninteractive: run a single SQL query and exit.
    if args.sql:
        try:
            result = client.query(args.sql)
            print(
                format_table(
                    result["columns"],
                    result["rows"],
                    result["row_count"],
                    result["elapsed_ms"],
                )
            )
        except EngineError as error:
            print(f"Error: {error.detail}", file=sys.stderr)
            sys.exit(1)
        except httpx.HTTPError as error:
            print(f"Network error: {error}", file=sys.stderr)
            sys.exit(2)
        finally:
            client.close()
        return

    # Interactive REPL.
    try:
        from .shell import run_repl

        run_repl(client)
    except KeyboardInterrupt:
        print()
    finally:
        client.close()
