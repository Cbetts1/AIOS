"""Tests for aura_os/pkg/registry.py — LocalRegistry."""

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from aura_os.pkg.registry import LocalRegistry


class TestLocalRegistry(unittest.TestCase):
    """Tests for LocalRegistry JSON-backed package registry."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.registry_path = os.path.join(self.tmpdir, "registry.json")
        self.reg = LocalRegistry(registry_path=self.registry_path)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _pkg(self, name="mypkg", version="1.0.0", **kwargs):
        manifest = {"name": name, "version": version}
        manifest.update(kwargs)
        return manifest

    # ------------------------------------------------------------------
    # Initialisation
    # ------------------------------------------------------------------

    def test_registry_file_created_on_init(self):
        self.assertTrue(os.path.isfile(self.registry_path))

    def test_empty_registry_on_init(self):
        self.assertEqual(self.reg.list_packages(), [])

    # ------------------------------------------------------------------
    # add_package / get_package
    # ------------------------------------------------------------------

    def test_add_and_get_package(self):
        self.reg.add_package(self._pkg())
        pkg = self.reg.get_package("mypkg")
        self.assertIsNotNone(pkg)
        self.assertEqual(pkg["name"], "mypkg")
        self.assertEqual(pkg["version"], "1.0.0")

    def test_get_nonexistent_returns_none(self):
        self.assertIsNone(self.reg.get_package("nothere"))

    def test_add_package_missing_name_raises(self):
        with self.assertRaises(ValueError):
            self.reg.add_package({"version": "1.0"})

    def test_add_package_missing_version_raises(self):
        with self.assertRaises(ValueError):
            self.reg.add_package({"name": "x"})

    def test_add_package_persists_to_disk(self):
        self.reg.add_package(self._pkg("persisted"))
        # Read fresh from disk
        reg2 = LocalRegistry(registry_path=self.registry_path)
        self.assertIsNotNone(reg2.get_package("persisted"))

    def test_add_package_updates_existing(self):
        self.reg.add_package(self._pkg(version="1.0.0"))
        self.reg.add_package(self._pkg(version="2.0.0"))
        pkg = self.reg.get_package("mypkg")
        self.assertEqual(pkg["version"], "2.0.0")

    def test_add_package_with_extra_fields(self):
        self.reg.add_package(self._pkg(description="A test package", files=[]))
        pkg = self.reg.get_package("mypkg")
        self.assertEqual(pkg["description"], "A test package")

    # ------------------------------------------------------------------
    # list_packages
    # ------------------------------------------------------------------

    def test_list_packages_empty(self):
        self.assertEqual(self.reg.list_packages(), [])

    def test_list_packages_returns_all(self):
        self.reg.add_package(self._pkg("alpha"))
        self.reg.add_package(self._pkg("beta"))
        packages = self.reg.list_packages()
        names = [p["name"] for p in packages]
        self.assertIn("alpha", names)
        self.assertIn("beta", names)

    def test_list_packages_count(self):
        for i in range(5):
            self.reg.add_package(self._pkg(f"pkg{i}"))
        self.assertEqual(len(self.reg.list_packages()), 5)

    # ------------------------------------------------------------------
    # remove_package
    # ------------------------------------------------------------------

    def test_remove_existing_package_returns_true(self):
        self.reg.add_package(self._pkg())
        result = self.reg.remove_package("mypkg")
        self.assertTrue(result)

    def test_remove_nonexistent_returns_false(self):
        result = self.reg.remove_package("ghost")
        self.assertFalse(result)

    def test_remove_actually_deletes_entry(self):
        self.reg.add_package(self._pkg())
        self.reg.remove_package("mypkg")
        self.assertIsNone(self.reg.get_package("mypkg"))
        self.assertEqual(self.reg.list_packages(), [])

    def test_remove_only_removes_target(self):
        self.reg.add_package(self._pkg("keep"))
        self.reg.add_package(self._pkg("remove_me"))
        self.reg.remove_package("remove_me")
        self.assertIsNotNone(self.reg.get_package("keep"))
        self.assertIsNone(self.reg.get_package("remove_me"))

    # ------------------------------------------------------------------
    # corrupted registry file recovery
    # ------------------------------------------------------------------

    def test_corrupted_json_returns_empty(self):
        with open(self.registry_path, "w") as fh:
            fh.write("INVALID JSON")
        reg2 = LocalRegistry(registry_path=self.registry_path)
        self.assertEqual(reg2.list_packages(), [])

    def test_registry_with_non_dict_json_returns_empty(self):
        with open(self.registry_path, "w") as fh:
            json.dump([1, 2, 3], fh)
        reg2 = LocalRegistry(registry_path=self.registry_path)
        self.assertEqual(reg2.list_packages(), [])


if __name__ == "__main__":
    unittest.main()
