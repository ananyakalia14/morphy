"""Slash-command completion for the MORPHY interactive shell."""

from prompt_toolkit.completion import Completer, Completion


# Commands available in all modes.
_BASE_COMMANDS = [
    ("/help", "Show available commands"),
    ("/schema", "Display the permitted database schema"),
    ("/examples", "List curated example questions"),
    ("/ask", "Generate SQL from a natural-language question"),
    ("/sql", "Execute a read-only SQL query"),
    ("/exit", "Leave the session"),
    ("/quit", "Leave the session"),
]


class SlashCompleter(Completer):
    """Tab-complete slash commands in the MORPHY REPL."""

    def __init__(self, *, is_live: bool = False):
        self._commands = list(_BASE_COMMANDS)

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
