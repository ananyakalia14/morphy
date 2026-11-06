"""Comprehensive tests for the MORPHY CLI, auth, control plane, shell and formatting."""

import io
import json
import os
from pathlib import Path
import sys
import time
from unittest.mock import MagicMock, patch
from uuid import UUID

import pytest

from morphy_cli.auth import AuthError, AuthManager, Session
from morphy_cli.client import EngineError, MorphyClient
from morphy_cli.completer import SlashCompleter
from morphy_cli.control import ControlClient, ControlPlaneError
from morphy_cli.formatting import (
    format_banner,
    format_csv,
    format_examples,
    format_generation,
    format_json,
    format_records_table,
    format_schema,
    format_table,
)
from morphy_cli.shell import ShellContext, _handle_command


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


class TestFormatCSV:
    def test_csv_output(self):
        result = format_csv(["id", "name"], [[1, "Alpha"], [2, None]])
        lines = result.strip().split("\n")
        assert lines[0] == "id,name"
        assert lines[1] == "1,Alpha"
        assert lines[2] == "2,"


class TestFormatRecordsTable:
    def test_records_table(self):
        items = [{"id": "1", "name": "Org 1"}, {"id": "2", "name": "Org 2"}]
        table = format_records_table(["ID", "Name"], items, ["id", "name"])
        assert "Org 1" in table
        assert "Org 2" in table

    def test_empty_records(self):
        assert format_records_table(["ID"], [], ["id"]) == "(none)"


class TestFormatSchema:
    def test_empty(self):
        assert "no permitted" in format_schema({})

    def test_tree_dict(self):
        result = format_schema({"users": {"id": "int4", "name": "text"}})
        assert "users" in result
        assert "id: int4" in result

    def test_tree_list(self):
        result = format_schema({"records": ["a", "b"]})
        assert "records" in result
        assert "a" in result


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


class TestFormatJSON:
    def test_json_dump(self):
        data = {"hello": "world", "num": 42}
        assert '"hello": "world"' in format_json(data)


class TestFormatBanner:
    def test_sample_banner(self):
        banner = format_banner(version="0.5.0", engine_url="http://127.0.0.1:8000")
        assert "███" in banner
        assert "v0.5.0" in banner
        assert "SAMPLE" in banner
        assert "http://127.0.0.1:8000" in banner

    def test_live_banner(self):
        banner = format_banner(
            version="0.5.0",
            engine_url="http://127.0.0.1:8000",
            database="analytics-db",
            user_email="user@example.com",
            org_name="Acme",
        )
        assert "Acme/analytics-db" in banner
        assert "user@example.com" in banner
        assert "live query mode" in banner


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
        assert "/login" in names
        assert "/orgs" in names
        assert "/dbs" in names
        assert "/connect" in names
        assert "/import" in names
        assert "/exit" in names

    def test_no_completion_without_slash(self):
        results = self._complete("sel")
        assert results == []


# ── Auth & Sessions ─────────────────────────────────────────────────


class TestAuthManager:
    def test_session_expiry(self):
        s = Session("access", "refresh", "uid", "test@example.com", time.time() + 30)
        assert s.is_expired  # < 60s
        s2 = Session("access", "refresh", "uid", "test@example.com", time.time() + 300)
        assert not s2.is_expired

    @patch("morphy_cli.auth.httpx.Client")
    def test_login_success(self, mock_client_cls):
        mock_client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "access_token": "acc-123",
            "refresh_token": "ref-456",
            "expires_in": 3600,
            "user": {"id": "user-uuid", "email": "dev@test.com"},
        }
        mock_client.post.return_value = mock_resp
        mock_client_cls.return_value.__enter__.return_value = mock_client

        auth = AuthManager(supabase_url="http://127.0.0.1:54321", supabase_key="test-key")
        sess = auth.login("dev@test.com", "secret")
        assert sess.access_token == "acc-123"
        assert sess.email == "dev@test.com"

        status = auth.status()
        assert status["authenticated"] is True
        assert status["email"] == "dev@test.com"

    @patch("morphy_cli.auth.httpx.Client")
    def test_login_failure(self, mock_client_cls):
        mock_client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.status_code = 400
        mock_resp.text = "Invalid credentials"
        mock_resp.json.side_effect = ValueError
        mock_client.post.return_value = mock_resp
        mock_client_cls.return_value.__enter__.return_value = mock_client

        auth = AuthManager(supabase_url="http://127.0.0.1:54321", supabase_key="test-key")
        with pytest.raises(AuthError):
            auth.login("dev@test.com", "wrong")


# ── Control Plane ───────────────────────────────────────────────────


class TestControlClient:
    def test_list_orgs(self):
        auth = MagicMock()
        auth.get_valid_token.return_value = "token"
        auth.supabase_url = "http://127.0.0.1:54321"
        auth.supabase_key = "key"

        control = ControlClient(auth)
        with patch.object(control, "_request", return_value=[{"id": "org-1", "name": "Acme"}]):
            orgs = control.list_organizations()
            assert len(orgs) == 1
            assert orgs[0]["name"] == "Acme"


# ── Mock Client & Shell ─────────────────────────────────────────────


class MockClient:
    """Mock MorphyClient for testing shell interaction."""

    def __init__(self, *, is_live=False):
        self.database = UUID("12345678-1234-1234-1234-123456789abc") if is_live else None
        self.is_live = is_live
        self.base_url = "http://127.0.0.1:8000"

    def set_token_source(self, src):
        pass

    def set_database(self, db):
        self.database = db
        self.is_live = db is not None

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

    def connect_database(self, uri):
        return {"status": "connected", "tables": 4}

    def import_csv(self, data):
        return {"table": "records", "columns": ["a", "b"], "rows": 10}


