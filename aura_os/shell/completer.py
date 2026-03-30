"""Tab-completion for the AURA OS interactive shell.

Provides a completer compatible with both ``prompt_toolkit`` and the
built-in ``readline`` module, so the same completion logic works
regardless of which backend is available.
"""

from typing import Dict, List, Optional, Sequence

# ──────────────────────────────────────────────────────────────────────
# Command tree (mirrors cli.py)
# ──────────────────────────────────────────────────────────────────────

# Mapping of command → list of sub-commands / flags
COMMAND_TREE: Dict[str, List[str]] = {
    "run":   ["--help"],
    "ai":    ["--model", "--max-tokens", "--help"],
    "env":   ["--json", "--help"],
    "pkg":   ["install", "remove", "list", "search", "info", "--help"],
    "sys":   ["--watch", "--help"],
    "shell": ["--help"],
    "exit":  [],
    "quit":  [],
    "help":  [],
}

TOP_LEVEL = sorted(COMMAND_TREE.keys())
GLOBAL_FLAGS = ["--version", "--verbose", "-v", "--help"]


# ──────────────────────────────────────────────────────────────────────
# Core completion logic
# ──────────────────────────────────────────────────────────────────────

def get_completions(text: str, line: str) -> List[str]:
    """Return a list of possible completions given *line* context.

    *text* is the token currently being completed.
    *line* is the entire line typed so far (for context).
    """
    parts = line.split()
    # If line ends with a space, user is starting a NEW token
    completing_new = line.endswith(" ")

    if not parts or (len(parts) == 1 and not completing_new):
        # Completing the top-level command
        return [c for c in TOP_LEVEL + GLOBAL_FLAGS if c.startswith(text)]

    command = parts[0]
    sub_options = COMMAND_TREE.get(command, [])

    if completing_new:
        # Show all options for the current command
        return sub_options
    else:
        # Filter sub-options that match current text
        return [s for s in sub_options if s.startswith(text)]


# ──────────────────────────────────────────────────────────────────────
# readline completer (fallback)
# ──────────────────────────────────────────────────────────────────────

class ReadlineCompleter:
    """A completer for Python's ``readline`` module."""

    def __init__(self):
        self._matches: List[str] = []

    def complete(self, text: str, state: int) -> Optional[str]:
        """Called by readline for each completion request."""
        if state == 0:
            import readline
            line = readline.get_line_buffer()
            self._matches = get_completions(text, line)
        try:
            return self._matches[state]
        except IndexError:
            return None


# ──────────────────────────────────────────────────────────────────────
# prompt_toolkit completer
# ──────────────────────────────────────────────────────────────────────

def make_prompt_toolkit_completer():
    """Return a ``prompt_toolkit`` Completer for the AURA shell.

    Returns *None* if ``prompt_toolkit`` is not installed.
    """
    try:
        from prompt_toolkit.completion import Completer, Completion
    except ImportError:
        return None

    class AuraCompleter(Completer):
        """prompt_toolkit completer using the shared AURA command tree."""

        def get_completions(self, document, complete_event):
            text = document.text_before_cursor
            word = document.get_word_before_cursor()
            for option in get_completions(word, text):
                yield Completion(option, start_position=-len(word))

    return AuraCompleter()
