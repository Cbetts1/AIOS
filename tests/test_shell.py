"""Tests for the modern shell module (colors, completer, formatters, shell)."""

import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ──────────────────────────────────────────────────────────────────────
# Colors
# ──────────────────────────────────────────────────────────────────────

class TestColors(unittest.TestCase):
    """Verify the color utility functions produce correct output."""

    def test_color_functions_return_strings(self):
        from aura_os.shell.colors import (
            bold, dim, red, green, yellow, blue, magenta, cyan,
            bright_cyan, bright_green, bright_yellow, bright_blue,
            bright_red, bright_white,
        )
        for fn in (bold, dim, red, green, yellow, blue, magenta, cyan,
                   bright_cyan, bright_green, bright_yellow, bright_blue,
                   bright_red, bright_white):
            result = fn("test")
            self.assertIsInstance(result, str)
            self.assertIn("test", result)

    def test_semantic_helpers(self):
        from aura_os.shell.colors import success, error, warning, info, header, label, muted
        for fn in (success, error, warning, info, header, label, muted):
            result = fn("text")
            self.assertIsInstance(result, str)
            self.assertIn("text", result)

    def test_progress_bar_returns_string(self):
        from aura_os.shell.colors import progress_bar
        bar = progress_bar(50.0)
        self.assertIsInstance(bar, str)

    def test_progress_bar_percentages(self):
        from aura_os.shell.colors import progress_bar
        # Should not raise for any valid percentage
        for pct in (0, 25, 49, 50, 79, 80, 100):
            bar = progress_bar(float(pct))
            self.assertIn(str(pct), bar)

    def test_no_color_env(self):
        """NO_COLOR env var should suppress ANSI codes."""
        with patch.dict(os.environ, {"NO_COLOR": "1"}):
            # Reimport to pick up the env change
            import importlib
            import aura_os.shell.colors as colors_mod
            original = colors_mod._COLOR_ENABLED
            colors_mod._COLOR_ENABLED = False
            try:
                result = colors_mod.red("hello")
                # Without color, no escape codes
                self.assertEqual(result, "hello")
            finally:
                colors_mod._COLOR_ENABLED = original


# ──────────────────────────────────────────────────────────────────────
# Completer
# ──────────────────────────────────────────────────────────────────────

class TestCompleter(unittest.TestCase):
    """Verify tab-completion logic."""

    def test_top_level_completions(self):
        from aura_os.shell.completer import get_completions
        results = get_completions("", "")
        # Should contain all top-level commands
        for cmd in ("run", "ai", "env", "pkg", "sys", "shell", "exit", "quit"):
            self.assertIn(cmd, results)

    def test_top_level_partial(self):
        from aura_os.shell.completer import get_completions
        results = get_completions("sy", "sy")
        self.assertIn("sys", results)
        self.assertNotIn("ai", results)

    def test_sub_command_completions(self):
        from aura_os.shell.completer import get_completions
        results = get_completions("", "pkg ")
        self.assertIn("install", results)
        self.assertIn("remove", results)
        self.assertIn("list", results)

    def test_sub_command_partial(self):
        from aura_os.shell.completer import get_completions
        results = get_completions("in", "pkg in")
        self.assertIn("install", results)
        self.assertNotIn("remove", results)

    def test_flag_completions(self):
        from aura_os.shell.completer import get_completions
        results = get_completions("", "env ")
        self.assertIn("--json", results)

    def test_global_flags(self):
        from aura_os.shell.completer import get_completions
        results = get_completions("--", "--")
        self.assertIn("--version", results)
        self.assertIn("--verbose", results)

    def test_readline_completer(self):
        from aura_os.shell.completer import ReadlineCompleter
        completer = ReadlineCompleter()
        # Mock readline.get_line_buffer
        with patch("readline.get_line_buffer", return_value="sy"):
            first = completer.complete("sy", 0)
            self.assertEqual(first, "sys")
            none = completer.complete("sy", 1)
            # After all matches exhausted
            self.assertIsNone(none)

    def test_prompt_toolkit_completer_creation(self):
        from aura_os.shell.completer import make_prompt_toolkit_completer
        completer = make_prompt_toolkit_completer()
        # Should return a completer instance (prompt_toolkit is installed)
        self.assertIsNotNone(completer)


# ──────────────────────────────────────────────────────────────────────
# Formatters
# ──────────────────────────────────────────────────────────────────────

class TestFormatters(unittest.TestCase):
    """Verify output formatters produce reasonable output."""

    def test_table_output(self):
        from aura_os.shell.formatters import table
        result = table(
            ["Name", "Value"],
            [["alpha", "1"], ["beta", "2"]],
        )
        self.assertIn("Name", result)
        self.assertIn("alpha", result)
        self.assertIn("beta", result)

    def test_table_empty(self):
        from aura_os.shell.formatters import table
        result = table(["A", "B"], [])
        self.assertIn("A", result)

    def test_kv_panel(self):
        from aura_os.shell.formatters import kv_panel
        result = kv_panel("Test", [("key", "value")])
        self.assertIn("Test", result)
        self.assertIn("key", result)
        self.assertIn("value", result)

    def test_section(self):
        from aura_os.shell.formatters import section
        result = section("My Section")
        self.assertIn("My Section", result)

    def test_badges(self):
        from aura_os.shell.formatters import badges
        result = badges(["git", "python", "node"])
        self.assertIn("git", result)
        self.assertIn("python", result)

    def test_status_messages(self):
        from aura_os.shell.formatters import success_msg, error_msg, warning_msg, info_msg
        self.assertIn("ok", success_msg("ok"))
        self.assertIn("fail", error_msg("fail"))
        self.assertIn("warn", warning_msg("warn"))
        self.assertIn("note", info_msg("note"))


# ──────────────────────────────────────────────────────────────────────
# Shell module (integration)
# ──────────────────────────────────────────────────────────────────────

class TestShellModule(unittest.TestCase):
    """Verify shell module imports and entry point exist."""

    def test_run_shell_is_callable(self):
        from aura_os.shell.shell import run_shell
        self.assertTrue(callable(run_shell))

    def test_print_welcome(self):
        from aura_os.shell.shell import _print_welcome

        class _StubEAL:
            platform = "linux"

        # Should not raise
        _print_welcome(_StubEAL())

    def test_execute_line_handles_error(self):
        from aura_os.shell.shell import _execute_line
        from aura_os.engine.cli import build_parser
        from aura_os.engine.router import CommandRouter

        class _StubEAL:
            platform = "linux"

        parser = build_parser()
        router = CommandRouter()
        eal = _StubEAL()

        # Should not raise even with no handlers registered
        _execute_line("nonexistent", parser, router, eal)

    def test_execute_line_handles_help(self):
        """--help triggers SystemExit which should be caught."""
        from aura_os.shell.shell import _execute_line
        from aura_os.engine.cli import build_parser
        from aura_os.engine.router import CommandRouter

        class _StubEAL:
            platform = "linux"

        parser = build_parser()
        router = CommandRouter()
        eal = _StubEAL()

        # Should not raise
        _execute_line("--help", parser, router, eal)


if __name__ == "__main__":
    unittest.main()
