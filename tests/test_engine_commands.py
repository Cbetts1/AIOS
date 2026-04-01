"""Tests for aura_os/engine/commands — EnvCommand, KillCommand, LogCommand,
PsCommand, RunCommand, SysCommand."""

import io
import os
import sys
import signal
import tempfile
import types
import unittest
from contextlib import redirect_stdout
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from aura_os.engine.commands.env_cmd import EnvCommand
from aura_os.engine.commands.kill_cmd import KillCommand
from aura_os.engine.commands.log_cmd import LogCommand
from aura_os.engine.commands.ps_cmd import PsCommand, get_process_manager
from aura_os.engine.commands.run import RunCommand
from aura_os.engine.commands.sys_cmd import SysCommand, _uptime, _disk_usage, _process_count


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _args(**kwargs):
    """Build a simple namespace object for command args."""
    return types.SimpleNamespace(**kwargs)


def _make_eal(platform="linux"):
    eal = MagicMock()
    eal.platform = platform
    eal.get_env_info.return_value = {
        "platform": platform,
        "pkg_manager": "apt",
        "paths": {"home": "/home/user"},
        "system": {"cpu_count": 4, "memory": {"total": 8192 * 1024 * 1024,
                                               "used": 2048 * 1024 * 1024,
                                               "available": 6144 * 1024 * 1024,
                                               "percent": 25.0}},
        "binaries": {"python3": "/usr/bin/python3"},
    }
    return eal


# ---------------------------------------------------------------------------
# EnvCommand
# ---------------------------------------------------------------------------

