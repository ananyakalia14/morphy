"""Interactive prompt-toolkit REPL for MORPHY with auth, org/database selection, and full CLI suite."""

import getpass
import os
from pathlib import Path
import sys
from typing import Any, Optional
from uuid import UUID

from prompt_toolkit import PromptSession
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.key_binding import KeyBindings

from .auth import AuthError, AuthManager
from .client import EngineError, MorphyClient
from .completer import SlashCompleter
from .control import ControlClient, ControlPlaneError
from .formatting import (
    format_banner,
    format_csv,
    format_examples,
    format_generation,
    format_json,
    format_records_table,
    format_schema,
    format_table,
)

import httpx

_HELP_TEXT = """\
Available commands:
  Authentication & Session:
    /login                     Sign in with email and password
    /logout                    Sign out and remove saved session
    /status                    Display session, active org and database context
    /profile                   View or claim your user profile

  Organization & Databases:
    /orgs                      List your organizations
    /use-org <id|name>         Switch active organization
    /dbs                       List target databases in the active organization
    /use-db <id|name|sample>   Switch target database (or switch back to sample)

  Database Administration:
    /connect <postgres_uri>    Connect target PostgreSQL database (Admin only)
    /import <path_to_csv>      Import UTF-8 CSV up to 1 MB (Admin only)

  Team & Invitations:
    /members                   List members of active organization
    /invites                   List pending invitations
    /invite <username>         Invite a user to active organization
    /accept <invitation_id>    Accept a pending invitation

  Queries & Generation:
    /schema                    Display permitted tables and columns
    /examples                  List curated example questions
    /ask <question>            Generate governed SQL from natural language
    /sql <SELECT ...>          Execute read-only SQL query
    /json                      Show last query result as JSON
    /export <file.csv>         Export last query result to a CSV file

  Session Control:
    /exit or /quit             Leave the session

Tips:
  • Tab completes slash commands.
  • Ctrl+C cancels the current input line; Ctrl+D exits.
  • In live mode, generated SQL is always displayed before confirmation."""


class ShellContext:
    """Holds state for the interactive shell session."""

    def __init__(self, client: MorphyClient, auth_manager: AuthManager):
        self.client = client
        self.auth = auth_manager
        self.control = ControlClient(auth_manager)
        self.active_org_id: Optional[str] = None
        self.active_org_name: Optional[str] = None
        self.active_db_id: Optional[str] = str(client.database) if client.database else None
        self.active_db_name: Optional[str] = None
        self.last_result: Optional[dict[str, Any]] = None

    def get_prompt(self) -> HTML:
        if self.active_db_id:
            db_label = self.active_db_name or self.active_db_id[:8]
            if self.active_org_name:
                context = f"{self.active_org_name}/{db_label}"
            else:
                context = db_label
            return HTML(f"<ansicyan>morphy</ansicyan> [<ansigreen>{context}</ansigreen>] &gt; ")
        return HTML("<ansicyan>morphy</ansicyan> (<ansiyellow>sample</ansiyellow>) &gt; ")


def _execute_sql(ctx: ShellContext, sql: str) -> str:
    """Execute SQL via the engine client and cache result."""
    result = ctx.client.query(sql)
    ctx.last_result = result
    return format_table(
        result["columns"], result["rows"], result["row_count"], result["elapsed_ms"]
    )


