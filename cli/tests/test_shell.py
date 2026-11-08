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

    @patch("morphy_cli.auth.httpx.Client")
    def test_refresh_success(self, mock_client_cls):
        mock_client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "access_token": "new-acc-789",
            "refresh_token": "new-ref-987",
            "expires_in": 3600,
            "user": {"id": "uid-1", "email": "dev@test.com"},
        }
        mock_client.post.return_value = mock_resp
        mock_client_cls.return_value.__enter__.return_value = mock_client

        auth = AuthManager(supabase_url="http://127.0.0.1:54321", supabase_key="test-key")
        auth.current_session = Session("old-acc", "old-ref", "uid-1", "dev@test.com", time.time() - 10)
        with patch.object(auth, "_store_refresh_token") as mock_store:
            new_sess = auth.refresh()
            assert new_sess.access_token == "new-acc-789"
            assert new_sess.refresh_token == "new-ref-987"
            assert auth.current_session.access_token == "new-acc-789"
            mock_store.assert_called_once_with("new-ref-987", new_sess)

    @patch("morphy_cli.auth.httpx.Client")
    def test_refresh_failure_clears_tokens(self, mock_client_cls):
        mock_client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_resp.text = "Invalid refresh token"
        mock_client.post.return_value = mock_resp
        mock_client_cls.return_value.__enter__.return_value = mock_client

        auth = AuthManager(supabase_url="http://127.0.0.1:54321", supabase_key="test-key")
        auth.current_session = Session("old-acc", "old-ref", "uid-1", "dev@test.com", time.time() - 10)
        with patch.object(auth, "_clear_stored_tokens") as mock_clear:
            with pytest.raises(AuthError) as exc:
                auth.refresh()
            assert "Session expired" in str(exc.value)
            assert auth.current_session is None
            mock_clear.assert_called_once()

    def test_get_valid_token_auto_refreshes_when_expired(self):
        auth = AuthManager(supabase_url="http://127.0.0.1:54321", supabase_key="test-key")
        # Session expired (expires_at in the past)
        auth.current_session = Session("expired-acc", "valid-ref", "uid-1", "dev@test.com", time.time() - 100)
        assert auth.current_session.is_expired

        with patch.object(auth, "refresh") as mock_refresh:
            def do_refresh():
                auth.current_session = Session("fresh-acc", "fresh-ref", "uid-1", "dev@test.com", time.time() + 3600)
                return auth.current_session
            mock_refresh.side_effect = do_refresh

            token = auth.get_valid_token()
            mock_refresh.assert_called_once()
            assert token == "fresh-acc"

    def test_get_valid_token_uses_unexpired_token(self):
        auth = AuthManager(supabase_url="http://127.0.0.1:54321", supabase_key="test-key")
        auth.current_session = Session("valid-acc", "valid-ref", "uid-1", "dev@test.com", time.time() + 1800)
        with patch.object(auth, "refresh") as mock_refresh:
            token = auth.get_valid_token()
            mock_refresh.assert_not_called()
            assert token == "valid-acc"

    def test_logout_clears_stored_credentials(self):
        auth = AuthManager(supabase_url="http://127.0.0.1:54321", supabase_key="test-key")
        auth.current_session = Session("acc", "ref", "uid-1", "dev@test.com", time.time() + 3600)
        with patch.object(auth, "_clear_stored_tokens") as mock_clear:
            auth.logout()
            assert auth.current_session is None
            mock_clear.assert_called_once()
            status = auth.status()
            assert status["authenticated"] is False


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

    def test_control_plane_dashboards_and_permissions(self):
        auth = MagicMock()
        auth.get_valid_token.return_value = "tok123"
        auth.supabase_key = "key123"
        auth.supabase_url = "https://example.supabase.co"
        control = ControlClient(auth)

        with patch.object(control, "_request") as mock_req:
            mock_req.return_value = [{"id": "d1", "title": "Board"}]
            boards = control.list_dashboards("o1", "db1")
            assert boards[0]["id"] == "d1"

            control.create_dashboard("o1", "db1", "Board 2", shared=True)
            mock_req.assert_called_with(
                "POST",
                "/rest/v1/dashboards",
                json_body={"org_id": "o1", "database_id": "db1", "title": "Board 2", "shared": True},
            )

            control.add_dashboard_panel("d1", "db1", "q1", 0)
            mock_req.assert_called_with(
                "POST",
                "/rest/v1/dashboard_panels",
                json_body={"dashboard_id": "d1", "database_id": "db1", "query_id": "q1", "position": 0},
            )

            control.save_permission("o1", "db1", role_id="r1", level="VIEW_ONLY")
            mock_req.assert_called_with(
                "POST",
                "/rest/v1/rpc/save_permission",
                json_body={"o": "o1", "d": "db1", "r": "r1", "person": None, "level": "VIEW_ONLY", "cols": {}, "rules": []},
            )

            control.revoke_permission("o1", "db1", role_id="r1")
            mock_req.assert_called_with(
                "POST",
                "/rest/v1/rpc/save_permission",
                json_body={"o": "o1", "d": "db1", "r": "r1", "person": None, "level": "NONE", "cols": {}, "rules": []},
            )


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

    def import_file(self, data, is_parquet=False):
        return {"table": "records", "columns": ["a", "b"], "rows": 10}

    def render_panel(self, dashboard_id, query_id):
        return {
            "columns": ["panel_metric", "val"],
            "rows": [["revenue", 999.0]],
            "row_count": 1,
            "sql": "SELECT 'revenue', 999.0",
            "elapsed_ms": 3.4,
        }


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

    def test_account_isolation_logout_clears_result(self, tmp_path):
        ctx = create_test_context()
        _handle_command(ctx, "/sql SELECT 1")
        assert ctx.last_result is not None

        # Log out
        res = _handle_command(ctx, "/logout")
        assert "Signed out" in res
        assert ctx.last_result is None

        # Verify /json does not expose previous account rows
        json_res = _handle_command(ctx, "/json")
        assert "No previous query result to display" in json_res
        assert "11650" not in json_res

        # Verify /export does not write previous account rows
        out_csv = tmp_path / "leaked.csv"
        export_res = _handle_command(ctx, f"/export {out_csv}")
        assert "No previous query result to export" in export_res
        assert not out_csv.exists()

    def test_workspace_isolation_clears_result(self):
        ctx = create_test_context()
        _handle_command(ctx, "/sql SELECT 1")
        assert ctx.last_result is not None

        # Switching org clears previous query result
        with patch.object(ctx.control, "list_organizations", return_value=[{"id": "o2", "name": "OtherOrg"}]):
            _handle_command(ctx, "/use-org OtherOrg")
        assert ctx.last_result is None

        # Re-populate and verify switching db clears previous query result
        _handle_command(ctx, "/sql SELECT 1")
        assert ctx.last_result is not None
        _handle_command(ctx, "/use-db sample")
        assert ctx.last_result is None

    def test_sql_visible_before_confirmation(self, capsys):
        ctx = create_test_context(is_live=True)
        printed_before_input = []

        def mock_input(prompt):
            captured = capsys.readouterr()
            printed_before_input.append(captured.out)
            return "n"

        with patch("builtins.input", side_effect=mock_input):
            result = _handle_command(ctx, "/ask Total revenue")

        assert len(printed_before_input) == 1
        assert "SELECT sum(total) FROM orders" in printed_before_input[0]
        assert "not executed" in result

    def test_profile_edit(self):
        ctx = create_test_context()
        with patch.object(ctx.control, "update_profile") as mock_update:
            res = _handle_command(ctx, "/profile edit Alice Wonderland")
            assert "Alice Wonderland" in res
            mock_update.assert_called_once_with("Alice Wonderland")

    def test_withdraw_invitation(self):
        ctx = create_test_context()
        with patch.object(ctx.control, "withdraw_invitation") as mock_withdraw:
            res = _handle_command(ctx, "/withdraw inv-456")
            assert "inv-456 withdrawn" in res
            mock_withdraw.assert_called_once_with("inv-456")

        with patch.object(ctx.control, "withdraw_invitation") as mock_withdraw:
            res2 = _handle_command(ctx, "/invite withdraw inv-789")
            assert "inv-789 withdrawn" in res2
            mock_withdraw.assert_called_once_with("inv-789")

    def test_saved_queries_and_dashboard(self, tmp_path):
        from morphy_cli.queries import QueryStore
        q_store = QueryStore(tmp_path / "test_queries.json")
        ctx = create_test_context()
        ctx.queries = q_store

        # Save query from last result
        _handle_command(ctx, "/sql SELECT 1")
        save_res = _handle_command(ctx, "/save-query my-test-query")
        assert "saved successfully" in save_res

        # List queries
        list_res = _handle_command(ctx, "/queries")
        assert "my-test-query" in list_res

        # Run query
        run_res = _handle_command(ctx, "/run-query my-test-query")
        assert "11650" in run_res

        # Dashboard shows query count and info
        dash_res = _handle_command(ctx, "/dashboard")
        assert "MORPHY DASHBOARD" in dash_res

        # Delete query
        del_res = _handle_command(ctx, "/delete-query my-test-query")
        assert "deleted" in del_res

    def test_dashboards_listing_and_rendering(self):
        ctx = create_test_context(is_live=True)
        ctx.active_org_id = "org-123"
        ctx.active_db_id = "db-456"

        board_id = "board-abc-123"
        query_id = "query-xyz-789"

        with patch.object(ctx.control, "list_dashboards") as mock_list, \
             patch.object(ctx.control, "get_dashboard") as mock_get, \
             patch.object(ctx.control, "create_dashboard") as mock_create, \
             patch.object(ctx.control, "add_dashboard_panel") as mock_add:

            mock_list.return_value = [
                {
                    "id": board_id,
                    "title": "Exec Overview",
                    "shared": True,
                    "dashboard_panels": [{"query_id": query_id, "position": 0}],
                    "updated_at": "2026-11-07T08:00:00",
                }
            ]
            mock_get.return_value = {
                "id": board_id,
                "title": "Exec Overview",
                "shared": True,
                "dashboard_panels": [{"query_id": query_id, "position": 0}],
            }
            mock_create.return_value = board_id

            # List dashboards
            list_res = _handle_command(ctx, "/dashboards")
            assert "Exec Overview" in list_res
            assert board_id in list_res

            # Create dashboard
            create_res = _handle_command(ctx, "/dashboard-create NewBoard shared")
            assert "NewBoard" in create_res
            mock_create.assert_called_once_with("org-123", "db-456", "NewBoard", shared=True)

            # Add panel
            add_res = _handle_command(ctx, f"/dashboard-add {board_id} {query_id} 1")
            assert "added to dashboard" in add_res
            mock_add.assert_called_once_with(board_id, "db-456", query_id, position=1)

            # Render dashboard
            render_res = _handle_command(ctx, f"/dashboard render {board_id}")
            assert "DASHBOARD: Exec Overview" in render_res
            assert "revenue" in render_res
            assert "999" in render_res
            assert ctx.last_result["rows"][0][1] == 999.0

    def test_permissions_and_revocation(self):
        ctx = create_test_context(is_live=True)
        ctx.active_org_id = "org-123"
        ctx.active_db_id = "db-456"

        with patch.object(ctx.control, "effective_permission") as mock_perm, \
             patch.object(ctx.control, "list_roles") as mock_roles, \
             patch.object(ctx.control, "revoke_permission") as mock_revoke:

            mock_perm.return_value = {
                "mode": "QUERY_ONLY",
                "table_columns": {"orders": ["id", "amount"]},
                "row_rules": [{"table": "orders", "column": "region", "op": "eq", "value": "APAC"}],
            }
            mock_roles.return_value = [{"id": "role-admin-1", "name": "ADMIN"}]

            # Check permissions
            perm_res = _handle_command(ctx, "/permissions")
            assert "Mode: QUERY_ONLY" in perm_res
            assert "orders: id, amount" in perm_res
            assert "orders.region eq APAC" in perm_res

            # Revoke role permission
            rev_res = _handle_command(ctx, "/perm-revoke ADMIN")
            assert "Revoked permission for role 'ADMIN'" in rev_res
            mock_revoke.assert_called_once_with("org-123", "db-456", role_id="role-admin-1")

    def test_ask_empty_shows_starter_questions(self):
        ctx = create_test_context(is_live=True)
        with patch.object(ctx.client, "schema", return_value={"tables": {"records": ["a", "b"]}, "question_examples": ["How many records?", "Count by city"]}):
            res = _handle_command(ctx, "/ask")
            assert "Usage: /ask <question>" in res
            assert "Starter questions to try:" in res
            assert "How many records?" in res
            assert "Count by city" in res

    def test_ask_overview_prompt(self):
        ctx = create_test_context(is_live=True)
        with patch.object(ctx.client, "schema", return_value={"tables": {"orders": {"id": "int4", "total": "numeric"}}, "question_examples": ["Top 5 by total"]}):
            res = _handle_command(ctx, "/ask what is this data about?")
            assert "Dataset Overview" in res
            assert "orders: id, total" in res
            assert "Top 5 by total" in res
            assert 'SELECT COUNT(*) AS row_count FROM "orders"' in res

    def test_examples_with_question_examples(self):
        ctx = create_test_context(is_live=True)
        with patch.object(ctx.client, "schema", return_value={"tables": {"records": ["col1"]}, "question_examples": ["Count records by dept"]}):
            res = _handle_command(ctx, "/examples")
            assert "Count records by dept" in res

    def test_examples_suggested_queries_fallback(self):
        ctx = create_test_context(is_live=True)
        with patch.object(ctx.client, "schema", return_value={"tables": {"users": ["id", "name", "email"]}}):
            res = _handle_command(ctx, "/examples")
            assert "Suggested starter queries for permitted tables:" in res
            assert 'SELECT COUNT(*) AS row_count FROM "users"' in res
            assert 'SELECT "id", "name", "email" FROM "users" LIMIT 10' in res

    def test_ask_interactive_clarification_choice_number(self):
        ctx = create_test_context(is_live=True)
        clarification_response = {
            "kind": "clarification",
            "message": "Several permitted columns match that metric. Which column should MORPHY use?",
            "choices": [
                {"column": "annual_salary", "question": "Who has the highest annual_salary?"},
                {"column": "base_salary", "question": "Who has the highest base_salary?"},
            ],
        }
        draft_response = {
            "sql": "SELECT first_name, annual_salary FROM records ORDER BY annual_salary DESC LIMIT 1",
            "provider": "morphy-template",
            "requires_execution": True,
        }

        with patch.object(ctx.client, "generate") as mock_gen, \
             patch("builtins.input", side_effect=["1", "y"]) as mock_input:
            mock_gen.side_effect = [clarification_response, draft_response]
            res = _handle_command(ctx, "/ask Who has the highest salary?")
            assert mock_gen.call_count == 2
            mock_gen.assert_any_call("Who has the highest salary?", include_clarification=True)
            mock_gen.assert_any_call("Who has the highest annual_salary?", require_template=True)
            assert "11650" in res

    def test_ask_interactive_clarification_choice_column(self):
        ctx = create_test_context(is_live=True)
        clarification_response = {
            "kind": "clarification",
            "message": "Several permitted columns match that metric. Which column should MORPHY use?",
            "choices": [
                {"column": "annual_salary", "question": "Who has the highest annual_salary?"},
                {"column": "base_salary", "question": "Who has the highest base_salary?"},
            ],
        }
        draft_response = {
            "sql": "SELECT first_name, base_salary FROM records ORDER BY base_salary DESC LIMIT 1",
            "provider": "morphy-template",
            "requires_execution": True,
        }

        with patch.object(ctx.client, "generate") as mock_gen, \
             patch("builtins.input", side_effect=["base_salary", "n"]):
            mock_gen.side_effect = [clarification_response, draft_response]
            res = _handle_command(ctx, "/ask Who has the highest salary?")
            assert mock_gen.call_count == 2
            mock_gen.assert_any_call("Who has the highest base_salary?", require_template=True)
            assert "not executed" in res

    def test_ask_interactive_clarification_cancelled(self):
        ctx = create_test_context(is_live=True)
        clarification_response = {
            "kind": "clarification",
            "message": "Several permitted columns match that metric.",
            "choices": [{"column": "col_a", "question": "Ask col_a?"}],
        }
        with patch.object(ctx.client, "generate", return_value=clarification_response), \
             patch("builtins.input", return_value=""):
            res = _handle_command(ctx, "/ask ambiguous question")
            assert "(clarification cancelled)" in res

    def test_import_parquet_file(self, tmp_path):
        parquet_file = tmp_path / "test.parquet"
        parquet_file.write_bytes(b"PAR1dummydata")
        ctx = create_test_context(is_live=True)
        ctx.active_db_id = "test-uuid"
        with patch.object(ctx.client, "import_file", return_value={"table": "records", "columns": ["x", "y"], "rows": 42}) as mock_import:
            res = _handle_command(ctx, f"/import {parquet_file}")
            assert "Imported 42 rows from Parquet into 'records'" in res
            assert "x, y" in res
            mock_import.assert_called_once_with(b"PAR1dummydata", is_parquet=True)

    def test_import_parquet_oversized(self, tmp_path):
        large_file = tmp_path / "large.parquet"
        large_file.write_bytes(b"x" * (1_048_576 + 10))
        ctx = create_test_context(is_live=True)
        ctx.active_db_id = "test-uuid"
        res = _handle_command(ctx, f"/import {large_file}")
        assert "Choose a CSV or Parquet file up to 1 MB" in res

    def test_account_switching_isolation(self):
        ctx = create_test_context()
        ctx.last_result = {"columns": ["secret"], "rows": [["data"]]}
        ctx.active_org_id = "old-org"
        ctx.active_db_id = "old-db"

        with patch.object(ctx.auth, "login") as mock_login, \
             patch("getpass.getpass", return_value="pass123"):
            mock_login.return_value = MagicMock(email="other@user.com")
            res = _handle_command(ctx, "/login other@user.com", session=MagicMock())
            assert "signed in as other@user.com" in res
            assert ctx.last_result is None
            assert ctx.active_org_id is None
            assert ctx.active_db_id is None


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

    def test_sql_success_exit_code(self):
        with patch("sys.argv", ["morphy", "--sql", "SELECT 1"]):
            with patch("morphy_cli.client.MorphyClient.query", return_value={"columns": ["c"], "rows": [[1]], "row_count": 1, "elapsed_ms": 1.0}):
                from morphy_cli.main import main
                main()

    def test_sql_engine_error_exit_code(self):
        with patch("sys.argv", ["morphy", "--sql", "SELECT 1"]):
            with patch("morphy_cli.client.MorphyClient.query", side_effect=EngineError(403, "denied")):
                from morphy_cli.main import main
                with pytest.raises(SystemExit) as exc:
                    main()
                assert exc.value.code == 1

    def test_sql_network_error_exit_code(self):
        import httpx
        with patch("sys.argv", ["morphy", "--sql", "SELECT 1"]):
            with patch("morphy_cli.client.MorphyClient.query", side_effect=httpx.ConnectError("refused")):
                from morphy_cli.main import main
                with pytest.raises(SystemExit) as exc:
                    main()
                assert exc.value.code == 2

    def test_sql_cancellation_exit_code(self):
        with patch("sys.argv", ["morphy", "--sql", "SELECT 1"]):
            with patch("morphy_cli.client.MorphyClient.query", side_effect=KeyboardInterrupt):
                from morphy_cli.main import main
                with pytest.raises(SystemExit) as exc:
                    main()
                assert exc.value.code == 130
