"""Tests for aura_os.kernel.scheduler — Scheduler & Task."""

import os
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault("AURA_HOME", str(Path(tempfile.gettempdir()) / "aura_os_test"))

from aura_os.kernel.scheduler import Scheduler, Task


class TestTask(unittest.TestCase):
    """Tests for the Task dataclass."""

    def test_task_defaults(self):
        t = Task(id="t-1", name="test", func=lambda: None)
        self.assertEqual(t.status, "pending")
        self.assertEqual(t.priority, 5)
        self.assertIsNone(t.result)
        self.assertIsNone(t.error)

    def test_task_custom_priority(self):
        t = Task(id="t-2", name="high", func=lambda: None, priority=1)
        self.assertEqual(t.priority, 1)


class TestScheduler(unittest.TestCase):
    """Unit tests for Scheduler."""

    def setUp(self):
        self.sched = Scheduler()

    # ── add_task ──────────────────────────────────────────────────────

    def test_add_task_returns_id(self):
        tid = self.sched.add_task("hello", lambda: 42)
        self.assertTrue(tid.startswith("task-"))

    def test_add_task_increments_id(self):
        tid1 = self.sched.add_task("a", lambda: 1)
        tid2 = self.sched.add_task("b", lambda: 2)
        # IDs should be unique and incrementing
        self.assertNotEqual(tid1, tid2)

    # ── get_status ────────────────────────────────────────────────────

    def test_get_status_empty(self):
        status = self.sched.get_status()
        self.assertEqual(status, [])

    def test_get_status_after_add(self):
        self.sched.add_task("t1", lambda: None)
        status = self.sched.get_status()
        self.assertEqual(len(status), 1)
        self.assertEqual(status[0]["name"], "t1")
        self.assertEqual(status[0]["status"], "pending")

    # ── run_once ──────────────────────────────────────────────────────

    def test_run_once_returns_none_when_empty(self):
        result = self.sched.run_once()
        self.assertIsNone(result)

    def test_run_once_executes_task(self):
        self.sched.add_task("compute", lambda: 42)
        task = self.sched.run_once()
        self.assertIsNotNone(task)
        self.assertEqual(task.result, 42)
        self.assertEqual(task.status, "done")

    def test_run_once_executes_highest_priority_first(self):
        self.sched.add_task("low", lambda: "low", priority=10)
        self.sched.add_task("high", lambda: "high", priority=1)
        self.sched.add_task("med", lambda: "med", priority=5)
        task = self.sched.run_once()
        self.assertEqual(task.name, "high")
        self.assertEqual(task.result, "high")

    def test_run_once_marks_error_on_exception(self):
        def failing():
            raise ValueError("boom")

        self.sched.add_task("fail", failing)
        task = self.sched.run_once()
        self.assertEqual(task.status, "error")
        self.assertIn("boom", task.error)

    def test_run_once_does_not_rerun_completed(self):
        self.sched.add_task("once", lambda: "done")
        self.sched.run_once()
        # Second run should return None (no pending tasks)
        result = self.sched.run_once()
        self.assertIsNone(result)

    # ── run_all ───────────────────────────────────────────────────────

    def test_run_all_executes_all_tasks(self):
        results = []
        self.sched.add_task("a", lambda: results.append("a"))
        self.sched.add_task("b", lambda: results.append("b"))
        self.sched.add_task("c", lambda: results.append("c"))
        self.sched.run_all()
        self.assertEqual(len(results), 3)

    def test_run_all_respects_priority_order(self):
        order = []
        self.sched.add_task("third", lambda: order.append(3), priority=10)
        self.sched.add_task("first", lambda: order.append(1), priority=1)
        self.sched.add_task("second", lambda: order.append(2), priority=5)
        self.sched.run_all()
        self.assertEqual(order, [1, 2, 3])

    def test_run_all_on_empty_scheduler(self):
        # Should not raise
        self.sched.run_all()

    def test_run_all_handles_mixed_success_and_failure(self):
        self.sched.add_task("ok", lambda: "fine")
        self.sched.add_task("fail", lambda: 1 / 0)
        self.sched.add_task("ok2", lambda: "also fine")
        self.sched.run_all()
        statuses = {s["name"]: s["status"] for s in self.sched.get_status()}
        self.assertEqual(statuses["ok"], "done")
        self.assertEqual(statuses["fail"], "error")
        self.assertEqual(statuses["ok2"], "done")

    # ── run_in_thread ─────────────────────────────────────────────────

    def test_run_in_thread_returns_thread(self):
        self.sched.add_task("bg", lambda: 1)
        thread = self.sched.run_in_thread()
        self.assertIsInstance(thread, threading.Thread)
        thread.join(timeout=5)
        self.assertFalse(thread.is_alive())

    def test_run_in_thread_executes_tasks(self):
        container = []
        self.sched.add_task("threaded", lambda: container.append("ran"))
        thread = self.sched.run_in_thread()
        thread.join(timeout=5)
        self.assertEqual(container, ["ran"])

    # ── Status transitions ────────────────────────────────────────────

    def test_status_transitions(self):
        self.sched.add_task("lifecycle", lambda: "result")
        # Before run: pending
        s = self.sched.get_status()
        self.assertEqual(s[0]["status"], "pending")
        # After run: done
        self.sched.run_once()
        s = self.sched.get_status()
        self.assertEqual(s[0]["status"], "done")


if __name__ == "__main__":
    unittest.main()