def create_test_context(is_live=False):
    client = MockClient(is_live=is_live)
    auth = MagicMock()
    auth.status.return_value = {"authenticated": True, "email": "test@user.com", "supabase_url": "http://127.0.0.1:54321"}
    ctx = ShellContext(client, auth)
    return ctx


class TestHandleCommand:
    def test_help(self):
        ctx = create_test_context()
        result = _handle_command(ctx, "/help")
        assert "/schema" in result
        assert "/ask" in result
        assert "/login" in result

    def test_exit(self):
        ctx = create_test_context()
        assert _handle_command(ctx, "/exit") is None
        assert _handle_command(ctx, "/quit") is None

    def test_status(self):
        ctx = create_test_context()
        result = _handle_command(ctx, "/status")
        assert "MORPHY Session Status" in result
        assert "test@user.com" in result

    def test_logout(self):
        ctx = create_test_context()
        result = _handle_command(ctx, "/logout")
        assert "Signed out" in result

    def test_orgs(self):
        ctx = create_test_context()
        with patch.object(ctx.control, "list_organizations", return_value=[{"id": "o1", "name": "Org 1", "created_at": "today"}]):
            result = _handle_command(ctx, "/orgs")
            assert "Org 1" in result

    def test_use_org(self):
        ctx = create_test_context()
        with patch.object(ctx.control, "list_organizations", return_value=[{"id": "o1-uuid", "name": "Production"}]):
            result = _handle_command(ctx, "/use-org Production")
            assert "Production" in result
            assert ctx.active_org_id == "o1-uuid"

    def test_dbs(self):
        ctx = create_test_context()
        with patch.object(ctx.control, "list_databases", return_value=[{"id": "d1", "name": "Sales", "dialect": "postgres"}]):
            result = _handle_command(ctx, "/dbs")
            assert "Sales" in result

    def test_use_db_sample(self):
        ctx = create_test_context(is_live=True)
        result = _handle_command(ctx, "/use-db sample")
        assert "sample workspace" in result
        assert ctx.active_db_id is None

    def test_use_db_live(self):
        ctx = create_test_context()
        with patch.object(ctx.control, "list_databases", return_value=[{"id": "d1-uuid", "name": "Analytics", "dialect": "postgres"}]):
            result = _handle_command(ctx, "/use-db Analytics")
            assert "Analytics" in result

    def test_connect(self):
        ctx = create_test_context(is_live=True)
        ctx.active_db_id = "test-uuid"
        result = _handle_command(ctx, "/connect postgresql://readonly@localhost/db")
        assert "Connected successfully" in result

    def test_import_missing_file(self):
        ctx = create_test_context(is_live=True)
        ctx.active_db_id = "test-uuid"
        result = _handle_command(ctx, "/import nonexistent_file.csv")
        assert "File not found" in result

    def test_import_valid_file(self, tmp_path):
        csv_file = tmp_path / "test.csv"
        csv_file.write_text("a,b\n1,2\n3,4", encoding="utf-8")
        ctx = create_test_context(is_live=True)
        ctx.active_db_id = "test-uuid"
        result = _handle_command(ctx, f"/import {csv_file}")
        assert "Imported 10 rows" in result

    def test_profile(self):
        ctx = create_test_context()
        with patch.object(ctx.control, "get_profile", return_value={"username": "alice", "display_name": "Alice M", "id": "uid"}):
            result = _handle_command(ctx, "/profile")
            assert "alice" in result

    def test_json_and_export(self, tmp_path):
        ctx = create_test_context()
        _handle_command(ctx, "/sql SELECT 1")
        json_out = _handle_command(ctx, "/json")
        assert "11650" in json_out

        out_csv = tmp_path / "out.csv"
        export_out = _handle_command(ctx, f"/export {out_csv}")
        assert "Saved 1 row" in export_out
        assert out_csv.is_file()

    def test_ask_sample_mode(self):
        ctx = create_test_context(is_live=False)
        result = _handle_command(ctx, "/ask Total revenue")
        assert "SELECT sum(total)" in result
        assert "11650" in result

    def test_ask_live_mode_decline(self):
        ctx = create_test_context(is_live=True)
        with patch("builtins.input", return_value="n"):
            result = _handle_command(ctx, "/ask Total revenue")
        assert "not executed" in result

    def test_ask_live_mode_accept(self):
        ctx = create_test_context(is_live=True)
        with patch("builtins.input", return_value="y"):
            result = _handle_command(ctx, "/ask Total revenue")
        assert "11650" in result


# ── Client & Entrypoint ─────────────────────────────────────────────


class TestClient:
    def test_sample_client(self):
        c = MorphyClient("http://127.0.0.1:8000")
        assert c.prefix == "/api/sample"
        assert not c.is_live
        c.close()

    def test_remote_requires_https(self):
        with patch.dict("os.environ", {"MORPHY_ACCESS_TOKEN": "token"}):
            with pytest.raises(SystemExit):
                MorphyClient("http://remote.host:8000", UUID("12345678-1234-1234-1234-123456789abc"))


class TestMainEntrypoint:
    def test_help_flag(self):
        with pytest.raises(SystemExit) as exc:
            sys.argv = ["morphy", "--help"]
            from morphy_cli.main import main
            main()
        assert exc.value.code == 0
