"""Tests for aura_os/kernel/scheduler.py — cooperative task scheduler."""

import os
import sys
import threading
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from aura_os.kernel.scheduler import Scheduler, Task


class TestTask(unittest.TestCase):
    """Tests for the Task dataclass."""

    def test_default_status(self):
        task = Task(id="t1", name="test", func=lambda: None)
        self.assertEqual(task.status, "pending")

    def test_default_priority(self):
        task = Task(id="t1", name="test", func=lambda: None)
        self.assertEqual(task.priority, 5)

    def test_default_result_and_error_are_none(self):
        task = Task(id="t1", name="test", func=lambda: None)
        self.assertIsNone(task.result)
        self.assertIsNone(task.error)


class TestScheduler(unittest.TestCase):
    """Tests for the Scheduler."""

    def setUp(self):
        self.sched = Scheduler()

    # ------------------------------------------------------------------
    # add_task / get_status
    # ------------------------------------------------------------------

    def test_add_task_returns_id(self):
        task_id = self.sched.add_task("hello", lambda: None)
        self.assertIsNotNone(task_id)
        self.assertTrue(task_id.startswith("task-"))

    def test_add_task_increments_counter(self):
        id1 = self.sched.add_task("t1", lambda: None)
        id2 = self.sched.add_task("t2", lambda: None)
        n1 = int(id1.split("-")[1])
        n2 = int(id2.split("-")[1])
        self.assertEqual(n2, n1 + 1)

    def test_get_status_empty(self):
        self.assertEqual(self.sched.get_status(), [])

    def test_get_status_lists_added_task(self):
        self.sched.add_task("mytask", lambda: 42)
        statuses = self.sched.get_status()
        self.assertEqual(len(statuses), 1)
        self.assertEqual(statuses[0]["name"], "mytask")
        self.assertEqual(statuses[0]["status"], "pending")

    def test_get_status_fields(self):
        self.sched.add_task("check", lambda: None, priority=3)
        s = self.sched.get_status()[0]
        for field in ("id", "name", "status", "priority", "error"):
            self.assertIn(field, s)
        self.assertEqual(s["priority"], 3)

    # ------------------------------------------------------------------
    # run_once
    # ------------------------------------------------------------------

    def test_run_once_returns_none_when_empty(self):
        result = self.sched.run_once()
        self.assertIsNone(result)

    def test_run_once_executes_task(self):
        called = []
        self.sched.add_task("run_me", lambda: called.append(True))
        task = self.sched.run_once()
        self.assertIsNotNone(task)
        self.assertTrue(called)
        self.assertEqual(task.status, "done")

    def test_run_once_sets_result(self):
        self.sched.add_task("result_task", lambda: 99)
        task = self.sched.run_once()
        self.assertEqual(task.result, 99)

    def test_run_once_handles_exception(self):
        def bad():
            raise ValueError("boom")

        self.sched.add_task("bad_task", bad)
        task = self.sched.run_once()
        self.assertEqual(task.status, "error")
        self.assertIn("boom", task.error)

    def test_run_once_returns_none_after_all_done(self):
        self.sched.add_task("one", lambda: None)
        self.sched.run_once()
        result = self.sched.run_once()
        self.assertIsNone(result)

    # ------------------------------------------------------------------
    # priority ordering
    # ------------------------------------------------------------------

    def test_run_once_respects_priority(self):
        order = []
        self.sched.add_task("low", lambda: order.append("low"), priority=10)
        self.sched.add_task("high", lambda: order.append("high"), priority=1)
        self.sched.add_task("mid", lambda: order.append("mid"), priority=5)
        self.sched.run_all()
        self.assertEqual(order, ["high", "mid", "low"])

    def test_equal_priority_tasks_all_run(self):
        results = []
        self.sched.add_task("a", lambda: results.append("a"), priority=5)
        self.sched.add_task("b", lambda: results.append("b"), priority=5)
        self.sched.run_all()
        self.assertIn("a", results)
        self.assertIn("b", results)

    # ------------------------------------------------------------------
    # run_all
    # ------------------------------------------------------------------

    def test_run_all_processes_all_tasks(self):
        results = []
        for i in range(5):
            self.sched.add_task(f"t{i}", lambda i=i: results.append(i))
        self.sched.run_all()
        self.assertEqual(len(results), 5)

    def test_run_all_on_empty_scheduler_does_not_raise(self):
        self.sched.run_all()  # should not raise

    # ------------------------------------------------------------------
    # run_in_thread
    # ------------------------------------------------------------------

    def test_run_in_thread_returns_thread(self):
        self.sched.add_task("bg", lambda: time.sleep(0))
        t = self.sched.run_in_thread()
        self.assertIsInstance(t, threading.Thread)
        t.join(timeout=3)
        self.assertFalse(t.is_alive())

    def test_run_in_thread_completes_tasks(self):
        results = []
        for i in range(3):
            self.sched.add_task(f"bg{i}", lambda i=i: results.append(i))
        t = self.sched.run_in_thread()
        t.join(timeout=5)
        self.assertEqual(len(results), 3)

    # ------------------------------------------------------------------
    # thread safety
    # ------------------------------------------------------------------

    def test_add_task_thread_safe(self):
        ids = []
        lock = threading.Lock()

        def adder():
            tid = self.sched.add_task("concurrent", lambda: None)
            with lock:
                ids.append(tid)

        threads = [threading.Thread(target=adder) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(ids), 20)
        self.assertEqual(len(set(ids)), 20)  # all IDs unique


if __name__ == "__main__":
    unittest.main()
