"""Tests for portable mode, macOS adapter, and overall polish."""

import json
import os
import platform
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

# Ensure project root is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("AURA_HOME", str(Path(tempfile.gettempdir()) / "aura_test"))


# ──────────────────────────────────────────────────────────────────────────────
# Portable bootstrap tests
# ──────────────────────────────────────────────────────────────────────────────

class TestPortableBootstrap(unittest.TestCase):
    """Verify _bootstrap() detects the portable marker."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.saved_env = {}
        for key in ("AURA_HOME", "AURA_PORTABLE"):
            self.saved_env[key] = os.environ.pop(key, None)

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)
        for key, val in self.saved_env.items():
            if val is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = val

    def test_bootstrap_default_home(self):
        """Without a marker, AURA_HOME defaults to ~/.aura."""
        from aura_os.main import _bootstrap
        os.environ.pop("AURA_HOME", None)
        _bootstrap()
        self.assertEqual(os.environ["AURA_HOME"], os.path.expanduser("~/.aura"))

    def test_bootstrap_respects_existing_env(self):
        """If AURA_HOME is already set, _bootstrap leaves it alone."""
        from aura_os.main import _bootstrap
        os.environ["AURA_HOME"] = "/custom/path"
        _bootstrap()
        self.assertEqual(os.environ["AURA_HOME"], "/custom/path")

    def test_bootstrap_portable_marker(self):
        """A .aura_portable marker next to the package triggers portable mode."""
        from aura_os import main as main_mod
        pkg_dir = os.path.dirname(os.path.abspath(main_mod.__file__))
        root_dir = os.path.dirname(pkg_dir)
        marker = os.path.join(root_dir, ".aura_portable")
        try:
            Path(marker).touch()
            os.environ.pop("AURA_HOME", None)
            os.environ.pop("AURA_PORTABLE", None)
            main_mod._bootstrap()
            expected = os.path.join(root_dir, ".aura")
            self.assertEqual(os.environ["AURA_HOME"], expected)
            self.assertEqual(os.environ.get("AURA_PORTABLE"), "1")
        finally:
            if os.path.exists(marker):
                os.remove(marker)


# ──────────────────────────────────────────────────────────────────────────────
# Detector enhancements
# ──────────────────────────────────────────────────────────────────────────────

class TestDetectorEnhancements(unittest.TestCase):
    """Test the new detector helpers: is_macos, is_portable, storage paths."""

    def test_is_macos_bool(self):
        from aura_os.eal.detector import is_macos
        self.assertIsInstance(is_macos(), bool)

    def test_is_portable_false_by_default(self):
        from aura_os.eal.detector import is_portable
        saved = os.environ.pop("AURA_PORTABLE", None)
        try:
            self.assertFalse(is_portable())
        finally:
            if saved is not None:
                os.environ["AURA_PORTABLE"] = saved

    def test_is_portable_true_when_set(self):
        from aura_os.eal.detector import is_portable
        saved = os.environ.get("AURA_PORTABLE")
        try:
            os.environ["AURA_PORTABLE"] = "1"
            self.assertTrue(is_portable())
        finally:
            if saved is None:
                os.environ.pop("AURA_PORTABLE", None)
            else:
                os.environ["AURA_PORTABLE"] = saved

    def test_storage_paths_include_portable(self):
        from aura_os.eal.detector import get_storage_paths
        paths = get_storage_paths()
        self.assertIn("portable", paths)
        self.assertIn(paths["portable"], ("True", "False"))

    def test_permissions_skip_portable_key(self):
        from aura_os.eal.detector import get_permissions
        perms = get_permissions()
        self.assertNotIn("portable_readable", perms)
        self.assertNotIn("portable_writable", perms)


# ──────────────────────────────────────────────────────────────────────────────
# MacOS adapter (aura_os/eal/adapters/macos.py)
# ──────────────────────────────────────────────────────────────────────────────

class TestMacOSAdapterUnit(unittest.TestCase):
    """Unit tests for the new aura_os MacOSAdapter."""

    def _make_adapter(self):
        from aura_os.eal.adapters.macos import MacOSAdapter
        return MacOSAdapter()

    def test_instantiation(self):
        adapter = self._make_adapter()
        self.assertIsNotNone(adapter)

    def test_get_home(self):
        adapter = self._make_adapter()
        self.assertEqual(adapter.get_home(), os.path.expanduser("~"))

    def test_get_prefix(self):
        adapter = self._make_adapter()
        prefix = adapter.get_prefix()
        self.assertIn(prefix, ("/opt/homebrew", "/usr/local"))

    def test_get_tmp(self):
        adapter = self._make_adapter()
        tmp = adapter.get_tmp()
        self.assertIsInstance(tmp, str)
        self.assertTrue(len(tmp) > 0)

    def test_run_command_echo(self):
        adapter = self._make_adapter()
        code, stdout, stderr = adapter.run_command(["echo", "hello"])
        self.assertEqual(code, 0)
        self.assertIn("hello", stdout)

    def test_run_command_nonexistent(self):
        adapter = self._make_adapter()
        code, stdout, stderr = adapter.run_command(["__no_such_cmd__"])
        self.assertNotEqual(code, 0)

    def test_available_pkg_manager_type(self):
        adapter = self._make_adapter()
        result = adapter.available_pkg_manager()
        self.assertTrue(result is None or isinstance(result, str))

    def test_get_system_info_keys(self):
        adapter = self._make_adapter()
        info = adapter.get_system_info()
        for key in ("platform", "arch", "cpu_count", "memory", "macos_version"):
            self.assertIn(key, info)
        self.assertEqual(info["platform"], "macos")
        self.assertIsInstance(info["cpu_count"], int)
        self.assertGreater(info["cpu_count"], 0)

    def test_get_system_info_memory_dict(self):
        adapter = self._make_adapter()
        info = adapter.get_system_info()
        self.assertIsInstance(info["memory"], dict)

    def test_get_system_info_version_string(self):
        adapter = self._make_adapter()
        info = adapter.get_system_info()
        self.assertIsInstance(info["macos_version"], str)


# ──────────────────────────────────────────────────────────────────────────────
# EAL adapter selection
# ──────────────────────────────────────────────────────────────────────────────

class TestEALAdapterSelection(unittest.TestCase):
    """Verify that EAL._select_adapter picks the right adapter."""

    def test_linux_selects_linux_adapter(self):
        from aura_os.eal import EAL
        from aura_os.eal.adapters.linux import LinuxAdapter
        eal = EAL.__new__(EAL)
        eal._platform = "linux"
        adapter = eal._select_adapter()
        self.assertIsInstance(adapter, LinuxAdapter)

    def test_macos_selects_macos_adapter(self):
        from aura_os.eal import EAL
        from aura_os.eal.adapters.macos import MacOSAdapter
        eal = EAL.__new__(EAL)
        eal._platform = "macos"
        adapter = eal._select_adapter()
        self.assertIsInstance(adapter, MacOSAdapter)

    def test_android_selects_android_adapter(self):
        from aura_os.eal import EAL
        from aura_os.eal.adapters.android import AndroidAdapter
        eal = EAL.__new__(EAL)
        eal._platform = "android"
        adapter = eal._select_adapter()
        self.assertIsInstance(adapter, AndroidAdapter)

    def test_termux_selects_android_adapter(self):
        from aura_os.eal import EAL
        from aura_os.eal.adapters.android import AndroidAdapter
        eal = EAL.__new__(EAL)
        eal._platform = "termux"
        adapter = eal._select_adapter()
        self.assertIsInstance(adapter, AndroidAdapter)

    def test_unknown_selects_fallback(self):
        from aura_os.eal import EAL
        from aura_os.eal.adapters.fallback import FallbackAdapter
        eal = EAL.__new__(EAL)
        eal._platform = "unknown"
        adapter = eal._select_adapter()
        self.assertIsInstance(adapter, FallbackAdapter)


# ──────────────────────────────────────────────────────────────────────────────
# Entry script (bash) portability
# ──────────────────────────────────────────────────────────────────────────────

class TestEntryScript(unittest.TestCase):
    """Verify the 'aura' bash entry-point script behaviour."""

    @classmethod
    def setUpClass(cls):
        cls.script = os.path.join(
            os.path.dirname(__file__), "..", "aura"
        )
        # Ensure the script is executable
        if os.path.exists(cls.script):
            st = os.stat(cls.script)
            os.chmod(cls.script, st.st_mode | stat.S_IEXEC)

    def test_script_exists(self):
        self.assertTrue(os.path.isfile(self.script))

    def test_script_has_shebang(self):
        with open(self.script, "r") as fh:
            first_line = fh.readline()
        self.assertTrue(first_line.startswith("#!/usr/bin/env bash"))

    def test_script_references_aura_portable(self):
        with open(self.script, "r") as fh:
            content = fh.read()
        self.assertIn(".aura_portable", content)

    def test_script_resolves_symlinks(self):
        with open(self.script, "r") as fh:
            content = fh.read()
        self.assertIn("readlink", content)


# ──────────────────────────────────────────────────────────────────────────────
# install.sh --portable flag
# ──────────────────────────────────────────────────────────────────────────────

class TestInstallScript(unittest.TestCase):
    """Verify install.sh has portable support and correct structure."""

    @classmethod
    def setUpClass(cls):
        cls.script = os.path.join(
            os.path.dirname(__file__), "..", "install.sh"
        )

    def test_install_script_exists(self):
        self.assertTrue(os.path.isfile(self.script))

    def test_install_script_supports_portable_flag(self):
        with open(self.script, "r") as fh:
            content = fh.read()
        self.assertIn("--portable", content)
        self.assertIn("PORTABLE=1", content)

    def test_install_script_creates_portable_marker(self):
        with open(self.script, "r") as fh:
            content = fh.read()
        self.assertIn(".aura_portable", content)


# ──────────────────────────────────────────────────────────────────────────────
# pyproject.toml
# ──────────────────────────────────────────────────────────────────────────────

class TestPyprojectToml(unittest.TestCase):
    """Verify pyproject.toml is present and well-formed."""

    @classmethod
    def setUpClass(cls):
        cls.path = os.path.join(
            os.path.dirname(__file__), "..", "pyproject.toml"
        )

    def test_file_exists(self):
        self.assertTrue(os.path.isfile(self.path))

    def test_contains_project_name(self):
        with open(self.path, "r") as fh:
            content = fh.read()
        self.assertIn('name = "aura-os"', content)

    def test_contains_version(self):
        with open(self.path, "r") as fh:
            content = fh.read()
        self.assertIn('version = "0.2.0"', content)

    def test_entry_point_defined(self):
        with open(self.path, "r") as fh:
            content = fh.read()
        self.assertIn('aura = "aura_os.main:main"', content)

    def test_requires_python_38(self):
        with open(self.path, "r") as fh:
            content = fh.read()
        self.assertIn('requires-python = ">=3.8"', content)


# ──────────────────────────────────────────────────────────────────────────────
# Version consistency
# ──────────────────────────────────────────────────────────────────────────────

class TestVersionConsistency(unittest.TestCase):
    """Ensure the version string is consistent across all files."""

    def test_init_version(self):
        from aura_os import __version__
        self.assertEqual(__version__, "0.2.0")

    def test_pyproject_matches(self):
        from aura_os import __version__
        path = os.path.join(os.path.dirname(__file__), "..", "pyproject.toml")
        with open(path, "r") as fh:
            for line in fh:
                if line.strip().startswith("version"):
                    self.assertIn(__version__, line)
                    return
        self.fail("version not found in pyproject.toml")


# ──────────────────────────────────────────────────────────────────────────────
# Adapters __init__.py exports
# ──────────────────────────────────────────────────────────────────────────────

class TestAdaptersExports(unittest.TestCase):
    """Verify that the adapters package exports all adapter classes."""

    def test_all_adapters_exported(self):
        from aura_os.eal import adapters
        self.assertTrue(hasattr(adapters, "AndroidAdapter"))
        self.assertTrue(hasattr(adapters, "LinuxAdapter"))
        self.assertTrue(hasattr(adapters, "MacOSAdapter"))
        self.assertTrue(hasattr(adapters, "FallbackAdapter"))

    def test_all_list_complete(self):
        from aura_os.eal.adapters import __all__
        for name in ("AndroidAdapter", "LinuxAdapter", "MacOSAdapter", "FallbackAdapter"):
            self.assertIn(name, __all__)


# ──────────────────────────────────────────────────────────────────────────────
# Shell help text covers all commands
# ──────────────────────────────────────────────────────────────────────────────

class TestShellHelpCompleteness(unittest.TestCase):
    """Verify _print_shell_help references essential built-in commands."""

    def test_help_text_includes_key_commands(self):
        from io import StringIO
        from aura_os.main import _print_shell_help
        buf = StringIO()
        with mock.patch("sys.stdout", buf):
            _print_shell_help()
        text = buf.getvalue()
        for cmd in ("cd", "pwd", "ls", "cat", "head", "tail", "mkdir",
                     "rm", "touch", "cp", "mv", "wc", "grep", "which",
                     "export", "set", "unset", "alias", "unalias", "echo",
                     "whoami", "hostname", "date", "uname", "uptime",
                     "clear", "exit", "quit"):
            self.assertIn(cmd, text, f"Shell help missing command: {cmd}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