class TestEnvCommand(unittest.TestCase):

    def setUp(self):
        self.cmd = EnvCommand()
        self.eal = _make_eal()

    def test_execute_returns_zero(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = self.cmd.execute(_args(as_json=False), self.eal)
        self.assertEqual(rc, 0)

    def test_execute_json_mode_returns_zero(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = self.cmd.execute(_args(as_json=True), self.eal)
        self.assertEqual(rc, 0)

    def test_execute_json_mode_outputs_valid_json(self):
        import json
        buf = io.StringIO()
        with redirect_stdout(buf):
            self.cmd.execute(_args(as_json=True), self.eal)
        data = json.loads(buf.getvalue())
        self.assertIn("platform", data)

    def test_execute_human_mode_shows_platform(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            self.cmd.execute(_args(as_json=False), self.eal)
        self.assertIn("linux", buf.getvalue())

    def test_print_human_no_paths(self):
        self.eal.get_env_info.return_value = {
            "platform": "linux",
            "pkg_manager": None,
            "paths": {},
            "system": {},
            "binaries": {},
        }
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = self.cmd.execute(_args(as_json=False), self.eal)
        self.assertEqual(rc, 0)

    def test_print_human_shows_binaries(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            self.cmd.execute(_args(as_json=False), self.eal)
        self.assertIn("python3", buf.getvalue())

    def test_print_human_memory_display(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            self.cmd.execute(_args(as_json=False), self.eal)
        self.assertIn("MB", buf.getvalue())


# ---------------------------------------------------------------------------
# KillCommand
# ---------------------------------------------------------------------------

class TestKillCommand(unittest.TestCase):

    def setUp(self):
        self.cmd = KillCommand()
        self.eal = _make_eal()

    def test_kill_tracked_process_returns_zero(self):
        mock_pm = MagicMock()
        mock_pm.send_signal.return_value = True
        with patch("aura_os.engine.commands.kill_cmd.get_process_manager", return_value=mock_pm):
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = self.cmd.execute(_args(pid=1234, signal_num=signal.SIGTERM), self.eal)
        self.assertEqual(rc, 0)

    def test_kill_untracked_process_os_kill_succeeds(self):
        mock_pm = MagicMock()
        mock_pm.send_signal.return_value = False
        with patch("aura_os.engine.commands.kill_cmd.get_process_manager", return_value=mock_pm):
            with patch("os.kill") as mock_os_kill:
                buf = io.StringIO()
                with redirect_stdout(buf):
                    rc = self.cmd.execute(_args(pid=9999, signal_num=signal.SIGTERM), self.eal)
        self.assertEqual(rc, 0)
        mock_os_kill.assert_called_once_with(9999, signal.SIGTERM)

    def test_kill_process_not_found_returns_one(self):
        mock_pm = MagicMock()
        mock_pm.send_signal.return_value = False
        with patch("aura_os.engine.commands.kill_cmd.get_process_manager", return_value=mock_pm):
            with patch("os.kill", side_effect=ProcessLookupError("no such process")):
                buf = io.StringIO()
                with redirect_stdout(buf):
                    rc = self.cmd.execute(_args(pid=99999, signal_num=signal.SIGTERM), self.eal)
        self.assertEqual(rc, 1)

    def test_kill_permission_denied_returns_one(self):
        mock_pm = MagicMock()
        mock_pm.send_signal.return_value = False
        with patch("aura_os.engine.commands.kill_cmd.get_process_manager", return_value=mock_pm):
            with patch("os.kill", side_effect=PermissionError("denied")):
                buf = io.StringIO()
                with redirect_stdout(buf):
                    rc = self.cmd.execute(_args(pid=1, signal_num=signal.SIGTERM), self.eal)
        self.assertEqual(rc, 1)

    def test_kill_uses_default_sigterm_when_no_signal_num(self):
        mock_pm = MagicMock()
        mock_pm.send_signal.return_value = True
        with patch("aura_os.engine.commands.kill_cmd.get_process_manager", return_value=mock_pm):
            buf = io.StringIO()
            with redirect_stdout(buf):
                # No signal_num attribute → should default to SIGTERM
                rc = self.cmd.execute(_args(pid=100), self.eal)
        self.assertEqual(rc, 0)
        mock_pm.send_signal.assert_called_once_with(100, signal.SIGTERM)


# ---------------------------------------------------------------------------
# LogCommand
# ---------------------------------------------------------------------------

class TestLogCommand(unittest.TestCase):

    def setUp(self):
        self.cmd = LogCommand()
        self.eal = _make_eal()
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _make_syslog(self, entries=None):
        from aura_os.kernel.syslog import Syslog
        log_path = os.path.join(self.tmpdir, "syslog.json")
        slog = Syslog(log_file=log_path)
        for entry in (entries or []):
            slog.log(entry, source="test")
        return slog

    def test_tail_no_entries_returns_zero(self):
        with patch("aura_os.engine.commands.log_cmd.Syslog") as MockSyslog:
            mock = MockSyslog.return_value
            mock.tail.return_value = []
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = self.cmd.execute(_args(log_command="tail", lines=10), self.eal)
        self.assertEqual(rc, 0)
        self.assertIn("no log", buf.getvalue())

    def test_tail_with_entries_returns_zero(self):
        with patch("aura_os.engine.commands.log_cmd.Syslog") as MockSyslog:
            mock = MockSyslog.return_value
            mock.tail.return_value = ["entry 1", "entry 2"]
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = self.cmd.execute(_args(log_command="tail", lines=5), self.eal)
        self.assertEqual(rc, 0)
        self.assertIn("entry 1", buf.getvalue())

    def test_search_with_results_returns_zero(self):
        with patch("aura_os.engine.commands.log_cmd.Syslog") as MockSyslog:
            mock = MockSyslog.return_value
            mock.search.return_value = ["matched line"]
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = self.cmd.execute(_args(log_command="search", pattern="error"), self.eal)
        self.assertEqual(rc, 0)

    def test_search_no_results(self):
        with patch("aura_os.engine.commands.log_cmd.Syslog") as MockSyslog:
            mock = MockSyslog.return_value
            mock.search.return_value = []
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = self.cmd.execute(_args(log_command="search", pattern="notfound"), self.eal)
        self.assertEqual(rc, 0)

    def test_search_missing_pattern_returns_one(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = self.cmd.execute(_args(log_command="search", pattern=""), self.eal)
        self.assertEqual(rc, 1)

    def test_clear_returns_zero(self):
        with patch("aura_os.engine.commands.log_cmd.Syslog") as MockSyslog:
            mock = MockSyslog.return_value
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = self.cmd.execute(_args(log_command="clear"), self.eal)
        self.assertEqual(rc, 0)
        mock.clear.assert_called_once()

    def test_unknown_subcommand_returns_one(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = self.cmd.execute(_args(log_command="unknown_cmd"), self.eal)
        self.assertEqual(rc, 1)

    def test_tail_is_default_subcommand(self):
        with patch("aura_os.engine.commands.log_cmd.Syslog") as MockSyslog:
            mock = MockSyslog.return_value
            mock.tail.return_value = []
            buf = io.StringIO()
            with redirect_stdout(buf):
                # No log_command attr → defaults to tail
                rc = self.cmd.execute(_args(), self.eal)
        self.assertEqual(rc, 0)
        mock.tail.assert_called_once()


# ---------------------------------------------------------------------------
# PsCommand
# ---------------------------------------------------------------------------

class TestPsCommand(unittest.TestCase):

    def setUp(self):
        self.cmd = PsCommand()
        self.eal = _make_eal()

    def test_no_processes_returns_zero(self):
        mock_pm = MagicMock()
        mock_pm.list_processes.return_value = []
        with patch("aura_os.engine.commands.ps_cmd.get_process_manager", return_value=mock_pm):
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = self.cmd.execute(_args(), self.eal)
        self.assertEqual(rc, 0)
        self.assertIn("No tracked", buf.getvalue())

    def test_with_processes_returns_zero(self):
        mock_pm = MagicMock()
        mock_pm.list_processes.return_value = [
            {"pid": 100, "ppid": 1, "status": "running", "elapsed": 30.0, "command": "test"},
        ]
        with patch("aura_os.engine.commands.ps_cmd.get_process_manager", return_value=mock_pm):
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = self.cmd.execute(_args(), self.eal)
        self.assertEqual(rc, 0)
        self.assertIn("100", buf.getvalue())

    def test_elapsed_seconds_formatting(self):
        mock_pm = MagicMock()
        mock_pm.list_processes.return_value = [
            {"pid": 1, "ppid": 0, "status": "running", "elapsed": 45.0, "command": "proc"},
        ]
        with patch("aura_os.engine.commands.ps_cmd.get_process_manager", return_value=mock_pm):
            buf = io.StringIO()
            with redirect_stdout(buf):
                self.cmd.execute(_args(), self.eal)
        self.assertIn("45.0s", buf.getvalue())

    def test_elapsed_minutes_formatting(self):
        mock_pm = MagicMock()
        mock_pm.list_processes.return_value = [
            {"pid": 1, "ppid": 0, "status": "running", "elapsed": 120.0, "command": "proc"},
        ]
        with patch("aura_os.engine.commands.ps_cmd.get_process_manager", return_value=mock_pm):
            buf = io.StringIO()
            with redirect_stdout(buf):
                self.cmd.execute(_args(), self.eal)
        self.assertIn("2.0m", buf.getvalue())

    def test_elapsed_hours_formatting(self):
        mock_pm = MagicMock()
        mock_pm.list_processes.return_value = [
            {"pid": 1, "ppid": 0, "status": "running", "elapsed": 7200.0, "command": "proc"},
        ]
        with patch("aura_os.engine.commands.ps_cmd.get_process_manager", return_value=mock_pm):
            buf = io.StringIO()
            with redirect_stdout(buf):
                self.cmd.execute(_args(), self.eal)
        self.assertIn("2.0h", buf.getvalue())


class TestGetProcessManager(unittest.TestCase):

    def test_returns_process_manager_instance(self):
        from aura_os.kernel.process import ProcessManager
        # Reset singleton for clean test
        import aura_os.engine.commands.ps_cmd as ps_mod
        ps_mod._pm = None
        pm = get_process_manager()
        self.assertIsInstance(pm, ProcessManager)

    def test_returns_same_instance(self):
        import aura_os.engine.commands.ps_cmd as ps_mod
        ps_mod._pm = None
        pm1 = get_process_manager()
        pm2 = get_process_manager()
        self.assertIs(pm1, pm2)


# ---------------------------------------------------------------------------
# RunCommand
# ---------------------------------------------------------------------------

class TestRunCommand(unittest.TestCase):

    def setUp(self):
        self.cmd = RunCommand()
        self.eal = _make_eal()
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _write_script(self, filename, content=""):
        path = os.path.join(self.tmpdir, filename)
        with open(path, "w") as fh:
            fh.write(content)
        return path

    def test_file_not_found_returns_one(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = self.cmd.execute(_args(file="/nonexistent/script.py", args=[]), self.eal)
        self.assertEqual(rc, 1)
        self.assertIn("not found", buf.getvalue())

    def test_no_runtime_for_extension_returns_one(self):
        path = self._write_script("unknown.xyz", "data")
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = self.cmd.execute(_args(file=path, args=[]), self.eal)
        self.assertEqual(rc, 1)

    def test_python_script_with_available_runtime(self):
        path = self._write_script("test.py", "print('hi')")
        with patch("shutil.which", return_value="/usr/bin/python3"):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0)
                buf = io.StringIO()
                with redirect_stdout(buf):
                    rc = self.cmd.execute(_args(file=path, args=[]), self.eal)
        self.assertEqual(rc, 0)

    def test_runtime_not_in_path_returns_one(self):
        path = self._write_script("script.py", "")
        with patch("shutil.which", return_value=None):
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = self.cmd.execute(_args(file=path, args=[]), self.eal)
        self.assertEqual(rc, 1)
        self.assertIn("not found", buf.getvalue())

    def test_executable_file_without_known_extension(self):
        path = self._write_script("myscript", "#!/bin/bash\necho hi")
        os.chmod(path, 0o755)
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            rc = self.cmd.execute(_args(file=path, args=[]), self.eal)
        self.assertEqual(rc, 0)

    def test_run_passes_extra_args_to_subprocess(self):
        path = self._write_script("script.py", "")
        captured_cmd = []

        def fake_run(cmd, **kwargs):
            captured_cmd.extend(cmd)
            return MagicMock(returncode=0)

        with patch("shutil.which", return_value="/usr/bin/python3"):
            with patch("subprocess.run", side_effect=fake_run):
                self.cmd.execute(_args(file=path, args=["--foo", "bar"]), self.eal)
        self.assertIn("--foo", captured_cmd)
        self.assertIn("bar", captured_cmd)

    def test_run_oserror_returns_one(self):
        path = self._write_script("script.sh", "")
        with patch("shutil.which", return_value="/bin/bash"):
            with patch("subprocess.run", side_effect=OSError("exec failed")):
                buf = io.StringIO()
                with redirect_stdout(buf):
                    rc = self.cmd.execute(_args(file=path, args=[]), self.eal)
        self.assertEqual(rc, 1)

    def test_keyboard_interrupt_returns_130(self):
        path = self._write_script("script.sh", "")
        with patch("shutil.which", return_value="/bin/bash"):
            with patch("subprocess.run", side_effect=KeyboardInterrupt):
                rc = self.cmd.execute(_args(file=path, args=[]), self.eal)
        self.assertEqual(rc, 130)


# ---------------------------------------------------------------------------
# SysCommand helper functions
# ---------------------------------------------------------------------------

class TestSysHelpers(unittest.TestCase):

    def test_uptime_returns_string(self):
        result = _uptime()
        self.assertIsInstance(result, str)

    def test_uptime_parses_proc_uptime(self):
        with patch("builtins.open", unittest.mock.mock_open(read_data="3661.5 7000.0\n")):
            result = _uptime()
        # 3661 seconds = 1h 1m 1s
        self.assertIn("1h", result)
        self.assertIn("1m", result)

    def test_uptime_oserror_returns_unknown(self):
        with patch("builtins.open", side_effect=OSError):
            result = _uptime()
        self.assertEqual(result, "unknown")

    def test_disk_usage_returns_dict(self):
        result = _disk_usage("/")
        self.assertIsInstance(result, dict)

    def test_disk_usage_has_keys(self):
        result = _disk_usage("/")
        for key in ("total_gb", "used_gb", "free_gb", "percent"):
            self.assertIn(key, result)

    def test_disk_usage_oserror_returns_empty(self):
        with patch("os.statvfs", side_effect=OSError):
            result = _disk_usage("/nonexistent")
        self.assertEqual(result, {})

    def test_process_count_returns_int(self):
        result = _process_count()
        self.assertIsInstance(result, int)
        self.assertGreaterEqual(result, 0)

    def test_process_count_oserror_returns_zero(self):
        with patch("os.listdir", side_effect=OSError):
            result = _process_count()
        self.assertEqual(result, 0)


class TestSysCommand(unittest.TestCase):

    def setUp(self):
        self.cmd = SysCommand()
        self.eal = _make_eal()

    def test_execute_returns_zero(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = self.cmd.execute(_args(watch=False), self.eal)
        self.assertEqual(rc, 0)

    def test_execute_shows_platform(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            self.cmd.execute(_args(watch=False), self.eal)
        self.assertIn("linux", buf.getvalue())

    def test_execute_shows_memory(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            self.cmd.execute(_args(watch=False), self.eal)
        self.assertIn("Memory", buf.getvalue())

    def test_execute_watch_stops_on_keyboard_interrupt(self):
        call_count = [0]

        def fake_sleep(_):
            call_count[0] += 1
            if call_count[0] >= 2:
                raise KeyboardInterrupt

        with patch("time.sleep", side_effect=fake_sleep):
            with patch("builtins.print"):
                rc = self.cmd.execute(_args(watch=True), self.eal)
        self.assertEqual(rc, 0)


if __name__ == "__main__":
    unittest.main()
