"""Tests for core.permissions — check_permission & require_permission."""

import io
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault("AURA_HOME", str(Path(tempfile.gettempdir()) / "aura_os_test"))

from core.permissions import (
    DANGEROUS_ACTIONS,
    check_permission,
    require_permission,
)


class TestDangerousActions(unittest.TestCase):
    """Tests for the DANGEROUS_ACTIONS constant."""

    def test_is_dict(self):
        self.assertIsInstance(DANGEROUS_ACTIONS, dict)

    def test_contains_expected_actions(self):
        expected = {"pkg_install", "pkg_remove", "fs_delete",
                    "process_kill", "host_shell", "systemd", "sudo"}
        self.assertTrue(expected.issubset(set(DANGEROUS_ACTIONS.keys())))

    def test_values_are_strings(self):
        for key, desc in DANGEROUS_ACTIONS.items():
            self.assertIsInstance(desc, str, f"{key} description is not a string")


class TestCheckPermission(unittest.TestCase):
    """Tests for check_permission()."""

    def test_auto_approve_returns_true(self):
        result = check_permission("pkg_install", auto_approve=True)
        self.assertTrue(result)

    def test_auto_approve_with_detail(self):
        result = check_permission("fs_delete", "remove /tmp/x", auto_approve=True)
        self.assertTrue(result)

    def test_non_interactive_denies(self):
        """Non-interactive mode (piped stdin) should deny."""
        with mock.patch("sys.stdin") as mock_stdin:
            mock_stdin.isatty.return_value = False
            result = check_permission("host_shell")
        self.assertFalse(result)

    @mock.patch("sys.stdin")
    @mock.patch("builtins.input", return_value="y")
    def test_interactive_user_approves(self, mock_input, mock_stdin):
        mock_stdin.isatty.return_value = True
        result = check_permission("pkg_install")
        self.assertTrue(result)

    @mock.patch("sys.stdin")
    @mock.patch("builtins.input", return_value="yes")
    def test_interactive_user_approves_yes(self, mock_input, mock_stdin):
        mock_stdin.isatty.return_value = True
        result = check_permission("pkg_install")
        self.assertTrue(result)

    @mock.patch("sys.stdin")
    @mock.patch("builtins.input", return_value="n")
    def test_interactive_user_denies(self, mock_input, mock_stdin):
        mock_stdin.isatty.return_value = True
        result = check_permission("pkg_install")
        self.assertFalse(result)

    @mock.patch("sys.stdin")
    @mock.patch("builtins.input", return_value="")
    def test_interactive_empty_input_denies(self, mock_input, mock_stdin):
        mock_stdin.isatty.return_value = True
        result = check_permission("pkg_install")
        self.assertFalse(result)

    @mock.patch("sys.stdin")
    @mock.patch("builtins.input", side_effect=EOFError)
    def test_eof_denies(self, mock_input, mock_stdin):
        mock_stdin.isatty.return_value = True
        result = check_permission("pkg_install")
        self.assertFalse(result)

    @mock.patch("sys.stdin")
    @mock.patch("builtins.input", side_effect=KeyboardInterrupt)
    def test_keyboard_interrupt_denies(self, mock_input, mock_stdin):
        mock_stdin.isatty.return_value = True
        result = check_permission("sudo")
        self.assertFalse(result)

    def test_unknown_action_still_works(self):
        result = check_permission("unknown_action", auto_approve=True)
        self.assertTrue(result)


class TestRequirePermission(unittest.TestCase):
    """Tests for require_permission()."""

    def test_auto_approve_does_not_raise(self):
        # Should not raise
        require_permission("fs_delete", auto_approve=True)

    def test_denial_raises_permission_error(self):
        with mock.patch("sys.stdin") as mock_stdin:
            mock_stdin.isatty.return_value = False
            with self.assertRaises(PermissionError) as ctx:
                require_permission("host_shell")
            self.assertIn("host_shell", str(ctx.exception))

    @mock.patch("sys.stdin")
    @mock.patch("builtins.input", return_value="y")
    def test_approval_does_not_raise(self, mock_input, mock_stdin):
        mock_stdin.isatty.return_value = True
        # Should not raise
        require_permission("pkg_install")


if __name__ == "__main__":
    unittest.main()
