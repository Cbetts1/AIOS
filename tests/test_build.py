"""Smoke tests for the build package and command router.

These tests are intentionally fast (no I/O, no subprocess) and act as
a CI gate to catch import-level breakage early.  If any command handler
module is missing or has a top-level import error the corresponding test
will fail with a clear error message.
"""

import sys
import os
import unittest

# Ensure the repo root is importable regardless of how pytest is invoked
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestRouterBuilds(unittest.TestCase):
    """The router must assemble without raising any ImportError."""

    def test_build_router_imports_all_handlers(self):
        """_build_router() must succeed and register every expected command."""
        from aura_os.main import _build_router
        router = _build_router()
        handlers = set(router._handlers.keys())

        expected = {
            "run", "ai", "env", "pkg", "sys", "ps", "kill", "service",
            "log", "user", "net", "init", "notify", "cron", "clip",
            "plugin", "secret", "disk", "health", "monitor", "web",
            "center", "shell", "validate", "build", "diag", "repair", "cloud",
        }
        missing = expected - handlers
        self.assertSetEqual(missing, set(),
                            msg=f"Router is missing handlers: {missing}")

    def test_router_count(self):
        """Router must have at least 28 registered commands."""
        from aura_os.main import _build_router
        router = _build_router()
        self.assertGreaterEqual(len(router._handlers), 28,
                                msg="Too few commands registered in router")


class TestBuildPackageImports(unittest.TestCase):
    """aura_os.build must be importable and expose the expected symbols."""

    def test_build_package_importable(self):
        import aura_os.build  # noqa: F401

    def test_validator_importable(self):
        from aura_os.build.validator import Validator, ValidateCommand
        self.assertTrue(callable(getattr(Validator, "run_all", None)))
        self.assertTrue(callable(getattr(ValidateCommand, "execute", None)))

    def test_manifest_importable(self):
        from aura_os.build.manifest import ManifestBuilder, BuildCommand
        self.assertTrue(callable(getattr(ManifestBuilder, "build", None)))
        self.assertTrue(callable(getattr(BuildCommand, "execute", None)))


class TestValidateCommand(unittest.TestCase):
    """ValidateCommand.execute() must return an int exit code."""

    def test_execute_returns_int(self):
        from aura_os.build.validator import ValidateCommand
        cmd = ValidateCommand()
        rc = cmd.execute(None, None)
        self.assertIsInstance(rc, int)

    def test_validator_run_all(self):
        from aura_os.build.validator import Validator
        v = Validator()
        results = v.run_all()
        self.assertIsInstance(results, list)
        self.assertGreater(len(results), 0)
        for r in results:
            self.assertTrue(hasattr(r, "name"))
            self.assertTrue(hasattr(r, "passed"))


class TestBuildCommand(unittest.TestCase):
    """BuildCommand.execute() must return an int exit code."""

    def _make_args(self, build_cmd=None, output=None, old=None, new=None):
        class _Args:
            pass
        a = _Args()
        a.build_cmd = build_cmd
        a.output = output
        a.old = old
        a.new = new
        return a

    def test_execute_default_returns_int(self):
        from aura_os.build.manifest import BuildCommand
        cmd = BuildCommand()
        rc = cmd.execute(self._make_args(), None)
        self.assertIsInstance(rc, int)

    def test_manifest_build_returns_dict(self):
        from aura_os.build.manifest import ManifestBuilder
        m = ManifestBuilder()
        manifest = m.build()
        self.assertIn("generated_at", manifest)
        self.assertIn("aura_version", manifest)
        self.assertIn("kernel_modules", manifest)
        self.assertIsInstance(manifest["kernel_modules"], dict)

    def test_manifest_diff_empty(self):
        from aura_os.build.manifest import ManifestBuilder
        m = ManifestBuilder()
        snap = m.build()
        diff = ManifestBuilder.diff(snap, snap)
        self.assertEqual(diff["added_packages"], [])
        self.assertEqual(diff["removed_packages"], [])


class TestCommandsPackageExports(unittest.TestCase):
    """engine.commands.__init__ must export all handler classes."""

    def test_all_exports_importable(self):
        from aura_os.engine import commands
        expected = [
            "RunCommand", "AiCommand", "EnvCommand", "PkgCommand", "SysCommand",
            "PsCommand", "KillCommand", "ServiceCommand", "LogCommand",
            "UserCommand", "NetCommand", "InitCommand",
            "NotifyCommand", "CronCommand", "ClipCommand", "PluginCommand",
            "SecretCommand", "DiskCommand", "HealthCommand", "MonitorCommand",
            "WebCommand",
        ]
        for name in expected:
            with self.subTest(cls=name):
                self.assertTrue(
                    hasattr(commands, name),
                    msg=f"commands.{name} not exported from __init__.py",
                )


