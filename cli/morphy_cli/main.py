"""Thin HTTP client for the synthetic sample workspace."""

import argparse
import os
from uuid import UUID
from urllib.parse import urlsplit
import json
import httpx


def main():
    parser = argparse.ArgumentParser(description="MORPHY sample workspace terminal")
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument("--sql", help="Run one read query and exit")
    parser.add_argument(
        "--database",
        type=UUID,
        help="Query an organization database using MORPHY_ACCESS_TOKEN",
    )
    args = parser.parse_args()
    prefix = (
        f"/api/engine/databases/{args.database}" if args.database else "/api/sample"
    )
    headers = {}
    if args.database:
        token = os.getenv("MORPHY_ACCESS_TOKEN")
        if not token:
            parser.error(
                "Set MORPHY_ACCESS_TOKEN to your active Supabase session token."
            )
        endpoint = urlsplit(args.url)
        if endpoint.scheme != "https" and not (
            endpoint.scheme == "http"
            and endpoint.hostname in {"localhost", "127.0.0.1", "::1"}
        ):
            parser.error("Use HTTPS or a loopback address for authenticated requests.")
        headers["Authorization"] = "Bearer " + token
    with httpx.Client(
        base_url=args.url, timeout=195, headers=headers, follow_redirects=False
    ) as client:

        def request(path, payload=None):
            response = (
                client.get(path) if payload is None else client.post(path, json=payload)
            )
            if response.is_error:
                try:
                    detail = response.json().get("detail", response.text)
                except ValueError:
                    detail = response.text
                raise ValueError(str(detail))
            return response.json()

        def execute(sql):
            result = request(prefix + "/query", {"sql": sql})
            print(" | ".join(result["columns"]))
            for row in result["rows"]:
                print(" | ".join("NULL" if v is None else str(v) for v in row))
            print(f'{result["row_count"]} rows · {result["elapsed_ms"]} ms')

        if args.sql:
            try:
                execute(args.sql)
            except (ValueError, httpx.HTTPError) as error:
                parser.exit(1, f"{error}\n")
            return
        print(
            f"MORPHY / {args.database}\n/help for commands"
            if args.database
            else "MORPHY / SAMPLE WORKSPACE\nSynthetic commerce data · APAC analyst\n/help for commands"
        )
        while True:
            try:
                line = input("morphy > ").strip()
                if line in ("/exit", "/quit"):
                    return
                if not line:
                    continue
                if line == "/help":
                    print(
                        "/schema · /examples · /ask <example title> · /sql <SELECT ...> · /exit"
                    )
                elif line in ("/schema", "/examples"):
                    metadata = request(prefix + "/schema")
                    print(
                        json.dumps(
                            (
                                metadata["tables"]
                                if line == "/schema"
                                else metadata.get(
                                    "examples", ["Use /ask followed by your question."]
                                )
                            ),
                            indent=2,
                        )
                    )
                elif line.startswith("/ask "):
                    generated = request(prefix + "/generate", {"question": line[5:]})
                    print(generated["sql"])
                    if (
                        not args.database
                        or input("Execute this SQL? [y/N] ").strip().lower() == "y"
                    ):
                        execute(generated["sql"])
                elif line.startswith("/sql "):
                    execute(line[5:])
                else:
                    print("Use /sql followed by a SELECT query, or /help.")
            except (EOFError, KeyboardInterrupt):
                print()
                return
            except (ValueError, httpx.HTTPError) as error:
                print(f"Request failed: {error}")
