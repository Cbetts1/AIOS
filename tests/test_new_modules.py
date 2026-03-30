"""
Tests for new AURA OS modules: pkg, process, shell, permissions, macOS adapter.
"""

import os
import sys
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

# Ensure the project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault("AURA_HOME", str(Path(tempfile.gettempdir()) / "aura_test"))


# ──────────────────────────────────────────────────────────────────────────────
# Package Module tests
# ──────────────────────────────────────────────────────────────────────────────

class TestPkgModule(unittest.TestCase):

    def setUp(self):
        from eal import detect_environment, get_adapter
        from modules.pkg import PkgModule
        self.env = detect_environment()
        self.adapter = get_adapter(self.env)
        self.pkg = PkgModule(self.env, self.adapter)

    def test_init(self):
        self.assertIsNotNone(self.pkg)

    def test_catalog_not_empty(self):
        from modules.pkg import CATALOG
        self.assertGreater(len(CATALOG), 10)

    def test_catalog_entries_have_required_keys(self):
        from modules.pkg import CATALOG
        for name, entry in CATALOG.items():
            self.assertIn("description", entry, f"{name} missing description")
            self.assertIn("category", entry, f"{name} missing category")

    def test_search_returns_results(self):
        # Should not raise; prints to stdout
        self.pkg.search("curl")

    def test_search_no_results(self):
        self.pkg.search("xyznonexistent999")

    def test_catalog_prints(self):
        # Should not raise
        self.pkg.catalog()

    def test_info_known_package(self):
        self.pkg.info("curl")

    def test_info_unknown_package(self):
        self.pkg.info("xyznonexistent999")

    def test_resolve_catalog_package(self):
        # Internal method: should return a native name or None
        result = self.pkg._resolve("curl")
        # On any platform, curl should resolve to something
        self.assertIsNotNone(result)

    def test_resolve_unknown_package_passthrough(self):
        # Non-catalog packages should pass through as-is
        result = self.pkg._resolve("my-custom-pkg")
        self.assertEqual(result, "my-custom-pkg")

    def test_canonicalize_pm(self):
        from modules.pkg import PkgModule
        self.assertEqual(PkgModule._canonicalize_pm("apt-get"), "apt")
        self.assertEqual(PkgModule._canonicalize_pm("yum"), "dnf")
        self.assertEqual(PkgModule._canonicalize_pm("brew"), "brew")
        self.assertIsNone(PkgModule._canonicalize_pm(None))


# ──────────────────────────────────────────────────────────────────────────────
# Process Module tests
# ──────────────────────────────────────────────────────────────────────────────

class TestProcessModule(unittest.TestCase):

    def setUp(self):
        from eal import detect_environment, get_adapter
        from modules.process import ProcessModule
        self.env = detect_environment()
        self.adapter = get_adapter(self.env)
        self.proc = ProcessModule(self.env, self.adapter)

    def test_init(self):
        self.assertIsNotNone(self.proc)
        self.assertEqual(self.proc._next_job, 1)

    def test_ps_runs(self):
        # Should not raise
        self.proc.ps()

    def test_ps_user_only(self):
        self.proc.ps(user_only=True)

    def test_kill_nonexistent_pid(self):
        # Very large PID should not exist
        result = self.proc.kill(999999999)
        self.assertFalse(result)

    def test_jobs_empty(self):
        # Should not raise
        self.proc.jobs()

    def test_spawn_and_jobs(self):
        jid = self.proc.spawn(["sleep", "0.1"], name="test-sleep")
        self.assertEqual(jid, 1)
        self.proc.jobs()
        # Wait for it to finish
        import time
        time.sleep(0.3)
        self.proc.jobs()

    def test_stop_nonexistent_job(self):
        result = self.proc.stop_job(999)
        self.assertFalse(result)

    def test_spawn_and_stop(self):
        jid = self.proc.spawn(["sleep", "60"], name="long-sleep")
        result = self.proc.stop_job(jid)
        self.assertTrue(result)

    def test_top_runs(self):
        self.proc.top()

    def test_uptime_runs(self):
        self.proc.uptime()


# ──────────────────────────────────────────────────────────────────────────────
# Shell Module tests (non-interactive)
# ──────────────────────────────────────────────────────────────────────────────

class TestShellModule(unittest.TestCase):

    def setUp(self):
        from eal import detect_environment, get_adapter
        from modules.shell import ShellModule
        self.env = detect_environment()
        self.adapter = get_adapter(self.env)
        self.shell = ShellModule(self.env, self.adapter)

    def test_init(self):
        self.assertIsNotNone(self.shell)

    def test_banner_exists(self):
        self.assertIn("AURA OS", self.shell.BANNER)

    def test_history_path(self):
        self.assertIsNotNone(self.shell._history_path)

    def test_lazy_init_creates_engine(self):
        self.shell._lazy_init()
        self.assertIsNotNone(self.shell._engine)

    def test_completer(self):
        from modules.shell import _AuraCompleter
        c = _AuraCompleter(["help", "sys", "ai", "pkg", "shell"])
        # Exact prefix
        result = c.complete("he", 0)
        self.assertEqual(result, "help")
        # No match
        result = c.complete("zzz", 0)
        self.assertIsNone(result)


