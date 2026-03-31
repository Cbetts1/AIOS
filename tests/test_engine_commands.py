"""Tests for aura_os.engine.commands — CLI command handlers."""

import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault("AURA_HOME", str(Path(tempfile.gettempdir()) / "aura_os_test"))


# ──────────────────────────────────────────────────────────────────────────────
# EnvCommand tests
# ──────────────────────────────────────────────────────────────────────────────

class TestEnvCommand(unittest.TestCase):
    """Tests for the EnvCommand handler."""

    def setUp(self):
        from aura_os.engine.commands.env_cmd import EnvCommand
        self.cmd = EnvCommand()
        self.mock_eal = mock.MagicMock()
        self.mock_eal.get_env_info.return_value = {
            "platform": "linux",
            "pkg_manager": "apt",
            "paths": {"home": "/home/user", "tmp": "/tmp"},
            "binaries": {"python3": "/usr/bin/python3", "git": "/usr/bin/git"},
            "system": {"hostname": "testhost"},
        }

    def test_execute_returns_zero(self):
        args = mock.MagicMock()
        args.as_json = False
        result = self.cmd.execute(args, self.mock_eal)
        self.assertEqual(result, 0)

    def test_execute_json_mode(self):
        args = mock.MagicMock()
        args.as_json = True
        with mock.patch("sys.stdout", new_callable=io.StringIO) as out:
            result = self.cmd.execute(args, self.mock_eal)
        self.assertEqual(result, 0)
        output = out.getvalue()
        parsed = json.loads(output)
        self.assertEqual(parsed["platform"], "linux")

    def test_execute_human_readable(self):
        args = mock.MagicMock()
        args.as_json = False
        with mock.patch("sys.stdout", new_callable=io.StringIO) as out:
            self.cmd.execute(args, self.mock_eal)
        output = out.getvalue()
        self.assertIn("linux", output)
        self.assertIn("apt", output)

    def test_print_human_includes_paths(self):
        with mock.patch("sys.stdout", new_callable=io.StringIO) as out:
            self.cmd._print_human({
                "platform": "linux",
                "paths": {"home": "/home/user"},
                "binaries": {},
                "system": {},
            })
        output = out.getvalue()
        self.assertIn("home", output)
        self.assertIn("/home/user", output)

    def test_print_human_memory_section(self):
        with mock.patch("sys.stdout", new_callable=io.StringIO) as out:
            self.cmd._print_human({
                "platform": "linux",
                "system": {"memory": {"total": 8589934592, "used": 4294967296, "percent": 50}},
            })
        output = out.getvalue()
        self.assertIn("memory", output)


# ──────────────────────────────────────────────────────────────────────────────
# KillCommand tests
# ──────────────────────────────────────────────────────────────────────────────

class TestKillCommand(unittest.TestCase):
    """Tests for the KillCommand handler."""

    def setUp(self):
        from aura_os.engine.commands.kill_cmd import KillCommand
        self.cmd = KillCommand()

    def test_kill_nonexistent_pid(self):
        args = mock.MagicMock()
        args.pid = 999999999  # PID that almost certainly doesn't exist
        args.signal_num = 15
        eal = mock.MagicMock()
        with mock.patch("sys.stdout", new_callable=io.StringIO):
            result = self.cmd.execute(args, eal)
        self.assertEqual(result, 1)


# ──────────────────────────────────────────────────────────────────────────────
# LogCommand tests
# ──────────────────────────────────────────────────────────────────────────────

class TestLogCommand(unittest.TestCase):
    """Tests for the LogCommand handler."""

    def setUp(self):
        from aura_os.engine.commands.log_cmd import LogCommand
        self.cmd = LogCommand()

    def test_tail_default(self):
        args = mock.MagicMock()
        args.log_command = "tail"
        args.lines = 25
        eal = mock.MagicMock()
        with mock.patch("sys.stdout", new_callable=io.StringIO):
            result = self.cmd.execute(args, eal)
        self.assertEqual(result, 0)

    def test_search_without_pattern(self):
        args = mock.MagicMock()
        args.log_command = "search"
        args.pattern = ""
        eal = mock.MagicMock()
        with mock.patch("sys.stdout", new_callable=io.StringIO):
            result = self.cmd.execute(args, eal)
        self.assertEqual(result, 1)

    def test_clear_log(self):
        args = mock.MagicMock()
        args.log_command = "clear"
        eal = mock.MagicMock()
        with mock.patch("sys.stdout", new_callable=io.StringIO):
            result = self.cmd.execute(args, eal)
        self.assertEqual(result, 0)

    def test_unknown_subcommand(self):
        args = mock.MagicMock()
        args.log_command = "invalid"
        eal = mock.MagicMock()
        with mock.patch("sys.stdout", new_callable=io.StringIO):
            result = self.cmd.execute(args, eal)
        self.assertEqual(result, 1)


# ──────────────────────────────────────────────────────────────────────────────
# PsCommand tests
# ──────────────────────────────────────────────────────────────────────────────

class TestPsCommand(unittest.TestCase):
    """Tests for the PsCommand handler."""

    def setUp(self):
        from aura_os.engine.commands.ps_cmd import PsCommand
        self.cmd = PsCommand()

    def test_ps_returns_zero(self):
        args = mock.MagicMock()
        eal = mock.MagicMock()
        with mock.patch("sys.stdout", new_callable=io.StringIO):
            result = self.cmd.execute(args, eal)
        self.assertEqual(result, 0)


# ──────────────────────────────────────────────────────────────────────────────
# SysCommand tests
# ──────────────────────────────────────────────────────────────────────────────

class TestSysCommand(unittest.TestCase):
    """Tests for the SysCommand handler."""

    def setUp(self):
        from aura_os.engine.commands.sys_cmd import SysCommand
        self.cmd = SysCommand()

    def test_sys_returns_zero(self):
        args = mock.MagicMock()
        args.watch = False
        eal = mock.MagicMock()
        eal.get_env_info.return_value = {"platform": "linux"}
        with mock.patch("sys.stdout", new_callable=io.StringIO):
            result = self.cmd.execute(args, eal)
        self.assertEqual(result, 0)


# ──────────────────────────────────────────────────────────────────────────────
# sys_cmd helper functions
# ──────────────────────────────────────────────────────────────────────────────

class TestSysCmdHelpers(unittest.TestCase):
    """Tests for sys_cmd module-level helper functions."""

    def test_uptime_returns_string(self):
        from aura_os.engine.commands.sys_cmd import _uptime
        result = _uptime()
        self.assertIsInstance(result, str)

    def test_disk_usage_returns_dict(self):
        from aura_os.engine.commands.sys_cmd import _disk_usage
        result = _disk_usage("/")
        self.assertIsInstance(result, dict)
        self.assertIn("total_gb", result)
        self.assertIn("free_gb", result)

    def test_process_count_positive(self):
        from aura_os.engine.commands.sys_cmd import _process_count
        count = _process_count()
        self.assertGreater(count, 0)

    def test_render_returns_string(self):
        from aura_os.engine.commands.sys_cmd import _render
        eal = mock.MagicMock()
        eal.get_env_info.return_value = {"platform": "linux"}
        result = _render(eal)
        self.assertIsInstance(result, str)
        self.assertIn("AURA", result)


if __name__ == "__main__":
    unittest.main()
