"""Slash-command completion for the MORPHY interactive shell."""

from prompt_toolkit.completion import Completer, Completion


# Commands available in the interactive shell.
_ALL_COMMANDS = [
    ("/help", "Show available commands"),
    ("/schema", "Display the permitted database schema"),
    ("/examples", "List starter questions or suggested queries"),
    ("/ask", "Generate SQL from natural language (supports clarification & overview)"),
    ("/sql", "Execute a read-only SQL query"),
    ("/login", "Sign in with email and password"),
    ("/logout", "Sign out and clear saved credentials"),
    ("/status", "Display authentication, active org and database status"),
    ("/orgs", "List your organizations"),
    ("/use-org", "Switch active organization context (/use-org <id>)"),
    ("/dbs", "List databases in active organization"),
    ("/use-db", "Switch active target database context (/use-db <id|sample>)"),
    ("/connect", "Save and verify PostgreSQL connection (/connect <uri>)"),
    ("/import", "Import UTF-8 CSV or Parquet into active database (/import <file>)"),
    ("/profile", "View or claim your user profile"),
    ("/members", "List members of active organization"),
    ("/invites", "List pending invitations"),
    ("/invite", "Invite a user to active organization (/invite <username>)"),
    ("/accept", "Accept an organization invitation (/accept <id>)"),
    ("/withdraw", "Withdraw a pending invitation (/withdraw <id>)"),
    ("/save-query", "Save current or specified SQL query (/save-query <name> [sql])"),
    ("/queries", "List saved queries"),
    ("/run-query", "Run a saved query by name (/run-query <name>)"),
    ("/delete-query", "Delete a saved query (/delete-query <name>)"),
    ("/dashboards", "List saved dashboards"),
    ("/dashboard", "Display summary dashboard or render a saved dashboard (/dashboard [render <id>])"),
    ("/dashboard-create", "Create a saved dashboard (/dashboard-create <title> [shared])"),
    ("/dashboard-add", "Add a query panel to dashboard (/dashboard-add <dash_id> <query_id>)"),
    ("/permissions", "Show effective permissions on active database"),
    ("/perm-revoke", "Revoke permissions for a role or user (/perm-revoke <role|user>)"),
    ("/export", "Export last query result to CSV file (/export <file.csv>)"),
    ("/json", "Display last query result formatted as JSON"),
    ("/exit", "Leave the session"),
    ("/quit", "Leave the session"),
]


class SlashCompleter(Completer):
    """Tab-complete slash commands in the MORPHY REPL."""

    def __init__(self, *, is_live: bool = False):
        self._commands = list(_ALL_COMMANDS)

    def get_completions(self, document, complete_event):
        text = document.text_before_cursor.lstrip()
        # Only complete at the beginning of the line and when starting with '/'.
        if document.cursor_position != len(document.text_before_cursor.lstrip()):
            return
        if not text.startswith("/"):
            return
        for name, description in self._commands:
            if name.startswith(text):
                yield Completion(
                    name,
                    start_position=-len(text),
                    display=name,
                    display_meta=description,
                )
