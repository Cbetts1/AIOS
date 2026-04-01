"""Tests for EAL adapters: FallbackAdapter and AndroidAdapter."""

import os
import sys
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from aura_os.eal.adapters.fallback import FallbackAdapter
from aura_os.eal.adapters.android import AndroidAdapter


# ---------------------------------------------------------------------------
# FallbackAdapter
# ---------------------------------------------------------------------------

class TestFallbackAdapter(unittest.TestCase):
    """Tests for FallbackAdapter — minimal POSIX adapter."""

    def setUp(self):
        self.adapter = FallbackAdapter()

    # ------------------------------------------------------------------
    # Path helpers
    # ------------------------------------------------------------------

    def test_get_home_returns_string(self):
        home = self.adapter.get_home()
        self.assertIsInstance(home, str)
        self.assertTrue(len(home) > 0)

    def test_get_home_matches_expanduser(self):
        expected = os.path.expanduser("~")
        self.assertEqual(self.adapter.get_home(), expected)

    def test_get_prefix_returns_usr_local(self):
        self.assertEqual(self.adapter.get_prefix(), "/usr/local")

    def test_get_tmp_returns_string(self):
        tmp = self.adapter.get_tmp()
        self.assertIsInstance(tmp, str)
        self.assertTrue(len(tmp) > 0)

    def test_get_tmp_uses_tmpdir_env(self):
        with patch.dict(os.environ, {"TMPDIR": "/custom/tmp"}):
            adapter = FallbackAdapter()
        self.assertEqual(adapter.get_tmp(), "/custom/tmp")

    # ------------------------------------------------------------------
    # run_command
    # ------------------------------------------------------------------

    def test_run_command_echo_succeeds(self):
        rc, stdout, stderr = self.adapter.run_command(["echo", "hello"])
        self.assertEqual(rc, 0)
        self.assertIn("hello", stdout)

    def test_run_command_returns_tuple(self):
        result = self.adapter.run_command(["echo", "test"])
        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 3)

    def test_run_command_nonexistent_binary_returns_127(self):
        rc, stdout, stderr = self.adapter.run_command(["totally_nonexistent_binary_xyz"])
        self.assertEqual(rc, 127)

    def test_run_command_oserror_returns_one(self):
        with patch("subprocess.run", side_effect=OSError("fail")):
            rc, stdout, stderr = self.adapter.run_command(["cmd"])
        self.assertEqual(rc, 1)
        self.assertIn("fail", stderr)

    def test_run_command_capture_false(self):
        # Should not raise; capture=False means output goes to real stdout
        rc, stdout, stderr = self.adapter.run_command(["true"], capture=False)
        self.assertEqual(rc, 0)

    # ------------------------------------------------------------------
    # available_pkg_manager
    # ------------------------------------------------------------------

    def test_available_pkg_manager_returns_none(self):
        result = self.adapter.available_pkg_manager()
        self.assertIsNone(result)

    # ------------------------------------------------------------------
    # get_system_info
    # ------------------------------------------------------------------

    def test_get_system_info_returns_dict(self):
        info = self.adapter.get_system_info()
        self.assertIsInstance(info, dict)

    def test_get_system_info_has_platform(self):
        info = self.adapter.get_system_info()
        self.assertIn("platform", info)
        self.assertIsInstance(info["platform"], str)

    def test_get_system_info_has_cpu_count(self):
        info = self.adapter.get_system_info()
        self.assertIn("cpu_count", info)
        self.assertGreater(info["cpu_count"], 0)

    def test_get_system_info_has_arch(self):
        info = self.adapter.get_system_info()
        self.assertIn("arch", info)

    def test_get_system_info_has_memory_key(self):
        info = self.adapter.get_system_info()
        self.assertIn("memory", info)


# ---------------------------------------------------------------------------
# AndroidAdapter
# ---------------------------------------------------------------------------

