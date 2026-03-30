"""
AURA OS Test Suite — OS Feature Tests
Tests for process manager, service manager, syslog, procfs, and enhanced shell.
"""

import os
import sys
import json
import tempfile
import time
import unittest
from pathlib import Path

# Ensure the project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault("AURA_HOME", str(Path(tempfile.gettempdir()) / "aura_os_test"))


# ──────────────────────────────────────────────────────────────────────────────
# Process Manager tests
# ──────────────────────────────────────────────────────────────────────────────

class TestProcessManager(unittest.TestCase):

    def setUp(self):
        from aura_os.kernel.process import ProcessManager
        self.pm = ProcessManager()

    def test_spawn_foreground(self):
        entry = self.pm.spawn(["echo", "hello"], name="echo-test")
        self.assertEqual(entry.status, "exited")
        self.assertEqual(entry.exit_code, 0)
        self.assertGreater(entry.pid, 0)

    def test_spawn_background(self):
        entry = self.pm.spawn(["sleep", "0.1"], name="sleep-bg", background=True)
        self.assertEqual(entry.status, "running")
        self.assertGreater(entry.pid, 0)
        time.sleep(0.3)
        procs = self.pm.list_processes()
        found = [p for p in procs if p["pid"] == entry.pid]
        self.assertTrue(len(found) > 0)
        # Should have exited by now
        self.assertEqual(found[0]["status"], "exited")

    def test_list_processes(self):
        self.pm.spawn(["echo", "a"], name="proc-a")
        self.pm.spawn(["echo", "b"], name="proc-b")
        procs = self.pm.list_processes()
        self.assertEqual(len(procs), 2)
        names = {p["name"] for p in procs}
        self.assertIn("proc-a", names)
        self.assertIn("proc-b", names)

    def test_get_process(self):
        entry = self.pm.spawn(["echo", "x"], name="get-me")
        result = self.pm.get_process(entry.pid)
        self.assertIsNotNone(result)
        self.assertEqual(result.name, "get-me")

    def test_get_process_nonexistent(self):
        result = self.pm.get_process(999999)
        self.assertIsNone(result)

    def test_terminate_running(self):
        entry = self.pm.spawn(["sleep", "30"], name="long-sleep", background=True)
        result = self.pm.terminate(entry.pid)
        self.assertTrue(result)
        time.sleep(0.2)
        procs = self.pm.list_processes()
        found = [p for p in procs if p["pid"] == entry.pid]
        self.assertEqual(found[0]["status"], "exited")

    def test_cleanup(self):
        self.pm.spawn(["echo", "done"], name="cleanup-test")
        self.assertEqual(len(self.pm.list_processes()), 1)
        self.pm.cleanup()
        self.assertEqual(len(self.pm.list_processes()), 0)

    def test_process_entry_has_command(self):
        entry = self.pm.spawn(["echo", "cmd-check"], name="cmd-test")
        self.assertEqual(entry.command, ["echo", "cmd-check"])


# ──────────────────────────────────────────────────────────────────────────────
# Service Manager tests
# ──────────────────────────────────────────────────────────────────────────────

class TestServiceManager(unittest.TestCase):

    def setUp(self):
        from aura_os.kernel.service import ServiceManager
        self.tmpdir = tempfile.mkdtemp()
        self.sm = ServiceManager(services_dir=self.tmpdir)

    def tearDown(self):
        for svc in self.sm.list_services():
            if svc["status"] == "running":
                self.sm.stop(svc["name"])

    def test_create_service(self):
        self.sm.create("test-svc", "echo hello", description="Test service")
        services = self.sm.list_services()
        self.assertEqual(len(services), 1)
        self.assertEqual(services[0]["name"], "test-svc")

    def test_create_writes_manifest(self):
        self.sm.create("file-svc", "echo hi")
        manifest_path = os.path.join(self.tmpdir, "file-svc.json")
        self.assertTrue(os.path.isfile(manifest_path))
        data = json.loads(Path(manifest_path).read_text())
        self.assertEqual(data["name"], "file-svc")
        self.assertEqual(data["command"], "echo hi")

    def test_start_and_stop(self):
        self.sm.create("start-stop", "sleep 30")
        result = self.sm.start("start-stop")
        self.assertTrue(result)
        status = self.sm.status("start-stop")
        self.assertEqual(status["status"], "running")
        self.assertIsNotNone(status["pid"])

        result = self.sm.stop("start-stop")
        self.assertTrue(result)
        status = self.sm.status("start-stop")
        self.assertEqual(status["status"], "stopped")

    def test_restart(self):
        self.sm.create("restart-svc", "sleep 30")
        self.sm.start("restart-svc")
        result = self.sm.restart("restart-svc")
        self.assertTrue(result)

    def test_enable_disable(self):
        self.sm.create("toggle-svc", "echo x")
        self.sm.enable("toggle-svc")
        status = self.sm.status("toggle-svc")
        self.assertTrue(status["enabled"])

        self.sm.disable("toggle-svc")
        status = self.sm.status("toggle-svc")
        self.assertFalse(status["enabled"])

    def test_status_unknown_service(self):
        result = self.sm.status("nonexistent")
        self.assertIsNone(result)

    def test_stop_not_running(self):
        self.sm.create("idle-svc", "echo x")
        result = self.sm.stop("idle-svc")
        self.assertFalse(result)

    def test_list_empty(self):
        tmpdir2 = tempfile.mkdtemp()
        from aura_os.kernel.service import ServiceManager
        sm2 = ServiceManager(services_dir=tmpdir2)
        self.assertEqual(sm2.list_services(), [])


