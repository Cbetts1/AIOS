"""Tests for the filesystem subsystem (VirtualFS and KVStore)."""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from aura_os.fs.vfs import VirtualFS
from aura_os.fs.store import KVStore


class TestVirtualFS(unittest.TestCase):
    """Tests for VirtualFS — sandboxed virtual filesystem."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.vfs = VirtualFS(base_dir=self.tmpdir)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_write_and_read(self):
        self.vfs.write("hello.txt", "hello world")
        content = self.vfs.read("hello.txt")
        self.assertEqual(content, "hello world")

    def test_exists_true_after_write(self):
        self.vfs.write("exists.txt", "x")
        self.assertTrue(self.vfs.exists("exists.txt"))

    def test_exists_false_for_missing(self):
        self.assertFalse(self.vfs.exists("does_not_exist.txt"))

    def test_delete(self):
        self.vfs.write("del.txt", "bye")
        self.assertTrue(self.vfs.exists("del.txt"))
        self.vfs.delete("del.txt")
        self.assertFalse(self.vfs.exists("del.txt"))

    def test_mkdir_and_ls(self):
        self.vfs.mkdir("subdir")
        self.vfs.write("subdir/item.txt", "data")
        entries = self.vfs.ls("subdir")
        self.assertIn("item.txt", entries)

    def test_ls_root(self):
        self.vfs.write("alpha.txt", "a")
        self.vfs.write("beta.txt", "b")
        entries = self.vfs.ls()
        self.assertIn("alpha.txt", entries)
        self.assertIn("beta.txt", entries)

    def test_stat_file(self):
        self.vfs.write("stat.txt", "content")
        info = self.vfs.stat("stat.txt")
        self.assertTrue(info["is_file"])
        self.assertFalse(info["is_dir"])
        self.assertGreater(info["size"], 0)

    def test_stat_dir(self):
        self.vfs.mkdir("statdir")
        info = self.vfs.stat("statdir")
        self.assertTrue(info["is_dir"])
        self.assertFalse(info["is_file"])

    def test_write_creates_parent_directories(self):
        self.vfs.write("deep/nested/file.txt", "deep")
        self.assertTrue(self.vfs.exists("deep/nested/file.txt"))

    def test_path_traversal_blocked(self):
        with self.assertRaises(PermissionError):
            self.vfs.read("../../etc/passwd")

    def test_path_traversal_blocked_absolute(self):
        with self.assertRaises(PermissionError):
            # Absolute path that doesn't resolve inside sandbox
            self.vfs._safe_path("/etc/passwd")

    def test_base_dir_property(self):
        self.assertEqual(self.vfs.base_dir, os.path.realpath(self.tmpdir))


class TestKVStore(unittest.TestCase):
    """Tests for KVStore — JSON-backed key-value store."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.store_path = os.path.join(self.tmpdir, "test_store.json")
        self.store = KVStore(store_path=self.store_path)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_set_and_get(self):
        self.store.set("foo", "bar")
        self.assertEqual(self.store.get("foo"), "bar")

    def test_get_default(self):
        self.assertIsNone(self.store.get("missing"))
        self.assertEqual(self.store.get("missing", 42), 42)

    def test_delete(self):
        self.store.set("key", "value")
        self.store.delete("key")
        self.assertIsNone(self.store.get("key"))

    def test_delete_nonexistent(self):
        # Should not raise
        self.store.delete("no_such_key")

    def test_keys(self):
        self.store.set("a", 1)
        self.store.set("b", 2)
        keys = self.store.keys()
        self.assertIn("a", keys)
        self.assertIn("b", keys)

    def test_clear(self):
        self.store.set("x", 99)
        self.store.clear()
        self.assertEqual(self.store.keys(), [])

    def test_persistence(self):
        self.store.set("persist", "yes")
        # Open a fresh KVStore instance pointing to same file
        store2 = KVStore(store_path=self.store_path)
        self.assertEqual(store2.get("persist"), "yes")

    def test_nested_value(self):
        self.store.set("nested", {"inner": [1, 2, 3]})
        val = self.store.get("nested")
        self.assertEqual(val["inner"], [1, 2, 3])


if __name__ == "__main__":
    unittest.main()
