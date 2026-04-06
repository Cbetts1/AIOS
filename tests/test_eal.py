"""Tests for the Environment Abstraction Layer (EAL)."""

import os
import sys
import tempfile
import unittest

# Ensure project root is importable when running tests directly
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from aura_os.eal import detector
from aura_os.eal import EAL


class TestDetector(unittest.TestCase):
    """Unit tests for aura_os.eal.detector."""

    def test_get_platform_returns_string(self):
        platform = detector.get_platform()
        self.assertIsInstance(platform, str)
        self.assertIn(platform, ("termux", "android", "linux", "macos", "windows", "unknown"))

    def test_get_available_binaries_returns_dict(self):
        binaries = detector.get_available_binaries()
        self.assertIsInstance(binaries, dict)
        # python3 should always be present since we are running Python
        self.assertIn("python3", binaries)
        # Values must be a string path or None
        for name, path in binaries.items():
            self.assertTrue(path is None or isinstance(path, str))

    def test_get_storage_paths_keys(self):
        paths = detector.get_storage_paths()
        for key in ("home_dir", "temp_dir", "aura_home", "data_dir"):
            self.assertIn(key, paths)
            self.assertIsInstance(paths[key], str)

    def test_get_permissions_returns_booleans(self):
        perms = detector.get_permissions()
        self.assertIsInstance(perms, dict)
        for v in perms.values():
            self.assertIsInstance(v, bool)

    def test_is_linux_bool(self):
        self.assertIsInstance(detector.is_linux(), bool)

    def test_is_termux_bool(self):
        self.assertIsInstance(detector.is_termux(), bool)

    def test_is_android_bool(self):
        self.assertIsInstance(detector.is_android(), bool)


class TestEAL(unittest.TestCase):
    """Integration tests for the EAL class."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_eal_instantiation(self):
        eal = EAL()
        self.assertIsNotNone(eal)
        self.assertIsNotNone(eal.adapter)
        self.assertIsNotNone(eal.platform)

    def test_platform_property(self):
        eal = EAL()
        self.assertIsInstance(eal.platform, str)

    def test_write_read_delete_round_trip(self):
        eal = EAL()
        test_path = os.path.join(self.tmpdir, "test_file.txt")
        content = "hello aura\n"

        eal.write_file(test_path, content)
        self.assertTrue(os.path.isfile(test_path))

        read_back = eal.read_file(test_path)
        self.assertEqual(read_back, content)

        eal.delete_file(test_path)
        self.assertFalse(os.path.isfile(test_path))

    def test_make_dir(self):
        eal = EAL()
        new_dir = os.path.join(self.tmpdir, "sub", "nested")
        eal.make_dir(new_dir)
        self.assertTrue(os.path.isdir(new_dir))

    def test_list_dir(self):
        eal = EAL()
        # Create a couple of files
        for name in ("b.txt", "a.txt", "c.txt"):
            open(os.path.join(self.tmpdir, name), "w").close()
        entries = eal.list_dir(self.tmpdir)
        self.assertEqual(entries, sorted(entries))  # must be sorted
        self.assertIn("a.txt", entries)

    def test_run_command_echo(self):
        eal = EAL()
        code, stdout, stderr = eal.run_command(["echo", "hello"])
        self.assertEqual(code, 0)
        self.assertIn("hello", stdout)

    def test_run_command_nonexistent(self):
        eal = EAL()
        code, stdout, stderr = eal.run_command(["__nonexistent_binary__"])
        self.assertNotEqual(code, 0)

    def test_get_env_info_keys(self):
        eal = EAL()
        info = eal.get_env_info()
        for key in ("platform", "paths", "binaries", "system"):
            self.assertIn(key, info)


class TestMacOSAdapter(unittest.TestCase):
    """Unit tests for MacOSAdapter (always run; no real macOS calls needed)."""

    def setUp(self):
        from aura_os.eal.adapters.macos import MacOSAdapter
        self.adapter = MacOSAdapter()

    def test_get_home(self):
        self.assertEqual(self.adapter.get_home(), os.path.expanduser("~"))

    def test_get_tmp(self):
        tmp = self.adapter.get_tmp()
        self.assertIsInstance(tmp, str)
        self.assertTrue(len(tmp) > 0)

    def test_get_prefix_returns_string(self):
        prefix = self.adapter.get_prefix()
        self.assertIsInstance(prefix, str)

    def test_run_command_echo(self):
        rc, stdout, _ = self.adapter.run_command(["echo", "mac"])
        self.assertEqual(rc, 0)
        self.assertIn("mac", stdout)

    def test_run_command_missing(self):
        rc, _, _ = self.adapter.run_command(["__no_such_binary_xyz__"])
        self.assertEqual(rc, 127)

    def test_available_pkg_manager_returns_str_or_none(self):
        mgr = self.adapter.available_pkg_manager()
        self.assertTrue(mgr is None or isinstance(mgr, str))

    def test_get_system_info_keys(self):
        info = self.adapter.get_system_info()
        for key in ("platform", "arch", "cpu_count", "memory"):
            self.assertIn(key, info)
        self.assertEqual(info["platform"], "macos")

    def test_get_system_info_memory_dict(self):
        mem = self.adapter.get_system_info()["memory"]
        self.assertIsInstance(mem, dict)


class TestWindowsAdapter(unittest.TestCase):
    """Unit tests for WindowsAdapter (always run; no real Windows calls needed)."""

    def setUp(self):
        from aura_os.eal.adapters.windows import WindowsAdapter
        self.adapter = WindowsAdapter()

    def test_get_home(self):
        self.assertEqual(self.adapter.get_home(), os.path.expanduser("~"))

    def test_get_tmp(self):
        tmp = self.adapter.get_tmp()
        self.assertIsInstance(tmp, str)

    def test_get_prefix_returns_string(self):
        prefix = self.adapter.get_prefix()
        self.assertIsInstance(prefix, str)

    def test_run_command_echo(self):
        rc, stdout, _ = self.adapter.run_command(["echo", "win"])
        self.assertEqual(rc, 0)
        self.assertIn("win", stdout)

    def test_run_command_missing(self):
        rc, _, _ = self.adapter.run_command(["__no_such_binary_xyz__"])
        self.assertEqual(rc, 127)

    def test_available_pkg_manager_returns_str_or_none(self):
        mgr = self.adapter.available_pkg_manager()
        self.assertTrue(mgr is None or isinstance(mgr, str))

    def test_get_system_info_keys(self):
        info = self.adapter.get_system_info()
        for key in ("platform", "arch", "cpu_count", "memory"):
            self.assertIn(key, info)
        self.assertEqual(info["platform"], "windows")

    def test_get_system_info_memory_dict(self):
        mem = self.adapter.get_system_info()["memory"]
        self.assertIsInstance(mem, dict)


if __name__ == "__main__":
    unittest.main()
