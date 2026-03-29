"""Tests for the engine (CLI parsing and command router)."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from aura_os.engine.cli import build_parser
from aura_os.engine.router import CommandRouter


# ---------------------------------------------------------------------------
# Minimal stub EAL for routing tests
# ---------------------------------------------------------------------------

class _StubEAL:
    platform = "linux"

    def get_env_info(self):
        return {"platform": "linux", "paths": {}, "binaries": {}, "system": {}}


# ---------------------------------------------------------------------------
# Minimal stub command handlers
# ---------------------------------------------------------------------------

class _OkHandler:
    """Always returns exit-code 0."""
    def execute(self, args, eal):
        return 0


class _FailHandler:
    """Always returns exit-code 1."""
    def execute(self, args, eal):
        return 1


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestCLIParsing(unittest.TestCase):
    """Verify that each subcommand is parsed correctly."""

    def setUp(self):
        self.parser = build_parser()

    def _parse(self, argv):
        return self.parser.parse_args(argv)

    def test_version_flag(self):
        with self.assertRaises(SystemExit) as ctx:
            self._parse(["--version"])
        self.assertEqual(ctx.exception.code, 0)

    def test_run_command(self):
        args = self._parse(["run", "script.py"])
        self.assertEqual(args.command, "run")
        self.assertEqual(args.file, "script.py")

    def test_run_command_with_args(self):
        args = self._parse(["run", "script.py", "--", "a", "b"])
        self.assertEqual(args.file, "script.py")
        self.assertIn("a", args.args)

    def test_ai_command(self):
        args = self._parse(["ai", "hello world"])
        self.assertEqual(args.command, "ai")
        self.assertEqual(args.prompt, "hello world")

    def test_ai_command_model_flag(self):
        args = self._parse(["ai", "test prompt", "--model", "mistral"])
        self.assertEqual(args.model, "mistral")

    def test_ai_command_max_tokens(self):
        args = self._parse(["ai", "p", "--max-tokens", "256"])
        self.assertEqual(args.max_tokens, 256)

    def test_env_command(self):
        args = self._parse(["env"])
        self.assertEqual(args.command, "env")
        self.assertFalse(args.as_json)

    def test_env_command_json(self):
        args = self._parse(["env", "--json"])
        self.assertTrue(args.as_json)

    def test_pkg_install(self):
        args = self._parse(["pkg", "install", "my-pkg"])
        self.assertEqual(args.command, "pkg")
        self.assertEqual(args.pkg_command, "install")
        self.assertEqual(args.name_or_path, "my-pkg")

    def test_pkg_remove(self):
        args = self._parse(["pkg", "remove", "my-pkg"])
        self.assertEqual(args.pkg_command, "remove")
        self.assertEqual(args.name, "my-pkg")

    def test_pkg_list(self):
        args = self._parse(["pkg", "list"])
        self.assertEqual(args.pkg_command, "list")

    def test_pkg_search(self):
        args = self._parse(["pkg", "search", "editor"])
        self.assertEqual(args.pkg_command, "search")
        self.assertEqual(args.query, "editor")

    def test_sys_command(self):
        args = self._parse(["sys"])
        self.assertEqual(args.command, "sys")
        self.assertFalse(args.watch)

    def test_sys_watch_flag(self):
        args = self._parse(["sys", "--watch"])
        self.assertTrue(args.watch)

    def test_shell_command(self):
        args = self._parse(["shell"])
        self.assertEqual(args.command, "shell")

    def test_verbose_flag(self):
        args = self._parse(["--verbose", "env"])
        self.assertTrue(args.verbose)


class TestRouter(unittest.TestCase):
    """Verify that CommandRouter dispatches to the correct handler."""

    def setUp(self):
        self.router = CommandRouter()
        self.eal = _StubEAL()
        self.parser = build_parser()

    def test_register_and_dispatch(self):
        self.router.register("env", _OkHandler)
        args = self.parser.parse_args(["env"])
        code = self.router.dispatch(args, self.eal)
        self.assertEqual(code, 0)

    def test_dispatch_unknown_command(self):
        # Don't register anything; simulate an unknown command
        args = self.parser.parse_args(["env"])
        # Override command name to something not registered
        args.command = "__nonexistent__"
        code = self.router.dispatch(args, self.eal)
        self.assertEqual(code, 1)

    def test_dispatch_no_command(self):
        args = self.parser.parse_args([])
        args.command = None
        code = self.router.dispatch(args, self.eal)
        self.assertEqual(code, 2)

    def test_dispatch_uses_correct_handler(self):
        self.router.register("env", _OkHandler)
        self.router.register("sys", _FailHandler)

        env_args = self.parser.parse_args(["env"])
        sys_args = self.parser.parse_args(["sys"])

        self.assertEqual(self.router.dispatch(env_args, self.eal), 0)
        self.assertEqual(self.router.dispatch(sys_args, self.eal), 1)


if __name__ == "__main__":
    unittest.main()
