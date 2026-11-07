"""MORPHY governed query terminal.

Supports both interactive (REPL with prompt-toolkit) and noninteractive
(--sql) modes. Install with ``python -m pip install -e ./cli``.
"""

import argparse
import sys
from uuid import UUID

from .auth import AuthManager
from .client import EngineError, MorphyClient
from .formatting import format_csv, format_json, format_table

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
            "  morphy --sql 'SELECT 1' --json    Output results in JSON format\n"
            "  morphy --sql 'SELECT 1' --csv     Output results in CSV format\n"
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
        help="Query an organization database using saved session or MORPHY_ACCESS_TOKEN",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output noninteractive query results as JSON",
    )
    parser.add_argument(
        "--csv",
        action="store_true",
        help="Output noninteractive query results as CSV",
    )
    args = parser.parse_args()

    auth = AuthManager()
    auth.restore_session()

    try:
        client = MorphyClient(
            args.url,
            args.database,
            token=lambda: auth.get_valid_token(),
        )
    except SystemExit as exc:
        parser.error(str(exc))

    # Noninteractive mode: execute single SQL statement and exit
    if args.sql:
        try:
            result = client.query(args.sql)
            if args.json:
                print(format_json(result))
            elif args.csv:
                print(format_csv(result["columns"], result["rows"]), end="")
            else:
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
        except KeyboardInterrupt:
            print("\nCancelled.", file=sys.stderr)
            sys.exit(130)
        finally:
            client.close()
        return

    # Interactive REPL mode
    try:
        from .shell import run_repl

        run_repl(client, auth_manager=auth)
    except KeyboardInterrupt:
        print()
        sys.exit(130)
    finally:
        client.close()