class TestAndroidAdapter(unittest.TestCase):
    """Tests for AndroidAdapter — Termux / Android adapter."""

    def setUp(self):
        # Termux home likely doesn't exist in CI; adapter should fall back
        self.adapter = AndroidAdapter()

    # ------------------------------------------------------------------
    # Path helpers
    # ------------------------------------------------------------------

    def test_get_home_returns_string(self):
        home = self.adapter.get_home()
        self.assertIsInstance(home, str)
        self.assertTrue(len(home) > 0)

    def test_get_prefix_returns_termux_prefix(self):
        self.assertEqual(self.adapter.get_prefix(), "/data/data/com.termux/files/usr")

    def test_get_tmp_returns_termux_tmp(self):
        self.assertEqual(self.adapter.get_tmp(), "/data/data/com.termux/files/usr/tmp")

    def test_get_home_falls_back_when_termux_missing(self):
        # In CI, Termux path doesn't exist so home should be real $HOME
        if not os.path.isdir("/data/data/com.termux/files/home"):
            expected = os.path.expanduser("~")
            self.assertEqual(self.adapter.get_home(), expected)

    # ------------------------------------------------------------------
    # available_pkg_manager
    # ------------------------------------------------------------------

    def test_available_pkg_manager_returns_pkg(self):
        self.assertEqual(self.adapter.available_pkg_manager(), "pkg")

    # ------------------------------------------------------------------
    # run_command
    # ------------------------------------------------------------------

    def test_run_command_echo(self):
        rc, stdout, stderr = self.adapter.run_command(["echo", "android"])
        self.assertEqual(rc, 0)
        self.assertIn("android", stdout)

    def test_run_command_missing_binary_returns_127(self):
        rc, stdout, stderr = self.adapter.run_command(["totally_missing_binary_abc"])
        self.assertEqual(rc, 127)

    def test_run_command_returns_tuple(self):
        result = self.adapter.run_command(["true"])
        self.assertEqual(len(result), 3)

    def test_run_command_oserror_returns_one(self):
        with patch("subprocess.run", side_effect=OSError("err")):
            rc, stdout, stderr = self.adapter.run_command(["cmd"])
        self.assertEqual(rc, 1)

    # ------------------------------------------------------------------
    # get_system_info
    # ------------------------------------------------------------------

    def test_get_system_info_returns_dict(self):
        info = self.adapter.get_system_info()
        self.assertIsInstance(info, dict)

    def test_get_system_info_platform_is_android(self):
        info = self.adapter.get_system_info()
        self.assertEqual(info["platform"], "android/termux")

    def test_get_system_info_has_arch(self):
        info = self.adapter.get_system_info()
        self.assertIn("arch", info)

    def test_get_system_info_has_cpu_count(self):
        info = self.adapter.get_system_info()
        self.assertGreater(info["cpu_count"], 0)

    def test_get_system_info_has_memory(self):
        info = self.adapter.get_system_info()
        self.assertIn("memory", info)

    # ------------------------------------------------------------------
    # _read_meminfo
    # ------------------------------------------------------------------

    def test_read_meminfo_returns_dict(self):
        result = AndroidAdapter._read_meminfo()
        self.assertIsInstance(result, dict)

    def test_read_meminfo_oserror_returns_empty(self):
        with patch("builtins.open", side_effect=OSError):
            result = AndroidAdapter._read_meminfo()
        self.assertEqual(result, {})

    def test_read_meminfo_parses_proc_meminfo(self):
        fake_content = (
            "MemTotal:       8000000 kB\n"
            "MemFree:        1000000 kB\n"
            "MemAvailable:   3000000 kB\n"
        )
        with patch("builtins.open", unittest.mock.mock_open(read_data=fake_content)):
            result = AndroidAdapter._read_meminfo()
        self.assertEqual(result["total_kb"], 8000000)
        self.assertEqual(result["available_kb"], 3000000)
        self.assertGreater(result["used_kb"], 0)
        self.assertGreaterEqual(result["percent"], 0.0)

    def test_read_meminfo_zero_total_gives_zero_percent(self):
        fake_content = "MemTotal: 0 kB\nMemFree: 0 kB\n"
        with patch("builtins.open", unittest.mock.mock_open(read_data=fake_content)):
            result = AndroidAdapter._read_meminfo()
        self.assertEqual(result.get("percent", 0.0), 0.0)

    def test_read_meminfo_uses_memfree_when_available_missing(self):
        fake_content = "MemTotal: 4000000 kB\nMemFree: 1000000 kB\n"
        with patch("builtins.open", unittest.mock.mock_open(read_data=fake_content)):
            result = AndroidAdapter._read_meminfo()
        self.assertEqual(result["available_kb"], 1000000)


if __name__ == "__main__":
    unittest.main()