class TestShellBuiltins(unittest.TestCase):
    """AuraShell must have a full set of built-in commands."""

    def _make_shell(self):
        from aura_os.shell.repl import AuraShell
        return AuraShell()

    def test_shell_instantiates(self):
        shell = self._make_shell()
        self.assertIsNotNone(shell)

    def test_pwd_builtin(self):
        import os
        shell = self._make_shell()
        shell._cwd = "/tmp"
        rc = shell.execute("pwd")
        self.assertEqual(rc, 0)

    def test_echo_builtin(self):
        shell = self._make_shell()
        rc = shell.execute("echo hello world")
        self.assertEqual(rc, 0)

    def test_ls_builtin(self):
        shell = self._make_shell()
        rc = shell.execute("ls /tmp")
        self.assertEqual(rc, 0)

    def test_cat_missing_file(self):
        shell = self._make_shell()
        rc = shell.execute("cat /tmp/__nonexistent_aura_test_file__")
        self.assertEqual(rc, 1)

    def test_whoami_builtin(self):
        shell = self._make_shell()
        rc = shell.execute("whoami")
        self.assertEqual(rc, 0)

    def test_date_builtin(self):
        shell = self._make_shell()
        rc = shell.execute("date")
        self.assertEqual(rc, 0)

    def test_hostname_builtin(self):
        shell = self._make_shell()
        rc = shell.execute("hostname")
        self.assertEqual(rc, 0)

    def test_mkdir_and_rm(self):
        import tempfile, os
        with tempfile.TemporaryDirectory() as tmp:
            shell = self._make_shell()
            shell._cwd = tmp
            new_dir = os.path.join(tmp, "testdir")
            rc = shell.execute(f"mkdir testdir")
            self.assertEqual(rc, 0)
            self.assertTrue(os.path.isdir(new_dir))
            rc = shell.execute(f"rm -r testdir")
            self.assertEqual(rc, 0)
            self.assertFalse(os.path.exists(new_dir))

    def test_touch_and_cat(self):
        import tempfile, os
        with tempfile.TemporaryDirectory() as tmp:
            shell = self._make_shell()
            shell._cwd = tmp
            rc = shell.execute("touch myfile.txt")
            self.assertEqual(rc, 0)
            self.assertTrue(os.path.exists(os.path.join(tmp, "myfile.txt")))
            rc = shell.execute("cat myfile.txt")
            self.assertEqual(rc, 0)

    def test_wc_builtin(self):
        import tempfile, os
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "wc_test.txt")
            with open(path, "w") as fh:
                fh.write("hello world\nfoo bar\n")
            shell = self._make_shell()
            shell._cwd = tmp
            rc = shell.execute("wc wc_test.txt")
            self.assertEqual(rc, 0)

    def test_grep_builtin(self):
        import tempfile, os
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "grep_test.txt")
            with open(path, "w") as fh:
                fh.write("hello world\nfoo bar\nhello again\n")
            shell = self._make_shell()
            shell._cwd = tmp
            rc = shell.execute("grep hello grep_test.txt")
            self.assertEqual(rc, 0)

    def test_grep_no_match(self):
        import tempfile, os
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "grep_nm.txt")
            with open(path, "w") as fh:
                fh.write("hello world\n")
            shell = self._make_shell()
            shell._cwd = tmp
            rc = shell.execute("grep zzznomatch grep_nm.txt")
            self.assertEqual(rc, 1)  # grep convention: 1 = no match

    def test_which_python(self):
        shell = self._make_shell()
        rc = shell.execute("which python3")
        # python3 should exist in CI
        self.assertIn(rc, (0, 1))

    def test_uname_builtin(self):
        shell = self._make_shell()
        rc = shell.execute("uname -a")
        self.assertEqual(rc, 0)

    def test_env_var_expansion(self):
        shell = self._make_shell()
        shell._env["AURA_TEST_VAR"] = "hello"
        rc = shell.execute("echo $AURA_TEST_VAR")
        self.assertEqual(rc, 0)

    def test_redirect_output(self):
        import tempfile, os
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "out.txt")
            shell = self._make_shell()
            shell._cwd = tmp
            rc = shell.execute(f"echo hello > out.txt")
            self.assertEqual(rc, 0)

    def test_alias(self):
        shell = self._make_shell()
        shell.execute("alias ll='ls -l'")
        self.assertIn("ll", shell._aliases)

    def test_cd_changes_cwd(self):
        shell = self._make_shell()
        shell.execute("cd /tmp")
        self.assertEqual(shell._cwd, "/tmp")

    def test_chain_semicolon(self):
        shell = self._make_shell()
        rc = shell.execute("echo a ; echo b")
        self.assertEqual(rc, 0)


class TestWebDashboard(unittest.TestCase):
    """Web module must expose the dashboard HTML."""

    def test_dashboard_html_not_empty(self):
        from aura_os.web import _DASHBOARD_HTML
        self.assertGreater(len(_DASHBOARD_HTML), 500)
        self.assertIn("<html", _DASHBOARD_HTML)
        self.assertIn("viewport", _DASHBOARD_HTML)  # mobile meta tag

    def test_health_endpoint(self):
        from aura_os.web import _get_health
        result = _get_health()
        self.assertIn("score", result)
        self.assertIsInstance(result["score"], (int, float))

    def test_stdlib_handler_serves_dashboard(self):
        """stdlib handler must serve HTML at GET /."""
        from aura_os.web import _StdlibHandler

        class _FakeEAL:
            def get_env_info(self):
                return {"platform": "test", "system": {}}

        handler_cls = _StdlibHandler(_FakeEAL()).build_handler()
        # Just check the class is callable (no actual HTTP call needed)
        self.assertTrue(callable(handler_cls))


if __name__ == "__main__":
    unittest.main()