# ──────────────────────────────────────────────────────────────────────────────
# Syslog tests
# ──────────────────────────────────────────────────────────────────────────────

class TestSyslog(unittest.TestCase):

    def setUp(self):
        from aura_os.kernel.syslog import Syslog
        Syslog.reset_instance()
        self._tmpfile_obj = tempfile.NamedTemporaryFile(suffix=".log", delete=False)
        self.tmpfile = self._tmpfile_obj.name
        self._tmpfile_obj.close()
        self.syslog = Syslog(log_path=self.tmpfile)

    def tearDown(self):
        from aura_os.kernel.syslog import Syslog
        Syslog.reset_instance()
        if os.path.isfile(self.tmpfile):
            os.remove(self.tmpfile)

    def test_log_and_tail(self):
        self.syslog.info("kern", "boot complete")
        entries = self.syslog.tail(10)
        self.assertEqual(len(entries), 1)
        self.assertIn("kern.info", entries[0])
        self.assertIn("boot complete", entries[0])

    def test_log_multiple(self):
        self.syslog.info("kern", "msg1")
        self.syslog.warning("daemon", "msg2")
        self.syslog.error("user", "msg3")
        entries = self.syslog.tail(10)
        self.assertEqual(len(entries), 3)

    def test_search(self):
        self.syslog.info("kern", "hello world")
        self.syslog.info("kern", "goodbye world")
        self.syslog.info("kern", "other stuff")
        results = self.syslog.search("world")
        self.assertEqual(len(results), 2)

    def test_clear(self):
        self.syslog.info("kern", "to be cleared")
        self.syslog.clear()
        entries = self.syslog.tail(10)
        self.assertEqual(len(entries), 0)

    def test_severity_filter(self):
        from aura_os.kernel.syslog import WARNING
        self.syslog.set_level(WARNING)
        self.syslog.info("kern", "should be dropped")
        self.syslog.warning("kern", "should appear")
        entries = self.syslog.tail(10)
        self.assertEqual(len(entries), 1)
        self.assertIn("should appear", entries[0])

    def test_tail_empty(self):
        entries = self.syslog.tail(10)
        self.assertEqual(len(entries), 0)


# ──────────────────────────────────────────────────────────────────────────────
# ProcFS tests
# ──────────────────────────────────────────────────────────────────────────────

class TestProcFS(unittest.TestCase):

    def setUp(self):
        from aura_os.fs.procfs import ProcFS
        self.procfs = ProcFS()

    def test_ls_root(self):
        entries = self.procfs.ls()
        self.assertIn("uptime", entries)
        self.assertIn("version", entries)
        self.assertIn("meminfo", entries)
        self.assertIn("cpuinfo", entries)
        self.assertIn("hostname", entries)

    def test_ls_self(self):
        entries = self.procfs.ls("self")
        self.assertIn("status", entries)

    def test_read_uptime(self):
        content = self.procfs.read("uptime")
        self.assertIsNotNone(content)
        parts = content.strip().split()
        self.assertEqual(len(parts), 2)
        float(parts[0])  # should not raise

    def test_read_version(self):
        content = self.procfs.read("version")
        self.assertIn("AURA OS", content)

    def test_read_meminfo(self):
        content = self.procfs.read("meminfo")
        self.assertIn("MemTotal", content)
        self.assertIn("MemAvailable", content)

    def test_read_cpuinfo(self):
        content = self.procfs.read("cpuinfo")
        self.assertIn("processor", content)
        self.assertIn("model name", content)

    def test_read_loadavg(self):
        content = self.procfs.read("loadavg")
        self.assertIsNotNone(content)
        parts = content.strip().split()
        self.assertEqual(len(parts), 3)

    def test_read_hostname(self):
        import platform
        content = self.procfs.read("hostname")
        self.assertEqual(content.strip(), platform.node())

    def test_read_self_status(self):
        content = self.procfs.read("self/status")
        self.assertIn("Pid:", content)
        self.assertIn("VmRSS:", content)

    def test_exists(self):
        self.assertTrue(self.procfs.exists("uptime"))
        self.assertTrue(self.procfs.exists("self/status"))
        self.assertFalse(self.procfs.exists("nonexistent"))

    def test_read_unknown(self):
        result = self.procfs.read("nonexistent")
        self.assertIsNone(result)


