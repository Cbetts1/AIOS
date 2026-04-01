"""Tests for aura_os/kernel/ipc.py — file-based IPC channels."""

import json
import os
import sys
import tempfile
import threading
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from aura_os.kernel.ipc import IPCChannel


class TestIPCChannel(unittest.TestCase):
    """Tests for IPCChannel message queues."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.ipc = IPCChannel(base_dir=self.tmpdir)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    # ------------------------------------------------------------------
    # send / receive
    # ------------------------------------------------------------------

    def test_send_and_receive_single_message(self):
        self.ipc.send("test", {"hello": "world"})
        msgs = self.ipc.receive("test")
        self.assertEqual(len(msgs), 1)
        self.assertEqual(msgs[0]["data"], {"hello": "world"})

    def test_receive_empty_channel_returns_empty_list(self):
        msgs = self.ipc.receive("nonexistent")
        self.assertEqual(msgs, [])

    def test_send_multiple_messages(self):
        for i in range(5):
            self.ipc.send("multi", {"index": i})
        msgs = self.ipc.receive("multi")
        self.assertEqual(len(msgs), 5)
        indices = [m["data"]["index"] for m in msgs]
        self.assertEqual(indices, list(range(5)))

    def test_message_has_timestamp(self):
        self.ipc.send("ts_test", {"x": 1})
        msgs = self.ipc.receive("ts_test")
        self.assertIn("ts", msgs[0])
        self.assertIsInstance(msgs[0]["ts"], float)

    def test_receive_does_not_consume_messages(self):
        self.ipc.send("persistent", {"v": 1})
        msgs1 = self.ipc.receive("persistent")
        msgs2 = self.ipc.receive("persistent")
        self.assertEqual(len(msgs1), 1)
        self.assertEqual(len(msgs2), 1)

    # ------------------------------------------------------------------
    # clear
    # ------------------------------------------------------------------

    def test_clear_removes_all_messages(self):
        self.ipc.send("clearme", {"a": 1})
        self.ipc.send("clearme", {"a": 2})
        self.ipc.clear("clearme")
        msgs = self.ipc.receive("clearme")
        self.assertEqual(msgs, [])

    def test_clear_nonexistent_channel_does_not_raise(self):
        # Should silently succeed even if channel does not exist
        self.ipc.clear("does_not_exist")

    # ------------------------------------------------------------------
    # channel isolation
    # ------------------------------------------------------------------

    def test_separate_channels_do_not_interfere(self):
        self.ipc.send("ch_a", {"src": "a"})
        self.ipc.send("ch_b", {"src": "b"})
        msgs_a = self.ipc.receive("ch_a")
        msgs_b = self.ipc.receive("ch_b")
        self.assertEqual(msgs_a[0]["data"]["src"], "a")
        self.assertEqual(msgs_b[0]["data"]["src"], "b")

    def test_channel_name_with_slash_is_sanitised(self):
        # "/" should be replaced in filename to avoid subdirectory creation
        self.ipc.send("a/b", {"x": 1})
        msgs = self.ipc.receive("a/b")
        self.assertEqual(len(msgs), 1)

    def test_channel_file_created_on_send(self):
        self.ipc.send("file_check", {"y": 99})
        path = self.ipc._channel_path("file_check")
        self.assertTrue(os.path.isfile(path))

    # ------------------------------------------------------------------
    # concurrent access
    # ------------------------------------------------------------------

    def test_concurrent_sends_no_data_loss(self):
        errors = []

        def sender(idx):
            try:
                self.ipc.send("concurrent", {"idx": idx})
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)

        threads = [threading.Thread(target=sender, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(errors, [])
        msgs = self.ipc.receive("concurrent")
        self.assertEqual(len(msgs), 20)

    # ------------------------------------------------------------------
    # corrupted line in channel file
    # ------------------------------------------------------------------

    def test_receive_skips_corrupt_lines(self):
        self.ipc.send("corrupt_test", {"good": True})
        path = self.ipc._channel_path("corrupt_test")
        with open(path, "a") as fh:
            fh.write("NOT JSON AT ALL\n")
        msgs = self.ipc.receive("corrupt_test")
        # Only the valid message should be returned
        self.assertEqual(len(msgs), 1)
        self.assertTrue(msgs[0]["data"]["good"])

    # ------------------------------------------------------------------
    # _get_lock
    # ------------------------------------------------------------------

    def test_get_lock_returns_same_lock_for_same_channel(self):
        lock1 = self.ipc._get_lock("mylock")
        lock2 = self.ipc._get_lock("mylock")
        self.assertIs(lock1, lock2)

    def test_get_lock_different_channels_different_locks(self):
        lock1 = self.ipc._get_lock("ch1")
        lock2 = self.ipc._get_lock("ch2")
        self.assertIsNot(lock1, lock2)


if __name__ == "__main__":
    unittest.main()
