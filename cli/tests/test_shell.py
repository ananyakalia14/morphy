"""Tests for the MORPHY CLI interactive shell and formatting."""

import sys
import types
import pytest
from unittest.mock import patch, MagicMock

from morphy_cli.formatting import (
    format_table,
    format_schema,
    format_examples,
    format_generation,
)
from morphy_cli.completer import SlashCompleter
from morphy_cli.client import MorphyClient, EngineError
from morphy_cli.shell import _handle_command


# ── Formatting ──────────────────────────────────────────────────────


class TestFormatTable:
    def test_basic_table(self):
        result = format_table(["id", "name"], [[1, "Alice"], [2, "Bob"]], 2, 3.5)
        assert "id" in result
        assert "Alice" in result
        assert "2 rows" in result
        assert "3.5 ms" in result

    def test_empty_columns(self):
        result = format_table([], [], 0, 1.0)
        assert "empty result" in result

    def test_null_display(self):
        result = format_table(["x"], [[None]], 1, 0.5)
        assert "\u2205" in result

    def test_single_row_grammar(self):
        result = format_table(["x"], [[1]], 1, 0.5)
        assert "1 row " in result
        assert "rows" not in result

    def test_capped_indicator(self):
        result = format_table(["x"], [[1]], 1000, 0.5)
        assert "capped" in result


class TestFormatSchema:
    def test_empty(self):
        assert "no permitted" in format_schema({})

    def test_tree(self):
        result = format_schema({"users": {"id": "int4", "name": "text"}})
        assert "users" in result
        assert "id: int4" in result


class TestFormatExamples:
    def test_empty(self):
        assert "no examples" in format_examples([])

    def test_bullets(self):
        result = format_examples(["Total sales", "Average order"])
        assert "• Total sales" in result
        assert "• Average order" in result


class TestFormatGeneration:
    def test_basic(self):
        gen = {"sql": "SELECT 1", "provider": "qwen", "attempts": 2, "cache": "miss"}
        result = format_generation(gen)
        assert "SELECT 1" in result
        assert "qwen" in result
        assert "2 attempts" in result
        assert "cache miss" in result

    def test_single_attempt(self):
        gen = {"sql": "SELECT 1", "provider": None, "attempts": 1, "cache": "hit"}
        result = format_generation(gen)
        assert "1 attempt" in result
        assert "attempts" not in result.replace("1 attempt", "")


# ── Completer ───────────────────────────────────────────────────────


class TestSlashCompleter:
    def _complete(self, text):
        completer = SlashCompleter(is_live=False)
        doc = MagicMock()
        doc.text_before_cursor = text
        doc.cursor_position = len(text)
        event = MagicMock()
        return list(completer.get_completions(doc, event))

    def test_slash_prefix(self):
        results = self._complete("/h")
        names = [c.text for c in results]
        assert "/help" in names

    def test_all_commands(self):
        results = self._complete("/")
        names = [c.text for c in results]
        assert "/help" in names
        assert "/schema" in names
        assert "/exit" in names

    def test_no_completion_without_slash(self):
        results = self._complete("sel")
        assert results == []


# ── Command dispatch ────────────────────────────────────────────────


class MockClient:
    """Minimal MorphyClient stand-in for unit tests."""

    def __init__(self, *, is_live=False):
        self.database = "test-uuid" if is_live else None
        self.is_live = is_live

    def schema(self):
        return {
            "tables": {"orders": {"id": "int4", "total": "numeric"}},
            "examples": ["Total revenue", "Average order size"],
        }

    def generate(self, question):
        return {
            "sql": "SELECT sum(total) FROM orders",
            "provider": "qwen",
            "attempts": 1,
            "cache": "miss",
            "requires_execution": True,
        }

    def query(self, sql):
        return {
            "columns": ["sum"],
            "rows": [[11650]],
            "row_count": 1,
            "sql": sql,
            "elapsed_ms": 5.2,
        }


class TestHandleCommand:
    def test_help(self):
        result = _handle_command(MockClient(), "/help")
        assert "/schema" in result
        assert "/ask" in result

    def test_exit(self):
        assert _handle_command(MockClient(), "/exit") is None
        assert _handle_command(MockClient(), "/quit") is None

    def test_schema(self):
        result = _handle_command(MockClient(), "/schema")
        assert "orders" in result
        assert "int4" in result

    def test_examples(self):
        result = _handle_command(MockClient(), "/examples")
        assert "Total revenue" in result

    def test_ask_sample_mode(self):
        result = _handle_command(MockClient(), "/ask Total revenue")
        assert "SELECT sum(total)" in result
        assert "11650" in result

    def test_ask_live_mode_decline(self):
        client = MockClient(is_live=True)
        with patch("builtins.input", return_value="n"):
            result = _handle_command(client, "/ask Total revenue")
        assert "not executed" in result

    def test_ask_live_mode_accept(self):
        client = MockClient(is_live=True)
        with patch("builtins.input", return_value="y"):
            result = _handle_command(client, "/ask Total revenue")
        assert "11650" in result

    def test_sql(self):
        result = _handle_command(MockClient(), "/sql SELECT 1")
        assert "sum" in result

    def test_unknown_command(self):
        result = _handle_command(MockClient(), "foobar")
        assert "Unknown" in result or "/help" in result

    def test_ask_empty_question(self):
        result = _handle_command(MockClient(), "/ask ")
        assert "Usage" in result

    def test_sql_empty_query(self):
        result = _handle_command(MockClient(), "/sql ")
        assert "Usage" in result


# ── Client ──────────────────────────────────────────────────────────


class TestClientInit:
    def test_sample_mode(self):
        client = MorphyClient("http://127.0.0.1:8000")
        assert client.prefix == "/api/sample"
        assert not client.is_live
        client.close()

    def test_live_requires_token(self):
        from uuid import UUID

        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(SystemExit):
                MorphyClient("http://127.0.0.1:8000", UUID("12345678-1234-1234-1234-123456789abc"))

    def test_live_requires_https_for_remote(self):
        from uuid import UUID

        with patch.dict("os.environ", {"MORPHY_ACCESS_TOKEN": "test-token"}):
            with pytest.raises(SystemExit):
                MorphyClient("http://example.com:8000", UUID("12345678-1234-1234-1234-123456789abc"))

    def test_live_allows_localhost(self):
        from uuid import UUID

        with patch.dict("os.environ", {"MORPHY_ACCESS_TOKEN": "test-token"}):
            client = MorphyClient("http://127.0.0.1:8000", UUID("12345678-1234-1234-1234-123456789abc"))
            assert client.is_live
            client.close()


class TestEngineError:
    def test_attributes(self):
        err = EngineError(403, "denied")
        assert err.status_code == 403
        assert err.detail == "denied"
        assert "denied" in str(err)


# ── CLI entrypoint ──────────────────────────────────────────────────


class TestMainEntrypoint:
    def test_help_flag(self):
        with pytest.raises(SystemExit) as exc:
            sys.argv = ["morphy", "--help"]
            from morphy_cli.main import main

            main()
        assert exc.value.code == 0
