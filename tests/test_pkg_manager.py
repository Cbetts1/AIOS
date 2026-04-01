"""Tests for aura_os/pkg/manager.py — PackageManager."""

import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from aura_os.pkg.registry import LocalRegistry
from aura_os.pkg.manager import PackageManager


class TestPackageManager(unittest.TestCase):
    """Tests for PackageManager high-level package operations."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        reg_path = os.path.join(self.tmpdir, "registry.json")
        install_dir = os.path.join(self.tmpdir, "installed")
        os.makedirs(install_dir, exist_ok=True)

        self.registry = LocalRegistry(registry_path=reg_path)
        self.pm = PackageManager(registry=self.registry)
        # Override install dir to use tmpdir
        self.pm._install_dir = install_dir

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _add_registry_pkg(self, name="mypkg", version="1.0.0", **kwargs):
        manifest = {"name": name, "version": version}
        manifest.update(kwargs)
        self.registry.add_package(manifest)
        return manifest

    def _write_manifest_file(self, name="filepkg", version="0.1.0", **kwargs):
        manifest = {"name": name, "version": version}
        manifest.update(kwargs)
        path = os.path.join(self.tmpdir, f"{name}.aura-pkg.json")
        with open(path, "w") as fh:
            json.dump(manifest, fh)
        return path, manifest

    # ------------------------------------------------------------------
    # install — from registry
    # ------------------------------------------------------------------

    def test_install_from_registry_returns_true(self):
        self._add_registry_pkg()
        result = self.pm.install("mypkg")
        self.assertTrue(result)

    def test_install_from_registry_saves_installed(self):
        self._add_registry_pkg()
        self.pm.install("mypkg")
        self.assertTrue(self.pm._is_installed("mypkg"))

    def test_install_unknown_package_returns_false(self):
        result = self.pm.install("ghost_package")
        self.assertFalse(result)

    def test_install_already_installed_returns_true(self):
        self._add_registry_pkg()
        self.pm.install("mypkg")
        # Second install should be idempotent
        result = self.pm.install("mypkg")
        self.assertTrue(result)

    # ------------------------------------------------------------------
    # install — from file
    # ------------------------------------------------------------------

    def test_install_from_file_returns_true(self):
        path, _ = self._write_manifest_file()
        result = self.pm.install(path)
        self.assertTrue(result)

    def test_install_from_file_saves_manifest(self):
        path, manifest = self._write_manifest_file(name="filepkg")
        self.pm.install(path)
        self.assertTrue(self.pm._is_installed("filepkg"))

    def test_install_from_invalid_json_file_returns_false(self):
        bad_path = os.path.join(self.tmpdir, "bad.json")
        with open(bad_path, "w") as fh:
            fh.write("NOT JSON")
        result = self.pm.install(bad_path)
        self.assertFalse(result)

    # ------------------------------------------------------------------
    # install — with install_cmd
    # ------------------------------------------------------------------

    def test_install_with_successful_install_cmd(self):
        self._add_registry_pkg(install_cmd="echo hello")
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            result = self.pm.install("mypkg")
        self.assertTrue(result)

    def test_install_with_failing_install_cmd_returns_false(self):
        self._add_registry_pkg(install_cmd="false_command")
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1)
            result = self.pm.install("mypkg")
        self.assertFalse(result)

    # ------------------------------------------------------------------
    # remove
    # ------------------------------------------------------------------

    def test_remove_installed_returns_true(self):
        self._add_registry_pkg()
        self.pm.install("mypkg")
        result = self.pm.remove("mypkg")
        self.assertTrue(result)

    def test_remove_deletes_manifest_file(self):
        self._add_registry_pkg()
        self.pm.install("mypkg")
        self.pm.remove("mypkg")
        self.assertFalse(self.pm._is_installed("mypkg"))

    def test_remove_not_installed_returns_false(self):
        result = self.pm.remove("not_installed_pkg")
        self.assertFalse(result)

    # ------------------------------------------------------------------
    # list_installed
    # ------------------------------------------------------------------

    def test_list_installed_empty(self):
        packages = self.pm.list_installed()
        self.assertEqual(packages, [])

    def test_list_installed_returns_installed_packages(self):
        for name in ("alpha", "beta", "gamma"):
            self._add_registry_pkg(name=name)
            self.pm.install(name)
        packages = self.pm.list_installed()
        names = [p["name"] for p in packages]
        for name in ("alpha", "beta", "gamma"):
            self.assertIn(name, names)

    def test_list_installed_sorted_by_name(self):
        for name in ("zzz", "aaa", "mmm"):
            self._add_registry_pkg(name=name)
            self.pm.install(name)
        packages = self.pm.list_installed()
        names = [p["name"] for p in packages]
        self.assertEqual(names, sorted(names))

    def test_list_installed_excludes_removed(self):
        self._add_registry_pkg()
        self.pm.install("mypkg")
        self.pm.remove("mypkg")
        self.assertEqual(self.pm.list_installed(), [])

    # ------------------------------------------------------------------
    # search
    # ------------------------------------------------------------------

    def test_search_matches_by_name(self):
        self._add_registry_pkg(name="curl_tool", description="HTTP client")
        results = self.pm.search("curl")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["name"], "curl_tool")

    def test_search_matches_by_description(self):
        self._add_registry_pkg(name="tool", description="awesome HTTP client")
        results = self.pm.search("http client")
        self.assertEqual(len(results), 1)

    def test_search_case_insensitive(self):
        self._add_registry_pkg(name="MyTool", description="description")
        results = self.pm.search("mytool")
        self.assertEqual(len(results), 1)

    def test_search_no_results(self):
        self._add_registry_pkg(name="tool", description="some description")
        results = self.pm.search("xyznonexistent999")
        self.assertEqual(results, [])

    def test_search_multiple_matches(self):
        self._add_registry_pkg(name="git_tool", description="git wrapper")
        self._add_registry_pkg(name="git_extra", description="extra git features")
        self._add_registry_pkg(name="curl", description="curl tool")
        results = self.pm.search("git")
        self.assertEqual(len(results), 2)

    # ------------------------------------------------------------------
    # _load_installed with corrupted file
    # ------------------------------------------------------------------

    def test_load_installed_returns_none_for_corrupted_file(self):
        bad_path = self.pm._installed_manifest_path("corrupted")
        with open(bad_path, "w") as fh:
            fh.write("NOT JSON")
        result = self.pm._load_installed("corrupted")
        self.assertIsNone(result)

    def test_load_installed_returns_none_for_missing_file(self):
        result = self.pm._load_installed("does_not_exist")
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
