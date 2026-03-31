"""Tests for aura_os.pkg.registry — LocalRegistry."""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault("AURA_HOME", str(Path(tempfile.gettempdir()) / "aura_os_test"))

from aura_os.pkg.registry import LocalRegistry


class TestLocalRegistry(unittest.TestCase):
    """Unit tests for LocalRegistry."""

    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        self._reg_path = os.path.join(self._tmp, "registry.json")
        self.reg = LocalRegistry(registry_path=self._reg_path)

    def tearDown(self):
        import shutil
        shutil.rmtree(self._tmp, ignore_errors=True)

    # ── Initialization ────────────────────────────────────────────────

    def test_creates_registry_file_on_init(self):
        self.assertTrue(os.path.isfile(self._reg_path))

    def test_empty_registry_on_init(self):
        self.assertEqual(self.reg.list_packages(), [])

    def test_creates_parent_directories(self):
        nested = os.path.join(self._tmp, "a", "b", "registry.json")
        reg = LocalRegistry(registry_path=nested)
        self.assertTrue(os.path.isfile(nested))

    # ── add_package ───────────────────────────────────────────────────

    def test_add_package(self):
        manifest = {"name": "foo", "version": "1.0.0", "description": "A foo package"}
        self.reg.add_package(manifest)
        result = self.reg.get_package("foo")
        self.assertIsNotNone(result)
        self.assertEqual(result["name"], "foo")
        self.assertEqual(result["version"], "1.0.0")

    def test_add_package_missing_name_raises(self):
        with self.assertRaises(ValueError):
            self.reg.add_package({"version": "1.0"})

    def test_add_package_missing_version_raises(self):
        with self.assertRaises(ValueError):
            self.reg.add_package({"name": "bar"})

    def test_add_package_updates_existing(self):
        self.reg.add_package({"name": "pkg", "version": "1.0"})
        self.reg.add_package({"name": "pkg", "version": "2.0"})
        result = self.reg.get_package("pkg")
        self.assertEqual(result["version"], "2.0")

    # ── get_package ───────────────────────────────────────────────────

    def test_get_package_nonexistent(self):
        self.assertIsNone(self.reg.get_package("nope"))

    # ── list_packages ─────────────────────────────────────────────────

    def test_list_packages_returns_all(self):
        self.reg.add_package({"name": "a", "version": "1"})
        self.reg.add_package({"name": "b", "version": "2"})
        pkgs = self.reg.list_packages()
        names = {p["name"] for p in pkgs}
        self.assertEqual(names, {"a", "b"})

    # ── remove_package ────────────────────────────────────────────────

    def test_remove_existing_package(self):
        self.reg.add_package({"name": "removeme", "version": "1"})
        result = self.reg.remove_package("removeme")
        self.assertTrue(result)
        self.assertIsNone(self.reg.get_package("removeme"))

    def test_remove_nonexistent_returns_false(self):
        result = self.reg.remove_package("ghost")
        self.assertFalse(result)

    # ── Persistence ───────────────────────────────────────────────────

    def test_data_persists_across_instances(self):
        self.reg.add_package({"name": "persist", "version": "1.0"})
        reg2 = LocalRegistry(registry_path=self._reg_path)
        result = reg2.get_package("persist")
        self.assertIsNotNone(result)
        self.assertEqual(result["version"], "1.0")

    def test_handles_corrupted_file(self):
        with open(self._reg_path, "w") as f:
            f.write("not json!")
        # _read should return empty dict, not crash
        result = self.reg.list_packages()
        self.assertEqual(result, [])

    # ── Validation ────────────────────────────────────────────────────

    def test_required_fields(self):
        self.assertEqual(LocalRegistry.REQUIRED_FIELDS, {"name", "version"})


if __name__ == "__main__":
    unittest.main()
