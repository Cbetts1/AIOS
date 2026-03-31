"""Tests for aura_os.pkg.manager — PackageManager."""

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

from aura_os.pkg.manager import PackageManager
from aura_os.pkg.registry import LocalRegistry


class TestPackageManager(unittest.TestCase):
    """Unit tests for PackageManager."""

    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        # Set AURA_HOME so PackageManager uses our temp dir
        self._orig_home = os.environ.get("AURA_HOME")
        os.environ["AURA_HOME"] = self._tmp
        self._reg_path = os.path.join(self._tmp, "pkg", "registry.json")
        self.registry = LocalRegistry(registry_path=self._reg_path)
        self.pm = PackageManager(registry=self.registry)

    def tearDown(self):
        import shutil
        shutil.rmtree(self._tmp, ignore_errors=True)
        if self._orig_home:
            os.environ["AURA_HOME"] = self._orig_home

    # ── install ───────────────────────────────────────────────────────

    def test_install_from_registry(self):
        self.registry.add_package({
            "name": "testpkg",
            "version": "1.0.0",
            "description": "Test package"
        })
        result = self.pm.install("testpkg")
        self.assertTrue(result)

    def test_install_nonexistent_package(self):
        result = self.pm.install("nonexistent")
        self.assertFalse(result)

    def test_install_already_installed(self):
        self.registry.add_package({"name": "dup", "version": "1.0"})
        self.pm.install("dup")
        # Installing again should return True (already installed)
        result = self.pm.install("dup")
        self.assertTrue(result)

    def test_install_from_manifest_file(self):
        manifest = {"name": "file-pkg", "version": "2.0", "description": "From file"}
        manifest_path = os.path.join(self._tmp, "pkg.json")
        with open(manifest_path, "w") as f:
            json.dump(manifest, f)
        result = self.pm.install(manifest_path)
        self.assertTrue(result)
        # Should be listed as installed
        installed = self.pm.list_installed()
        names = [p["name"] for p in installed]
        self.assertIn("file-pkg", names)

    def test_install_from_invalid_manifest_file(self):
        bad_path = os.path.join(self._tmp, "bad.json")
        with open(bad_path, "w") as f:
            f.write("not json!")
        result = self.pm.install(bad_path)
        self.assertFalse(result)

    def test_install_with_install_cmd(self):
        self.registry.add_package({
            "name": "cmdpkg",
            "version": "1.0",
            "install_cmd": "echo installed"
        })
        result = self.pm.install("cmdpkg")
        self.assertTrue(result)

    def test_install_with_failing_install_cmd(self):
        self.registry.add_package({
            "name": "failcmd",
            "version": "1.0",
            "install_cmd": "false"
        })
        result = self.pm.install("failcmd")
        self.assertFalse(result)

    # ── remove ────────────────────────────────────────────────────────

    def test_remove_installed_package(self):
        self.registry.add_package({"name": "removable", "version": "1.0"})
        self.pm.install("removable")
        result = self.pm.remove("removable")
        self.assertTrue(result)

    def test_remove_not_installed(self):
        result = self.pm.remove("ghost")
        self.assertFalse(result)

    # ── list_installed ────────────────────────────────────────────────

    def test_list_installed_empty(self):
        self.assertEqual(self.pm.list_installed(), [])

    def test_list_installed_after_install(self):
        self.registry.add_package({"name": "listed", "version": "1.0"})
        self.pm.install("listed")
        installed = self.pm.list_installed()
        self.assertEqual(len(installed), 1)
        self.assertEqual(installed[0]["name"], "listed")

    def test_list_installed_sorted_by_name(self):
        for name in ("charlie", "alpha", "bravo"):
            self.registry.add_package({"name": name, "version": "1.0"})
            self.pm.install(name)
        installed = self.pm.list_installed()
        names = [p["name"] for p in installed]
        self.assertEqual(names, ["alpha", "bravo", "charlie"])

    # ── search ────────────────────────────────────────────────────────

    def test_search_by_name(self):
        self.registry.add_package({"name": "python-utils", "version": "1.0", "description": ""})
        self.registry.add_package({"name": "js-tools", "version": "1.0", "description": ""})
        results = self.pm.search("python")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["name"], "python-utils")

    def test_search_by_description(self):
        self.registry.add_package({
            "name": "mylib",
            "version": "1.0",
            "description": "A library for data parsing"
        })
        results = self.pm.search("parsing")
        self.assertEqual(len(results), 1)

    def test_search_case_insensitive(self):
        self.registry.add_package({"name": "CamelCase", "version": "1.0", "description": ""})
        results = self.pm.search("camelcase")
        self.assertEqual(len(results), 1)

    def test_search_no_results(self):
        results = self.pm.search("zzzznonexistent")
        self.assertEqual(results, [])


if __name__ == "__main__":
    unittest.main()