# ──────────────────────────────────────────────────────────────────────────────
# CLI Parser tests for new commands
# ──────────────────────────────────────────────────────────────────────────────

class TestCLIParser(unittest.TestCase):

    def setUp(self):
        from aura_os.engine.cli import build_parser
        self.parser = build_parser()

    def test_ps_command(self):
        args = self.parser.parse_args(["ps"])
        self.assertEqual(args.command, "ps")

    def test_kill_command(self):
        args = self.parser.parse_args(["kill", "1234"])
        self.assertEqual(args.command, "kill")
        self.assertEqual(args.pid, 1234)

    def test_kill_with_signal(self):
        args = self.parser.parse_args(["kill", "-s", "9", "5678"])
        self.assertEqual(args.signal_num, 9)
        self.assertEqual(args.pid, 5678)

    def test_service_list(self):
        args = self.parser.parse_args(["service", "list"])
        self.assertEqual(args.svc_command, "list")

    def test_service_start(self):
        args = self.parser.parse_args(["service", "start", "myservice"])
        self.assertEqual(args.svc_command, "start")
        self.assertEqual(args.name, "myservice")

    def test_service_create(self):
        args = self.parser.parse_args([
            "service", "create", "web", "--cmd", "python3 -m http.server"
        ])
        self.assertEqual(args.svc_command, "create")
        self.assertEqual(args.name, "web")
        self.assertEqual(args.cmd, "python3 -m http.server")

    def test_log_tail(self):
        args = self.parser.parse_args(["log", "tail", "-n", "50"])
        self.assertEqual(args.log_command, "tail")
        self.assertEqual(args.lines, 50)

    def test_log_search(self):
        args = self.parser.parse_args(["log", "search", "error"])
        self.assertEqual(args.log_command, "search")
        self.assertEqual(args.pattern, "error")

    def test_log_clear(self):
        args = self.parser.parse_args(["log", "clear"])
        self.assertEqual(args.log_command, "clear")


# ──────────────────────────────────────────────────────────────────────────────
# Shell helper function tests
# ──────────────────────────────────────────────────────────────────────────────

class TestShellHelpers(unittest.TestCase):

    def test_expand_env_vars(self):
        from aura_os.main import _expand_env_vars
        env = {"HOME": "/home/user", "USER": "testuser"}
        self.assertEqual(_expand_env_vars("hello $USER", env), "hello testuser")
        self.assertEqual(_expand_env_vars("${HOME}/bin", env), "/home/user/bin")
        self.assertEqual(_expand_env_vars("no vars", env), "no vars")
        self.assertEqual(_expand_env_vars("$MISSING", env), "")

    def test_expand_env_vars_multiple(self):
        from aura_os.main import _expand_env_vars
        env = {"A": "1", "B": "2"}
        self.assertEqual(_expand_env_vars("$A and $B", env), "1 and 2")

    def test_expand_env_vars_mixed(self):
        from aura_os.main import _expand_env_vars
        env = {"NAME": "world"}
        self.assertEqual(_expand_env_vars("hello ${NAME}!", env), "hello world!")


# ──────────────────────────────────────────────────────────────────────────────
# Router integration tests for new commands
# ──────────────────────────────────────────────────────────────────────────────

class TestRouterNewCommands(unittest.TestCase):

    def setUp(self):
        from aura_os.main import _build_router
        self.router = _build_router()

    def test_all_commands_registered(self):
        for cmd in ("run", "ai", "env", "pkg", "sys", "ps", "kill", "service", "log"):
            self.assertIn(cmd, self.router._handlers)


if __name__ == "__main__":
    unittest.main(verbosity=2)