def _handle_command(ctx: ShellContext, line: str, session: Optional[PromptSession] = None) -> Optional[str]:
    """Dispatch a single command line."""
    cmd = line.strip()
    if cmd in ("/exit", "/quit"):
        return None

    if cmd == "/help":
        return _HELP_TEXT

    # ── Status ──────────────────────────────────────────────────────────
    if cmd == "/status":
        auth_status = ctx.auth.status()
        lines = ["=== MORPHY Session Status ==="]
        lines.append(f"Engine URL:       {ctx.client.base_url}")
        lines.append(f"Supabase URL:     {auth_status.get('supabase_url', '(not configured)')}")
        lines.append(f"Authenticated:    {auth_status.get('authenticated', False)}")
        if auth_status.get("email"):
            lines.append(f"User:             {auth_status['email']}")
        if auth_status.get("user_id"):
            lines.append(f"User ID:          {auth_status['user_id']}")
        if auth_status.get("expires_in_seconds") is not None:
            lines.append(f"Token TTL:        {auth_status['expires_in_seconds']}s")
        lines.append(f"Active Org:       {ctx.active_org_name or '(none)'} ({ctx.active_org_id or 'none'})")
        lines.append(f"Active Database:  {ctx.active_db_name or '(none)'} ({ctx.active_db_id or 'sample mode'})")
        return "\n".join(lines)

    # ── Login ───────────────────────────────────────────────────────────
    if cmd.startswith("/login"):
        parts = cmd.split(maxsplit=2)
        email = parts[1] if len(parts) > 1 else ""
        if not email and session:
            try:
                email = session.prompt("Email: ").strip()
            except (KeyboardInterrupt, EOFError):
                return "Login cancelled."

        if not email:
            return "Usage: /login <email>"

        try:
            password = getpass.getpass("Password: ")
        except (KeyboardInterrupt, EOFError):
            return "Login cancelled."

        try:
            sess = ctx.auth.login(email, password)
            ctx.client.set_token_source(lambda: ctx.auth.get_valid_token())
            return f"Successfully signed in as {sess.email}."
        except AuthError as err:
            return f"Authentication failed: {err}"

    # ── Logout ──────────────────────────────────────────────────────────
    if cmd == "/logout":
        ctx.auth.logout()
        ctx.client.set_token_source(None)
        ctx.active_org_id = None
        ctx.active_org_name = None
        ctx.active_db_id = None
        ctx.active_db_name = None
        ctx.client.set_database(None)
        return "Signed out. Saved credentials cleared."

    # ── Organizations ───────────────────────────────────────────────────
    if cmd == "/orgs":
        try:
            orgs = ctx.control.list_organizations()
            if not orgs:
                return "No organizations found. Create one with /org-create <name> or via the website."
            return format_records_table(["ID", "Name", "Created"], orgs, ["id", "name", "created_at"])
        except (AuthError, ControlPlaneError) as err:
            return f"Error listing organizations: {err}"

    if cmd.startswith("/use-org"):
        parts = cmd.split(maxsplit=1)
        if len(parts) < 2:
            return "Usage: /use-org <id|name>"
        query = parts[1].strip()
        try:
            orgs = ctx.control.list_organizations()
            matched = [o for o in orgs if o["id"].startswith(query) or o["name"].lower() == query.lower()]
            if not matched:
                return f"Organization '{query}' not found. Use /orgs to view available organizations."
            org = matched[0]
            ctx.active_org_id = org["id"]
            ctx.active_org_name = org["name"]
            # Reset active db when switching org
            ctx.active_db_id = None
            ctx.active_db_name = None
            ctx.client.set_database(None)
            return f"Active organization set to: {ctx.active_org_name} ({ctx.active_org_id})"
        except (AuthError, ControlPlaneError) as err:
            return f"Error selecting organization: {err}"

    # ── Target Databases ────────────────────────────────────────────────
    if cmd == "/dbs":
        try:
            dbs = ctx.control.list_databases(ctx.active_org_id)
            if not dbs:
                return "No target databases found in current context."
            return format_records_table(["ID", "Name", "Dialect"], dbs, ["id", "name", "dialect"])
        except (AuthError, ControlPlaneError) as err:
            return f"Error listing databases: {err}"

    if cmd.startswith("/use-db"):
        parts = cmd.split(maxsplit=1)
        if len(parts) < 2:
            return "Usage: /use-db <id|name|sample>"
        target = parts[1].strip()
        if target.lower() == "sample":
            ctx.active_db_id = None
            ctx.active_db_name = None
            ctx.client.set_database(None)
            return "Switched to sample workspace (synthetic commerce dataset)."

        try:
            dbs = ctx.control.list_databases(ctx.active_org_id)
            matched = [d for d in dbs if d["id"].startswith(target) or d["name"].lower() == target.lower()]
            if not matched:
                # Direct UUID fallback
                try:
                    uuid_val = UUID(target)
                    ctx.active_db_id = str(uuid_val)
                    ctx.active_db_name = target[:8]
                    ctx.client.set_database(uuid_val)
                    return f"Active database set to {ctx.active_db_id}."
                except ValueError:
                    return f"Database '{target}' not found. Run /dbs to view available databases."
            db_row = matched[0]
            ctx.active_db_id = str(db_row["id"])
            ctx.active_db_name = db_row["name"]
            try:
                ctx.client.set_database(UUID(ctx.active_db_id))
            except ValueError:
                ctx.client.set_database(ctx.active_db_id)
            return f"Active database set to: {ctx.active_db_name} [{db_row.get('dialect', 'db')}] ({ctx.active_db_id})"
        except (AuthError, ControlPlaneError) as err:
            return f"Error setting database: {err}"

    # ── Connections & CSV Import ─────────────────────────────────────────
    if cmd.startswith("/connect"):
        parts = cmd.split(maxsplit=1)
        if len(parts) < 2:
            return "Usage: /connect <postgres_uri>"
        uri = parts[1].strip()
        if not ctx.active_db_id:
            return "Select a database first with /use-db <id> before configuring a connection."
        try:
            res = ctx.client.connect_database(uri)
            return f"Connected successfully. Reflected {res.get('tables', 0)} tables."
        except EngineError as err:
            return f"Connection error: {err.detail}"

    if cmd.startswith("/import"):
        parts = cmd.split(maxsplit=1)
        if len(parts) < 2:
            return "Usage: /import <path_to_csv_file>"
        csv_path = Path(parts[1].strip().strip('"').strip("'"))
        if not csv_path.is_file():
            return f"File not found: {csv_path}"
        if not ctx.active_db_id:
            return "Select a database first with /use-db <id> before importing data."
        try:
            data = csv_path.read_bytes()
            res = ctx.client.import_csv(data)
            return f"Imported {res.get('rows', 0)} rows into '{res.get('table', 'records')}'. Columns: {', '.join(res.get('columns', []))}"
        except EngineError as err:
            return f"Import error: {err.detail}"
        except Exception as err:
            return f"Failed to read file: {err}"

    # ── Profile & Team Management ───────────────────────────────────────
    if cmd == "/profile":
        try:
            profile = ctx.control.get_profile()
            if not profile:
                return "No profile claimed yet. Claim with /profile claim <username> <display_name>"
            return f"Username:     {profile.get('username')}\nDisplay Name: {profile.get('display_name')}\nUser ID:      {profile.get('id')}"
        except (AuthError, ControlPlaneError) as err:
            return f"Profile error: {err}"

    if cmd.startswith("/profile claim"):
        parts = cmd.split(maxsplit=3)
        if len(parts) < 4:
            return "Usage: /profile claim <username> <display_name>"
        try:
            ctx.control.claim_profile(parts[2], parts[3])
            return "Profile successfully claimed!"
        except (AuthError, ControlPlaneError) as err:
            return f"Error claiming profile: {err}"

    if cmd == "/members":
        if not ctx.active_org_id:
            return "Select an active organization first with /use-org <id>"
        try:
            members = ctx.control.list_members(ctx.active_org_id)
            if not members:
                return "No members found."
            return format_records_table(["User ID", "Username", "Role ID"], members, ["user_id", "username", "role_id"])
        except (AuthError, ControlPlaneError) as err:
            return f"Error listing members: {err}"

    if cmd == "/invites":
        try:
            invites = ctx.control.list_invitations()
            if not invites:
                return "No pending invitations."
            return format_records_table(["Invitation ID", "Organization", "Status"], invites, ["id", "organization_name", "status"])
        except (AuthError, ControlPlaneError) as err:
            return f"Error listing invitations: {err}"

    if cmd.startswith("/invite"):
        parts = cmd.split(maxsplit=1)
        if len(parts) < 2 or not ctx.active_org_id:
            return "Usage: /invite <username> (with an active organization set)"
        prefix = parts[1].strip()
        try:
            people = ctx.control.find_people(prefix)
            if not people:
                return f"No users found matching '{prefix}'."
            target_user = people[0]
            roles = ctx.control.list_roles(ctx.active_org_id)
            viewer_role = next((r["id"] for r in roles if r["name"] == "VIEWER"), roles[0]["id"] if roles else None)
            if not viewer_role:
                return "No suitable role found to invite user."
            ctx.control.invite_person(ctx.active_org_id, target_user["id"], viewer_role)
            return f"Invitation sent to {target_user['username']}."
        except (AuthError, ControlPlaneError) as err:
            return f"Error sending invitation: {err}"

    if cmd.startswith("/accept"):
        parts = cmd.split(maxsplit=1)
        if len(parts) < 2:
            return "Usage: /accept <invitation_id>"
        inv_id = parts[1].strip()
        try:
            ctx.control.accept_invitation(inv_id)
            return f"Invitation {inv_id} accepted!"
        except (AuthError, ControlPlaneError) as err:
            return f"Error accepting invitation: {err}"

    # ── Export & JSON ───────────────────────────────────────────────────
    if cmd == "/json":
        if not ctx.last_result:
            return "No previous query result to display."
        return format_json(ctx.last_result)

    if cmd.startswith("/export"):
        parts = cmd.split(maxsplit=1)
        if len(parts) < 2:
            return "Usage: /export <filename.csv>"
        if not ctx.last_result:
            return "No previous query result to export."
        out_path = Path(parts[1].strip())
        csv_content = format_csv(ctx.last_result["columns"], ctx.last_result["rows"])
        try:
            out_path.write_text(csv_content, encoding="utf-8")
            return f"Saved {ctx.last_result.get('row_count', 0)} rows to {out_path}."
        except Exception as err:
            return f"Failed to write CSV: {err}"

    # ── Schema & Examples ───────────────────────────────────────────────
    if cmd in ("/schema", "/examples"):
        metadata = ctx.client.schema()
        if cmd == "/schema":
            return format_schema(metadata.get("tables", {}))
        return format_examples(metadata.get("examples", ["Use /ask followed by your question."]))

    # ── Natural Language /ask ───────────────────────────────────────────
    if cmd.startswith("/ask "):
        question = cmd[5:].strip()
        if not question:
            return "Usage: /ask <question>"
        generated = ctx.client.generate(question)
        output = format_generation(generated)

        # In sample mode: execute immediately
        if not ctx.client.is_live:
            res_table = _execute_sql(ctx, generated["sql"])
            return output + "\n\n" + res_table

        # In live mode: Always display generated SQL first, then request confirmation
        print(output)
        try:
            confirm = input("Execute this SQL? [y/N] ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            return "Cancelled."
        if confirm == "y":
            return _execute_sql(ctx, generated["sql"])
        return "(not executed)"

    # ── Direct SQL Execution ────────────────────────────────────────────
    if cmd.startswith("/sql "):
        sql = cmd[5:].strip()
        if not sql:
            return "Usage: /sql <SELECT ...>"
        return _execute_sql(ctx, sql)

    return "Unknown command. Use /sql followed by a SELECT query, or /help."


def run_repl(client: MorphyClient, auth_manager: Optional[AuthManager] = None):
    """Launch the interactive prompt-toolkit REPL."""
    auth = auth_manager or AuthManager()
    # Try restoring session silently
    auth.restore_session()
    client.set_token_source(lambda: auth.get_valid_token())

    ctx = ShellContext(client, auth)
    auth_status = auth.status()

    banner = format_banner(
        version="0.5.0",
        engine_url=client.base_url,
        database=client.database,
        user_email=auth_status.get("email"),
        org_name=ctx.active_org_name,
    )
    print(banner)

    bindings = KeyBindings()

    @bindings.add("c-c")
    def _(event):
        """Ctrl+C clears current input line without exiting REPL."""
        event.current_buffer.reset()
        print()

    session: PromptSession = PromptSession(
        message=ctx.get_prompt,
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
            output = _handle_command(ctx, line, session)
        except EngineError as error:
            print(f"Error: {error.detail}")
            continue
        except httpx.HTTPError as error:
            print(f"Network error: {error}")
            continue

        if output is None:
            break
        print(output)
