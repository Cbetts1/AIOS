"""Tests for aura_os.kernel.ipc — IPCChannel."""

import json
import os
import sys
import tempfile
import threading
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault("AURA_HOME", str(Path(tempfile.gettempdir()) / "aura_os_test"))

from aura_os.kernel.ipc import IPCChannel


class TestIPCChannel(unittest.TestCase):
    """Unit tests for IPCChannel."""

    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        self.ipc = IPCChannel(base_dir=self._tmp)

    def tearDown(self):
        import shutil
        shutil.rmtree(self._tmp, ignore_errors=True)

    # ── Basic send / receive ──────────────────────────────────────────

    def test_send_and_receive(self):
        self.ipc.send("test-ch", {"key": "value"})
        msgs = self.ipc.receive("test-ch")
        self.assertEqual(len(msgs), 1)
        self.assertEqual(msgs[0]["data"], {"key": "value"})
        self.assertIn("ts", msgs[0])

    def test_receive_empty_channel(self):
        msgs = self.ipc.receive("nonexistent")
        self.assertEqual(msgs, [])

    def test_multiple_messages(self):
        for i in range(5):
            self.ipc.send("multi", {"i": i})
        msgs = self.ipc.receive("multi")
        self.assertEqual(len(msgs), 5)
        self.assertEqual([m["data"]["i"] for m in msgs], list(range(5)))

    def test_receive_preserves_messages(self):
        """receive() should NOT remove messages; they stay until clear()."""
        self.ipc.send("persist", {"a": 1})
        self.ipc.receive("persist")
        msgs = self.ipc.receive("persist")
        self.assertEqual(len(msgs), 1)

    # ── Clear ─────────────────────────────────────────────────────────

    def test_clear_removes_messages(self):
        self.ipc.send("clearme", {"x": 1})
        self.ipc.clear("clearme")
        msgs = self.ipc.receive("clearme")
        self.assertEqual(msgs, [])

    def test_clear_nonexistent_channel(self):
        # Should not raise
        self.ipc.clear("nope")

    # ── Channel isolation ─────────────────────────────────────────────

    def test_channels_are_isolated(self):
        self.ipc.send("ch-a", {"src": "a"})
        self.ipc.send("ch-b", {"src": "b"})
        a_msgs = self.ipc.receive("ch-a")
        b_msgs = self.ipc.receive("ch-b")
        self.assertEqual(len(a_msgs), 1)
        self.assertEqual(a_msgs[0]["data"]["src"], "a")
        self.assertEqual(len(b_msgs), 1)
        self.assertEqual(b_msgs[0]["data"]["src"], "b")

    # ── Channel name sanitization ─────────────────────────────────────

    def test_channel_path_sanitizes_slashes(self):
        path = self.ipc._channel_path("a/b/c")
        self.assertNotIn("/b/", path.replace(self._tmp, ""))
        self.assertTrue(path.endswith(".jsonl"))

    def test_channel_path_sanitizes_dotdot(self):
        path = self.ipc._channel_path("../escape")
        self.assertNotIn("..", os.path.basename(path))

    # ── Thread safety ─────────────────────────────────────────────────

    def test_concurrent_sends(self):
        """Multiple threads sending to the same channel should not corrupt data."""
        errors = []

        def worker(thread_id):
            try:
                for i in range(10):
                    self.ipc.send("concurrent", {"tid": thread_id, "i": i})
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=worker, args=(t,)) for t in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(errors, [])
        msgs = self.ipc.receive("concurrent")
        self.assertEqual(len(msgs), 40)  # 4 threads × 10 messages

    # ── Lock management ───────────────────────────────────────────────

    def test_get_lock_returns_same_lock_for_same_channel(self):
        lock1 = self.ipc._get_lock("same")
        lock2 = self.ipc._get_lock("same")
        self.assertIs(lock1, lock2)

    def test_get_lock_returns_different_locks_for_different_channels(self):
        lock_a = self.ipc._get_lock("alpha")
        lock_b = self.ipc._get_lock("beta")
        self.assertIsNot(lock_a, lock_b)

    # ── Complex message data ──────────────────────────────────────────

    def test_nested_dict_message(self):
        nested = {"list": [1, 2, 3], "nested": {"a": True, "b": None}}
        self.ipc.send("complex", nested)
        msgs = self.ipc.receive("complex")
        self.assertEqual(msgs[0]["data"], nested)

    def test_empty_dict_message(self):
        self.ipc.send("empty", {})
        msgs = self.ipc.receive("empty")
        self.assertEqual(msgs[0]["data"], {})


if __name__ == "__main__":
    unittest.main()