# ──────────────────────────────────────────────────────────────────────────────
# Permissions tests
# ──────────────────────────────────────────────────────────────────────────────

class TestPermissions(unittest.TestCase):

    def test_auto_approve(self):
        from core.permissions import check_permission
        self.assertTrue(check_permission("pkg_install", auto_approve=True))

    def test_dangerous_actions_defined(self):
        from core.permissions import DANGEROUS_ACTIONS
        self.assertIn("pkg_install", DANGEROUS_ACTIONS)
        self.assertIn("fs_delete", DANGEROUS_ACTIONS)
        self.assertIn("process_kill", DANGEROUS_ACTIONS)
        self.assertIn("host_shell", DANGEROUS_ACTIONS)

    def test_non_interactive_denied(self):
        """In test (piped) mode, permission should be denied."""
        from core.permissions import check_permission
        # stdin is not a tty during tests
        result = check_permission("pkg_install", "test package")
        self.assertFalse(result)

    def test_require_permission_raises(self):
        from core.permissions import require_permission
        with self.assertRaises(PermissionError):
            require_permission("sudo", "test")


# ──────────────────────────────────────────────────────────────────────────────
# macOS Adapter tests
# ──────────────────────────────────────────────────────────────────────────────

class TestMacOSAdapter(unittest.TestCase):

    def test_instantiate(self):
        from eal.adapters.macos import MacOSAdapter
        from eal import detect_environment
        env = detect_environment()
        adapter = MacOSAdapter(env)
        self.assertIsNotNone(adapter)

    def test_get_package_manager(self):
        from eal.adapters.macos import MacOSAdapter
        from eal import detect_environment
        env = detect_environment()
        adapter = MacOSAdapter(env)
        # Returns brew, port, or None depending on system
        pm = adapter.get_package_manager()
        self.assertIn(pm, ("brew", "port", None))

    def test_storage_info(self):
        from eal.adapters.macos import MacOSAdapter
        from eal import detect_environment
        env = detect_environment()
        adapter = MacOSAdapter(env)
        info = adapter.storage_info()
        self.assertIn("total_mb", info)
        self.assertIn("free_mb", info)

    def test_inherits_base(self):
        from eal.adapters.macos import MacOSAdapter
        from eal.adapters import BaseAdapter
        self.assertTrue(issubclass(MacOSAdapter, BaseAdapter))


# ──────────────────────────────────────────────────────────────────────────────
# Engine integration: new commands registered
# ──────────────────────────────────────────────────────────────────────────────

class TestEngineNewCommands(unittest.TestCase):

    def setUp(self):
        from core.engine import CommandEngine
        self.engine = CommandEngine()

    def test_new_commands_registered(self):
        names = self.engine.registry.names()
        for cmd in ("pkg", "ps", "kill", "top", "jobs", "shell"):
            self.assertIn(cmd, names, f"Missing command: {cmd}")

    def test_pkg_no_args(self):
        # Should not raise
        self.engine.run(["pkg"])

    def test_pkg_catalog(self):
        self.engine.run(["pkg", "catalog"])

    def test_pkg_search(self):
        self.engine.run(["pkg", "search", "curl"])

    def test_pkg_info(self):
        self.engine.run(["pkg", "info", "git"])

    def test_ps_runs(self):
        self.engine.run(["ps"])

    def test_top_runs(self):
        self.engine.run(["top"])

    def test_jobs_runs(self):
        self.engine.run(["jobs"])

    def test_kill_no_args(self):
        # Should print usage, not crash
        self.engine.run(["kill"])


# ──────────────────────────────────────────────────────────────────────────────
# AI module: new rules
# ──────────────────────────────────────────────────────────────────────────────

class TestAINewRules(unittest.TestCase):

    def setUp(self):
        from eal import detect_environment, get_adapter
        from modules.ai import AIModule
        env = detect_environment()
        adapter = get_adapter(env)
        self.ai = AIModule(env, adapter)

    def test_ai_knows_packages(self):
        result = self.ai.query("how do I install a package")
        self.assertIn("pkg", result.lower())

    def test_ai_knows_processes(self):
        result = self.ai.query("how do I kill a process")
        self.assertIn("aura", result.lower())

    def test_ai_knows_shell(self):
        result = self.ai.query("how do I start the interactive terminal")
        self.assertIn("shell", result.lower())

    def test_ai_greeting_updated(self):
        result = self.ai.query("hello")
        self.assertIn("AI", result)


if __name__ == "__main__":
    unittest.main(verbosity=2)
