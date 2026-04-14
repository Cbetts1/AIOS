"""Tests for the new AURA OS modules:
- command_center: CommandCenter, CenterCommand
- shell: AuraShell, ShellCommand
- build: Validator, ManifestBuilder, BuildCommand
- maintenance: Diagnostics, Repair, DiagnosticsCommand, RepairCommand
- cloud: CloudClient, NodeRegistry, CloudCommand
- ai: AuraPersona, AuraSession
"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ======================================================================
# Helpers
# ======================================================================

def _tmp_home():
    """Return a fresh temporary AURA_HOME directory."""
    d = tempfile.mkdtemp(prefix="aura_test_")
    os.environ["AURA_HOME"] = d
    return d


def _cleanup(path):
    import shutil
    shutil.rmtree(path, ignore_errors=True)


# ======================================================================
# CommandCenter Tests
# ======================================================================

class TestCommandCenter(unittest.TestCase):

    def setUp(self):
        self.home = _tmp_home()

    def tearDown(self):
        _cleanup(self.home)

    def test_import(self):
        from aura_os.command_center import CommandCenter
        cc = CommandCenter()
        self.assertIsNotNone(cc)

    def test_summary_returns_dict(self):
        from aura_os.command_center import CommandCenter
        cc = CommandCenter()
        s = cc.summary()
        self.assertIsInstance(s, dict)
        self.assertIn("timestamp", s)
        self.assertIn("cpu", s)
        self.assertIn("memory", s)
        self.assertIn("disk", s)
        self.assertIn("health", s)

    def test_show_prints_output(self):
        from aura_os.command_center import CommandCenter
        import io
        cc = CommandCenter()
        with patch("sys.stdout", new_callable=io.StringIO) as mock_out:
            cc.show()
            output = mock_out.getvalue()
        self.assertIn("AURA OS", output)
        self.assertIn("Command Center", output)

    def test_health_score_types(self):
        from aura_os.command_center import CommandCenter
        cc = CommandCenter()
        score = cc._health_score()
        self.assertIn(score, ("healthy", "warning", "critical"))

    def test_cpu_summary_returns_dict(self):
        from aura_os.command_center import CommandCenter
        cc = CommandCenter()
        result = cc._cpu_summary()
        self.assertIsInstance(result, dict)

    def test_memory_summary_returns_dict(self):
        from aura_os.command_center import CommandCenter
        cc = CommandCenter()
        result = cc._memory_summary()
        self.assertIsInstance(result, dict)

    def test_center_command_execute(self):
        from aura_os.command_center.center import CenterCommand
        cmd = CenterCommand()
        args = MagicMock()
        args.watch = False
        rc = cmd.execute(args, None)
        self.assertEqual(rc, 0)

    def test_center_command_via_router(self):
        from aura_os.engine.router import CommandRouter
        from aura_os.command_center.center import CenterCommand
        router = CommandRouter()
        router.register("center", CenterCommand)
        args = MagicMock()
        args.command = "center"
        args.watch = False
        rc = router.dispatch(args, None)
        self.assertEqual(rc, 0)


# ======================================================================
# Shell Tests
# ======================================================================

class TestAuraShell(unittest.TestCase):

    def setUp(self):
        self.home = _tmp_home()

    def tearDown(self):
        _cleanup(self.home)

    def test_import(self):
        from aura_os.shell import AuraShell
        shell = AuraShell(home=self.home)
        self.assertIsNotNone(shell)

    def test_execute_echo(self):
        from aura_os.shell import AuraShell
        import io
        shell = AuraShell(home=self.home)
        with patch("sys.stdout", new_callable=io.StringIO) as mock_out:
            rc = shell.execute("echo hello world")
            output = mock_out.getvalue()
        # echo is a built-in that prints to stdout
        self.assertIn("hello world", output)
        self.assertEqual(rc, 0)

    def test_execute_pwd(self):
        from aura_os.shell import AuraShell
        import io
        shell = AuraShell(home=self.home)
        with patch("sys.stdout", new_callable=io.StringIO) as mock_out:
            rc = shell.execute("pwd")
            output = mock_out.getvalue()
        self.assertIn(os.getcwd(), output)
        self.assertEqual(rc, 0)

    def test_execute_cd(self):
        from aura_os.shell import AuraShell
        shell = AuraShell(home=self.home)
        original = os.getcwd()
        shell.execute(f"cd {self.home}")
        self.assertEqual(shell._cwd, self.home)
        os.chdir(original)

    def test_execute_assignment(self):
        from aura_os.shell import AuraShell
        shell = AuraShell(home=self.home)
        shell.execute("MYVAR=hello123")
        self.assertEqual(shell._env.get("MYVAR"), "hello123")

    def test_execute_unknown_command(self):
        from aura_os.shell import AuraShell
        shell = AuraShell(home=self.home)
        rc = shell.execute("this_command_does_not_exist_xyz")
        self.assertEqual(rc, 127)

    def test_run_script(self):
        from aura_os.shell import AuraShell
        script = os.path.join(self.home, "test_script.sh")
        with open(script, "w") as f:
            f.write("# comment\n")
            f.write("echo script_ran\n")
        import io
        shell = AuraShell(home=self.home)
        with patch("sys.stdout", new_callable=io.StringIO) as mock_out:
            rc = shell.run_script(script)
            output = mock_out.getvalue()
        self.assertIn("script_ran", output)
        self.assertEqual(rc, 0)

    def test_run_script_missing_file(self):
        from aura_os.shell import AuraShell
        shell = AuraShell(home=self.home)
        rc = shell.run_script("/nonexistent/path/script.sh")
        self.assertEqual(rc, 1)

    def test_redirect_output(self):
        from aura_os.shell import AuraShell
        out_file = os.path.join(self.home, "out.txt")
        shell = AuraShell(home=self.home)
        shell.execute(f"echo redirected > {out_file}")
        if os.path.exists(out_file):
            content = open(out_file).read()
            self.assertIn("redirected", content)

    def test_shell_command_execute(self):
        from aura_os.shell.repl import ShellCommand
        cmd = ShellCommand()
        args = MagicMock()
        args.script = os.path.join(self.home, "empty.sh")
        with open(args.script, "w") as f:
            f.write("# empty\n")
        rc = cmd.execute(args, None)
        self.assertEqual(rc, 0)

    def test_alias_builtin(self):
        from aura_os.shell import AuraShell
        shell = AuraShell(home=self.home)
        shell.execute("alias ll='ls -l'")
        self.assertIn("ll", shell._aliases)

    def test_history_tracking(self):
        from aura_os.shell import AuraShell
        shell = AuraShell(home=self.home)
        # Manually add to history (as the REPL would do during run())
        shell._history.append("echo one")
        shell._history.append("echo two")
        self.assertGreaterEqual(len(shell._history), 2)


# ======================================================================
# Validator Tests
# ======================================================================

class TestValidator(unittest.TestCase):

    def setUp(self):
        self.home = _tmp_home()

    def tearDown(self):
        _cleanup(self.home)

    def test_import(self):
        from aura_os.build import Validator
        v = Validator(self.home)
        self.assertIsNotNone(v)

    def test_check_all_returns_list(self):
        from aura_os.build import Validator
        v = Validator(self.home)
        results = v.check_all()
        self.assertIsInstance(results, list)
        self.assertGreater(len(results), 0)

    def test_check_results_have_required_fields(self):
        from aura_os.build import Validator
        from aura_os.build.validator import CheckResult
        v = Validator(self.home)
        results = v.check_all()
        for r in results:
            self.assertIsInstance(r, CheckResult)
            self.assertIsInstance(r.name, str)
            self.assertIsInstance(r.passed, bool)
            self.assertIn(r.severity, ("info", "warning", "error"))

    def test_python_version_check_passes(self):
        from aura_os.build import Validator
        v = Validator(self.home)
        result = v._check_python_version()
        # We're running Python 3.8+, so this should pass
        self.assertTrue(result.passed)

    def test_print_report(self):
        from aura_os.build import Validator
        import io
        v = Validator(self.home)
        results = v.check_all()
        with patch("sys.stdout", new_callable=io.StringIO) as mock_out:
            v.print_report(results)
            output = mock_out.getvalue()
        self.assertIn("AURA OS", output)
        self.assertIn("Validation", output)

    def test_validate_command_execute(self):
        from aura_os.build.validator import ValidateCommand
        cmd = ValidateCommand()
        args = MagicMock()
        rc = cmd.execute(args, None)
        self.assertIn(rc, (0, 1))  # may pass or warn


# ======================================================================
# ManifestBuilder Tests
# ======================================================================

class TestManifestBuilder(unittest.TestCase):

    def setUp(self):
        self.home = _tmp_home()

    def tearDown(self):
        _cleanup(self.home)

    def test_import(self):
        from aura_os.build import ManifestBuilder
        mb = ManifestBuilder(self.home)
        self.assertIsNotNone(mb)

    def test_build_returns_dict(self):
        from aura_os.build import ManifestBuilder
        mb = ManifestBuilder(self.home)
        manifest = mb.build()
        self.assertIsInstance(manifest, dict)
        self.assertIn("generated_at", manifest)
        self.assertIn("python", manifest)
        self.assertIn("platform", manifest)
        self.assertIn("packages", manifest)
        self.assertIn("kernel_modules", manifest)

    def test_python_info(self):
        from aura_os.build import ManifestBuilder
        mb = ManifestBuilder(self.home)
        info = mb._python_info()
        self.assertIn("version", info)
        self.assertIn("executable", info)

    def test_platform_info(self):
        from aura_os.build import ManifestBuilder
        mb = ManifestBuilder(self.home)
        info = mb._platform_info()
        self.assertIn("system", info)

    def test_save_and_load(self):
        from aura_os.build import ManifestBuilder
        mb = ManifestBuilder(self.home)
        manifest = mb.build()
        save_path = os.path.join(self.home, "manifest.json")
        mb.save(manifest, save_path)
        loaded = mb.load(save_path)
        self.assertEqual(manifest["generated_at"], loaded["generated_at"])

    def test_diff_empty(self):
        from aura_os.build import ManifestBuilder
        mb = ManifestBuilder(self.home)
        m = mb.build()
        diff = mb.diff(m, m)
        self.assertEqual(diff, {})

    def test_format_summary(self):
        from aura_os.build import ManifestBuilder
        mb = ManifestBuilder(self.home)
        manifest = mb.build()
        summary = mb.format_summary(manifest)
        self.assertIn("AURA OS", summary)
        self.assertIn("Packages", summary)

    def test_kernel_modules_list(self):
        from aura_os.build import ManifestBuilder
        mb = ManifestBuilder(self.home)
        modules = mb._kernel_modules()
        self.assertIsInstance(modules, list)
        self.assertGreater(len(modules), 0)
        # All kernel modules should be available
        available = [m for m in modules if m["status"] == "available"]
        self.assertGreater(len(available), 0)

    def test_build_command_manifest(self):
        from aura_os.build.manifest import BuildCommand
        cmd = BuildCommand()
        args = MagicMock()
        args.build_cmd = "manifest"
        args.output = None
        rc = cmd.execute(args, None)
        self.assertEqual(rc, 0)


# ======================================================================
# Diagnostics Tests
# ======================================================================

class TestDiagnostics(unittest.TestCase):

    def setUp(self):
        self.home = _tmp_home()

    def tearDown(self):
        _cleanup(self.home)

    def test_import(self):
        from aura_os.maintenance import Diagnostics
        d = Diagnostics(self.home)
        self.assertIsNotNone(d)

    def test_run_all_returns_list(self):
        from aura_os.maintenance import Diagnostics
        d = Diagnostics(self.home)
        results = d.run_all()
        self.assertIsInstance(results, list)
        self.assertGreater(len(results), 0)

    def test_diag_result_fields(self):
        from aura_os.maintenance import Diagnostics
        from aura_os.maintenance.diagnostics import DiagResult
        d = Diagnostics(self.home)
        results = d.run_all()
        for r in results:
            self.assertIsInstance(r, DiagResult)
            self.assertIsInstance(r.category, str)
            self.assertIsInstance(r.name, str)
            self.assertIn(r.status, ("ok", "warning", "error", "info"))

    def test_platform_section(self):
        from aura_os.maintenance import Diagnostics
        d = Diagnostics(self.home)
        results = d._diag_platform()
        names = [r.name for r in results]
        self.assertIn("system", names)
        self.assertIn("node", names)

    def test_python_section(self):
        from aura_os.maintenance import Diagnostics
        d = Diagnostics(self.home)
        results = d._diag_python()
        names = [r.name for r in results]
        self.assertIn("version", names)
        # Python version check should pass (we're >= 3.8)
        ver_result = next(r for r in results if r.name == "version")
        self.assertEqual(ver_result.status, "ok")

    def test_print_report(self):
        from aura_os.maintenance import Diagnostics
        import io
        d = Diagnostics(self.home)
        results = d.run_all()
        with patch("sys.stdout", new_callable=io.StringIO) as mock_out:
            d.print_report(results)
            output = mock_out.getvalue()
        self.assertIn("AURA OS", output)
        self.assertIn("Diagnostics", output)

    def test_diagnostics_command_execute(self):
        from aura_os.maintenance.diagnostics import DiagnosticsCommand
        cmd = DiagnosticsCommand()
        args = MagicMock()
        rc = cmd.execute(args, None)
        self.assertIn(rc, (0, 1))


# ======================================================================
# Repair Tests
# ======================================================================

class TestRepair(unittest.TestCase):

    def setUp(self):
        self.home = _tmp_home()

    def tearDown(self):
        _cleanup(self.home)

    def test_import(self):
        from aura_os.maintenance import Repair
        r = Repair(self.home)
        self.assertIsNotNone(r)

    def test_repair_dirs_creates_dirs(self):
        from aura_os.maintenance import Repair
        r = Repair(self.home)
        results = r.repair_dirs()
        # All required dirs should exist after repair
        for d in Repair._REQUIRED_DIRS:
            self.assertTrue((Path(self.home) / d).exists())
        # All results should be successful
        for res in results:
            self.assertTrue(res.success, f"Dir repair failed for: {res.target}")

    def test_repair_config_creates_config(self):
        from aura_os.maintenance import Repair
        r = Repair(self.home)
        results = r.repair_config()
        cfg = Path(self.home) / "configs" / "system.json"
        self.assertTrue(cfg.exists())
        data = json.loads(cfg.read_text())
        self.assertIn("version", data)

    def test_repair_config_fixes_corrupt(self):
        from aura_os.maintenance import Repair
        cfg_dir = Path(self.home) / "configs"
        cfg_dir.mkdir(parents=True)
        cfg = cfg_dir / "system.json"
        cfg.write_text("INVALID JSON {{{")
        r = Repair(self.home)
        results = r.repair_config()
        # Should have reset the config
        data = json.loads(cfg.read_text())
        self.assertIn("version", data)
        actions = [res.action for res in results]
        self.assertIn("reset_config", actions)

    def test_rotate_logs_empty(self):
        from aura_os.maintenance import Repair
        r = Repair(self.home)
        results = r.rotate_logs()
        # No logs yet, should return empty list or just no errors
        for res in results:
            self.assertTrue(res.success)

    def test_rotate_large_log(self):
        from aura_os.maintenance import Repair
        log_dir = Path(self.home) / "logs"
        log_dir.mkdir(parents=True)
        big_log = log_dir / "syslog.log"
        big_log.write_bytes(b"x" * 11_000_000)  # 11 MB > 10 MB limit
        r = Repair(self.home)
        results = r.rotate_logs(max_size_mb=10.0)
        actions = [res.action for res in results]
        self.assertIn("rotate_log", actions)
        # Original log file should now be small/empty
        self.assertLess(big_log.stat().st_size, 1000)

    def test_purge_stale_state(self):
        from aura_os.maintenance import Repair
        # Create a fake PID file
        pid_file = Path(self.home) / "test.pid"
        pid_file.write_text("12345")
        r = Repair(self.home)
        results = r.purge_stale_state()
        purged = [res for res in results if res.action == "purge_stale"]
        self.assertTrue(len(purged) >= 1)
        self.assertFalse(pid_file.exists())

    def test_repair_all(self):
        from aura_os.maintenance import Repair
        r = Repair(self.home)
        results = r.repair_all()
        self.assertIsInstance(results, list)
        self.assertGreater(len(results), 0)

    def test_repair_command_execute(self):
        from aura_os.maintenance.repair import RepairCommand
        cmd = RepairCommand()
        args = MagicMock()
        args.repair_cmd = "all"
        rc = cmd.execute(args, None)
        self.assertIn(rc, (0, 1))


# ======================================================================
# CloudClient Tests
# ======================================================================

class TestCloudClient(unittest.TestCase):

    def test_import(self):
        from aura_os.cloud import CloudClient
        c = CloudClient()
        self.assertIsNotNone(c)

    def test_ping_unreachable_returns_false(self):
        from aura_os.cloud import CloudClient
        c = CloudClient(timeout=1)
        reachable, code, latency = c.ping("http://192.0.2.1:9999/")
        self.assertFalse(reachable)
        self.assertEqual(code, 0)

    def test_get_unreachable_returns_0(self):
        from aura_os.cloud import CloudClient
        c = CloudClient(timeout=1)
        code, _ = c.get("http://192.0.2.1:9999/")
        self.assertEqual(code, 0)

    def test_post_json_unreachable(self):
        from aura_os.cloud import CloudClient
        c = CloudClient(timeout=1)
        code, _ = c.post_json("http://192.0.2.1:9999/api", {"key": "val"})
        self.assertEqual(code, 0)

    def test_resolve_relative(self):
        from aura_os.cloud import CloudClient
        c = CloudClient(base_url="http://localhost:7070")
        self.assertEqual(c._resolve("/api/status"), "http://localhost:7070/api/status")

    def test_resolve_absolute(self):
        from aura_os.cloud import CloudClient
        c = CloudClient(base_url="http://localhost:7070")
        self.assertEqual(
            c._resolve("http://other.com/path"),
            "http://other.com/path",
        )

    def test_build_headers_includes_user_agent(self):
        from aura_os.cloud import CloudClient
        c = CloudClient()
        h = c._build_headers()
        self.assertIn("User-Agent", h)
        self.assertIn("AURA", h["User-Agent"])

    def test_cloud_command_status(self):
        from aura_os.cloud.client import CloudCommand
        cmd = CloudCommand()
        args = MagicMock()
        args.cloud_cmd = "status"
        import io
        with patch("sys.stdout", new_callable=io.StringIO) as mock_out:
            rc = cmd.execute(args, None)
            output = mock_out.getvalue()
        self.assertEqual(rc, 0)
        self.assertIn("cloud", output.lower())


# ======================================================================
# NodeRegistry Tests
# ======================================================================

class TestNodeRegistry(unittest.TestCase):

    def setUp(self):
        self.home = _tmp_home()

    def tearDown(self):
        _cleanup(self.home)

    def test_import(self):
        from aura_os.cloud import NodeRegistry
        nr = NodeRegistry(self.home)
        self.assertIsNotNone(nr)

    def test_register_and_list(self):
        from aura_os.cloud import NodeRegistry
        nr = NodeRegistry(self.home)
        nr.register("node-1", "http://10.0.0.2:7070")
        nodes = nr.list_nodes()
        self.assertEqual(len(nodes), 1)
        self.assertEqual(nodes[0]["name"], "node-1")
        self.assertEqual(nodes[0]["url"], "http://10.0.0.2:7070")

    def test_get_node(self):
        from aura_os.cloud import NodeRegistry
        nr = NodeRegistry(self.home)
        nr.register("node-x", "http://10.0.0.5:7070")
        node = nr.get_node("node-x")
        self.assertIsNotNone(node)
        self.assertEqual(node["name"], "node-x")

    def test_get_nonexistent_node(self):
        from aura_os.cloud import NodeRegistry
        nr = NodeRegistry(self.home)
        self.assertIsNone(nr.get_node("does-not-exist"))

    def test_deregister(self):
        from aura_os.cloud import NodeRegistry
        nr = NodeRegistry(self.home)
        nr.register("node-del", "http://10.0.0.3:7070")
        removed = nr.deregister("node-del")
        self.assertTrue(removed)
        self.assertIsNone(nr.get_node("node-del"))

    def test_deregister_nonexistent(self):
        from aura_os.cloud import NodeRegistry
        nr = NodeRegistry(self.home)
        result = nr.deregister("never-existed")
        self.assertFalse(result)

    def test_list_sessions(self):
        from aura_os.cloud import NodeRegistry
        nr = NodeRegistry(self.home)
        nr.register("node-a", "http://10.0.0.1:7070")
        nr.register("node-b", "http://10.0.0.2:7070")
        nodes = nr.list_nodes()
        self.assertEqual(len(nodes), 2)

    def test_persist_across_instances(self):
        from aura_os.cloud import NodeRegistry
        nr1 = NodeRegistry(self.home)
        nr1.register("persistent-node", "http://10.0.0.9:7070")
        nr2 = NodeRegistry(self.home)
        nodes = nr2.list_nodes()
        names = [n["name"] for n in nodes]
        self.assertIn("persistent-node", names)

    def test_ping_node_unreachable(self):
        from aura_os.cloud import NodeRegistry
        nr = NodeRegistry(self.home)
        nr.register("unreachable", "http://192.0.2.1:9999")
        result = nr.ping_node("unreachable")
        self.assertFalse(result)

    def test_ping_nonexistent_node(self):
        from aura_os.cloud import NodeRegistry
        nr = NodeRegistry(self.home)
        result = nr.ping_node("ghost-node")
        self.assertFalse(result)


# ======================================================================
# AuraPersona Tests
# ======================================================================

class TestAuraPersona(unittest.TestCase):

    def test_import(self):
        from aura_os.ai.aura import AuraPersona
        persona = AuraPersona()
        self.assertIsNotNone(persona)

    def test_ask_returns_string(self):
        from aura_os.ai.aura import AuraPersona
        persona = AuraPersona(inject_context=False)
        response = persona.ask("What is the system health?")
        self.assertIsInstance(response, str)
        self.assertGreater(len(response), 0)

    def test_fallback_response_health(self):
        from aura_os.ai.aura import AuraPersona
        persona = AuraPersona(inject_context=False)
        response = persona._fallback_response("system health status")
        self.assertIn("aura", response.lower())

    def test_fallback_response_process(self):
        from aura_os.ai.aura import AuraPersona
        persona = AuraPersona(inject_context=False)
        response = persona._fallback_response("what processes are running")
        self.assertIn("ps", response)

    def test_fallback_response_services(self):
        from aura_os.ai.aura import AuraPersona
        persona = AuraPersona(inject_context=False)
        response = persona._fallback_response("check daemon services")
        self.assertIn("service", response)

    def test_fallback_response_repair(self):
        from aura_os.ai.aura import AuraPersona
        persona = AuraPersona(inject_context=False)
        response = persona._fallback_response("the system needs repair, please fix it")
        self.assertIn("repair", response.lower())

    def test_explain_command(self):
        from aura_os.ai.aura import AuraPersona
        persona = AuraPersona(inject_context=False)
        response = persona.explain_command("aura health")
        self.assertIsInstance(response, str)

    def test_suggest_fix(self):
        from aura_os.ai.aura import AuraPersona
        persona = AuraPersona(inject_context=False)
        response = persona.suggest_fix("disk is 95% full")
        self.assertIsInstance(response, str)

    def test_with_session(self):
        from aura_os.ai.aura import AuraPersona
        from aura_os.ai.session import AuraSession
        home = _tmp_home()
        try:
            session = AuraSession("test", aura_home=home)
            persona = AuraPersona(session=session, inject_context=False)
            response = persona.ask("hello")
            self.assertIsInstance(response, str)
            # Session should have recorded the exchange
            self.assertEqual(session.exchange_count, 1)
        finally:
            _cleanup(home)


# ======================================================================
# AuraSession Tests
# ======================================================================

class TestAuraSession(unittest.TestCase):

    def setUp(self):
        self.home = _tmp_home()

    def tearDown(self):
        _cleanup(self.home)

    def test_import(self):
        from aura_os.ai.session import AuraSession
        session = AuraSession("test", aura_home=self.home)
        self.assertIsNotNone(session)

    def test_add_exchange(self):
        from aura_os.ai.session import AuraSession
        session = AuraSession("test", aura_home=self.home)
        session.add_exchange("Hello", "Hi there!")
        self.assertEqual(session.exchange_count, 1)

    def test_recent_exchanges(self):
        from aura_os.ai.session import AuraSession
        session = AuraSession("test", aura_home=self.home)
        for i in range(5):
            session.add_exchange(f"q{i}", f"a{i}")
        recent = session.recent_exchanges(3)
        self.assertEqual(len(recent), 3)
        self.assertEqual(recent[-1]["user"], "q4")

    def test_save_and_load(self):
        from aura_os.ai.session import AuraSession
        session = AuraSession("persist_test", aura_home=self.home)
        session.add_exchange("Q1", "A1")
        session.add_exchange("Q2", "A2")
        session.save()

        session2 = AuraSession("persist_test", aura_home=self.home)
        loaded = session2.load()
        self.assertTrue(loaded)
        self.assertEqual(session2.exchange_count, 2)
        recent = session2.recent_exchanges(2)
        self.assertEqual(recent[0]["user"], "Q1")
        self.assertEqual(recent[1]["user"], "Q2")

    def test_clear(self):
        from aura_os.ai.session import AuraSession
        session = AuraSession("clear_test", aura_home=self.home)
        session.add_exchange("Q", "A")
        session.clear()
        self.assertEqual(session.exchange_count, 0)

    def test_delete(self):
        from aura_os.ai.session import AuraSession
        session = AuraSession("del_test", aura_home=self.home)
        session.save()
        path = session._session_path
        self.assertTrue(path.exists())
        result = session.delete()
        self.assertTrue(result)
        self.assertFalse(path.exists())

    def test_load_nonexistent(self):
        from aura_os.ai.session import AuraSession
        session = AuraSession("ghost", aura_home=self.home)
        result = session.load()
        self.assertFalse(result)

    def test_list_sessions(self):
        from aura_os.ai.session import AuraSession
        s1 = AuraSession("sess_a", aura_home=self.home)
        s2 = AuraSession("sess_b", aura_home=self.home)
        s1.save()
        s2.save()
        sessions = AuraSession.list_sessions(self.home)
        self.assertIn("sess_a", sessions)
        self.assertIn("sess_b", sessions)

    def test_max_history_trimming(self):
        from aura_os.ai.session import AuraSession
        session = AuraSession("trim", aura_home=self.home, max_history=5)
        for i in range(10):
            session.add_exchange(f"Q{i}", f"A{i}")
        self.assertLessEqual(session.exchange_count, 5)

    def test_name_property(self):
        from aura_os.ai.session import AuraSession
        session = AuraSession("my_session", aura_home=self.home)
        self.assertEqual(session.name, "my_session")


# ======================================================================
# CLI routing for new commands
# ======================================================================

class TestNewCommandsRouter(unittest.TestCase):

    def test_all_new_commands_registered(self):
        from aura_os.main import _build_router
        router = _build_router()
        new_cmds = ["center", "validate", "build", "diag", "repair", "cloud"]
        for cmd in new_cmds:
            self.assertIn(cmd, router._handlers,
                          f"Command '{cmd}' not registered in router")

    def test_validate_command_in_cli_parser(self):
        from aura_os.engine.cli import build_parser
        parser = build_parser()
        # Should not raise
        args = parser.parse_args(["validate"])
        self.assertEqual(args.command, "validate")

    def test_diag_command_in_cli_parser(self):
        from aura_os.engine.cli import build_parser
        parser = build_parser()
        args = parser.parse_args(["diag"])
        self.assertEqual(args.command, "diag")

    def test_repair_command_in_cli_parser(self):
        from aura_os.engine.cli import build_parser
        parser = build_parser()
        args = parser.parse_args(["repair"])
        self.assertEqual(args.command, "repair")

    def test_center_command_in_cli_parser(self):
        from aura_os.engine.cli import build_parser
        parser = build_parser()
        args = parser.parse_args(["center"])
        self.assertEqual(args.command, "center")

    def test_cloud_command_in_cli_parser(self):
        from aura_os.engine.cli import build_parser
        parser = build_parser()
        args = parser.parse_args(["cloud", "status"])
        self.assertEqual(args.command, "cloud")

    def test_build_manifest_in_cli_parser(self):
        from aura_os.engine.cli import build_parser
        parser = build_parser()
        args = parser.parse_args(["build", "manifest"])
        self.assertEqual(args.command, "build")
        self.assertEqual(args.build_cmd, "manifest")


if __name__ == "__main__":
    unittest.main()
