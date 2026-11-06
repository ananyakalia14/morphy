"""Interactive prompt-toolkit REPL for MORPHY."""

import sys

from prompt_toolkit import PromptSession
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.formatted_text import HTML

from .client import MorphyClient, EngineError
from .completer import SlashCompleter
from .formatting import (
    format_table,
    format_schema,
    format_examples,
    format_generation,
)

import httpx


_HELP_TEXT = """\
Available commands:
  /help                Show this help message
  /schema              Display the permitted database schema
  /examples            List curated example questions
  /ask <question>      Generate SQL from a natural-language question
  /sql <SELECT ...>    Execute a read-only SQL query
  /exit or /quit       Leave the session

Tips:
  • Tab completes slash commands.
  • Ctrl+C cancels the current input; Ctrl+D exits.
  • Use --sql to run a single query without entering the REPL."""


def _banner(client: MorphyClient) -> str:
    if client.is_live:
        return f"MORPHY / {client.database}\n/help for commands"
    return (
        "MORPHY / SAMPLE WORKSPACE\n"
        "Synthetic commerce data · APAC analyst\n"
        "/help for commands"
    )


def _execute_sql(client: MorphyClient, sql: str) -> str:
    """Execute SQL and return a formatted result string."""
    result = client.query(sql)
    return format_table(
        result["columns"], result["rows"], result["row_count"], result["elapsed_ms"]
    )


def _handle_command(client: MorphyClient, line: str) -> str | None:
    """Dispatch a single command. Returns the output string or None for exit."""
    if line in ("/exit", "/quit"):
        return None

    if line == "/help":
        return _HELP_TEXT

    if line in ("/schema", "/examples"):
        metadata = client.schema()
        if line == "/schema":
            return format_schema(metadata.get("tables", {}))
        return format_examples(
            metadata.get("examples", ["Use /ask followed by your question."])
        )

    if line.startswith("/ask "):
        question = line[5:].strip()
        if not question:
            return "Usage: /ask <question>"
        generated = client.generate(question)
        output = format_generation(generated)
        if not client.is_live:
            # Sample mode: execute immediately.
            result = _execute_sql(client, generated["sql"])
            return output + "\n\n" + result
        # Live mode: confirm before execution.
        try:
            confirm = input("Execute this SQL? [y/N] ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            return "\nCancelled."
        if confirm == "y":
            result = _execute_sql(client, generated["sql"])
            return output + "\n\n" + result
        return output + "\n(not executed)"

    if line.startswith("/sql "):
        sql = line[5:].strip()
        if not sql:
            return "Usage: /sql <SELECT ...>"
        return _execute_sql(client, sql)

    return "Unknown command. Use /sql followed by a SELECT query, or /help."


def run_repl(client: MorphyClient):
    """Launch the interactive prompt-toolkit REPL."""
    print(_banner(client))

    bindings = KeyBindings()

    @bindings.add("c-c")
    def _(event):
        """Ctrl+C clears the current buffer instead of raising."""
        event.current_buffer.reset()
        print()

    session: PromptSession = PromptSession(
        message=HTML("<ansigreen>morphy &gt;</ansigreen> "),
        completer=SlashCompleter(is_live=client.is_live),
        history=InMemoryHistory(),
        key_bindings=bindings,
        complete_while_typing=False,
    )

    while True:
        try:
            line = session.prompt().strip()
        except KeyboardInterrupt:
            continue
        except EOFError:
            print()
            break

        if not line:
            continue

        try:
            output = _handle_command(client, line)
        except EngineError as error:
            print(f"Error: {error.detail}")
            continue
        except httpx.HTTPError as error:
            print(f"Network error: {error}")
            continue

        if output is None:
            break
        print(output)
