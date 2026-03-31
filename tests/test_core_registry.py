"""Tests for core.registry — CommandRegistry."""

import os
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault("AURA_HOME", str(Path(tempfile.gettempdir()) / "aura_os_test"))

from core.registry import CommandRegistry


class TestCommandRegistry(unittest.TestCase):
    """Unit tests for CommandRegistry."""

    def setUp(self):
        self.reg = CommandRegistry()

    # ── Initialization ────────────────────────────────────────────────

    def test_empty_on_init(self):
        self.assertEqual(self.reg.names(), [])
        self.assertEqual(self.reg.all_commands(), {})

    # ── register ──────────────────────────────────────────────────────

    def test_register_command(self):
        handler = lambda args, ctx: None
        self.reg.register("test", handler, "A test command", "test <args>")
        cmd = self.reg.get("test")
        self.assertIsNotNone(cmd)
        self.assertEqual(cmd["description"], "A test command")
        self.assertEqual(cmd["usage"], "test <args>")
        self.assertIs(cmd["handler"], handler)

    def test_register_default_usage(self):
        self.reg.register("foo", lambda a, c: None, "Foo cmd")
        cmd = self.reg.get("foo")
        self.assertEqual(cmd["usage"], "foo")

    def test_register_overwrites_existing(self):
        self.reg.register("cmd", lambda a, c: "v1", "Version 1")
        self.reg.register("cmd", lambda a, c: "v2", "Version 2")
        cmd = self.reg.get("cmd")
        self.assertEqual(cmd["description"], "Version 2")

    # ── get ────────────────────────────────────────────────────────────

    def test_get_nonexistent_returns_none(self):
        self.assertIsNone(self.reg.get("nope"))

    def test_get_returns_registered_command(self):
        self.reg.register("exists", lambda a, c: None)
        self.assertIsNotNone(self.reg.get("exists"))

    # ── names ──────────────────────────────────────────────────────────

    def test_names_returns_all_registered(self):
        self.reg.register("alpha", lambda a, c: None)
        self.reg.register("beta", lambda a, c: None)
        self.reg.register("gamma", lambda a, c: None)
        names = self.reg.names()
        self.assertEqual(set(names), {"alpha", "beta", "gamma"})

    # ── all_commands ──────────────────────────────────────────────────

    def test_all_commands_returns_dict(self):
        self.reg.register("x", lambda a, c: None, "X cmd")
        cmds = self.reg.all_commands()
        self.assertIsInstance(cmds, dict)
        self.assertIn("x", cmds)

    def test_all_commands_returns_copy(self):
        self.reg.register("a", lambda a, c: None)
        cmds = self.reg.all_commands()
        cmds["hacked"] = True
        self.assertIsNone(self.reg.get("hacked"))

    # ── Multiple commands ──────────────────────────────────────────────

    def test_multiple_independent_commands(self):
        self.reg.register("cmd1", lambda a, c: 1, "First")
        self.reg.register("cmd2", lambda a, c: 2, "Second")
        self.assertEqual(len(self.reg.names()), 2)
        self.assertEqual(self.reg.get("cmd1")["description"], "First")
        self.assertEqual(self.reg.get("cmd2")["description"], "Second")


if __name__ == "__main__":
    unittest.main()
