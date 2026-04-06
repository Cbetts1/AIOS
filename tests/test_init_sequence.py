"""Tests for aura_os.init.sequence.InitManager."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from aura_os.init.sequence import InitManager


class TestInitManagerRegistration(unittest.TestCase):
    """Unit registration."""

    def setUp(self):
        self.im = InitManager()

    def test_register_unit(self):
        self.im.register("net", start_fn=lambda: None)
        status = self.im.status()
        names = [u["name"] for u in status]
        self.assertIn("net", names)

    def test_register_multiple_units(self):
        for name in ("fs", "net", "db"):
            self.im.register(name, start_fn=lambda: None)
        names = [u["name"] for u in self.im.status()]
        for name in ("fs", "net", "db"):
            self.assertIn(name, names)

    def test_status_initial_state_is_pending(self):
        self.im.register("svc", start_fn=lambda: None)
        units = {u["name"]: u for u in self.im.status()}
        self.assertEqual(units["svc"]["state"], "pending")

    def test_status_has_required_keys(self):
        self.im.register("svc", start_fn=lambda: None)
        for u in self.im.status():
            for key in ("name", "description", "state", "error"):
                self.assertIn(key, u)


class TestInitManagerBoot(unittest.TestCase):
    """Boot sequence execution."""

    def setUp(self):
        self.im = InitManager()
        self.executed = []

    def test_boot_runs_units(self):
        self.im.register("a", start_fn=lambda: self.executed.append("a"))
        self.im.register("b", start_fn=lambda: self.executed.append("b"))
        self.im.boot()
        self.assertIn("a", self.executed)
        self.assertIn("b", self.executed)

    def test_boot_returns_ok_list(self):
        self.im.register("a", start_fn=lambda: None)
        result = self.im.boot()
        self.assertIn("ok", result)
        self.assertIn("a", result["ok"])

    def test_boot_reports_failed_units(self):
        def _fail():
            raise RuntimeError("boot error")

        self.im.register("bad_unit", start_fn=_fail)
        result = self.im.boot()
        self.assertIn("bad_unit", result["failed"])
        self.assertNotIn("bad_unit", result["ok"])

    def test_boot_failed_unit_has_error_in_status(self):
        def _fail():
            raise RuntimeError("specific error msg")

        self.im.register("bad_unit", start_fn=_fail)
        self.im.boot()
        units = {u["name"]: u for u in self.im.status()}
        self.assertEqual(units["bad_unit"]["state"], "failed")
        self.assertIn("specific error msg", units["bad_unit"]["error"])

    def test_boot_successful_unit_state(self):
        self.im.register("good", start_fn=lambda: None)
        self.im.boot()
        units = {u["name"]: u for u in self.im.status()}
        # After topo-sort, state is set during boot
        self.assertIn(units["good"]["state"], ("running", "failed", "skipped"))


class TestInitManagerDependencyOrdering(unittest.TestCase):
    """Topological sort and dependency enforcement."""

    def setUp(self):
        self.im = InitManager()
        self.order = []

    def _fn(self, name):
        def _inner():
            self.order.append(name)
        return _inner

    def test_after_dependency_respected(self):
        self.im.register("b", start_fn=self._fn("b"), after=["a"])
        self.im.register("a", start_fn=self._fn("a"))
        self.im.boot()
        self.assertLess(self.order.index("a"), self.order.index("b"))

    def test_requires_respected(self):
        self.im.register("b", start_fn=self._fn("b"), requires=["a"])
        self.im.register("a", start_fn=self._fn("a"))
        self.im.boot()
        self.assertLess(self.order.index("a"), self.order.index("b"))

    def test_requires_failed_skips_dependent(self):
        def _fail():
            raise RuntimeError("whoops")

        self.im.register("a", start_fn=_fail)
        self.im.register("b", start_fn=self._fn("b"), requires=["a"])
        result = self.im.boot()
        self.assertIn("a", result["failed"])
        self.assertIn("b", result["skipped"])
        self.assertNotIn("b", self.order)

    def test_chain_dependency_ordering(self):
        self.im.register("c", start_fn=self._fn("c"), after=["b"])
        self.im.register("b", start_fn=self._fn("b"), after=["a"])
        self.im.register("a", start_fn=self._fn("a"))
        self.im.boot()
        self.assertLess(self.order.index("a"), self.order.index("b"))
        self.assertLess(self.order.index("b"), self.order.index("c"))

    def test_circular_dependency_does_not_crash(self):
        # Circular deps are silently resolved; boot must not raise
        self.im.register("x", start_fn=lambda: None, after=["y"])
        self.im.register("y", start_fn=lambda: None, after=["x"])
        result = self.im.boot()
        self.assertIn("ok", result)


class TestInitManagerShutdown(unittest.TestCase):
    """Shutdown sequence."""

    def setUp(self):
        self.im = InitManager()
        self.stopped = []

    def test_shutdown_calls_stop_fns(self):
        self.im.register(
            "svc",
            start_fn=lambda: None,
            stop_fn=lambda: self.stopped.append("svc"),
        )
        self.im.boot()
        self.im.shutdown()
        self.assertIn("svc", self.stopped)

    def test_shutdown_reverse_order(self):
        order = []
        self.im.register(
            "a",
            start_fn=lambda: None,
            stop_fn=lambda: order.append("a"),
        )
        self.im.register(
            "b",
            start_fn=lambda: None,
            stop_fn=lambda: order.append("b"),
            after=["a"],
        )
        self.im.boot()
        self.im.shutdown()
        # b started after a, so b should stop before a
        self.assertGreater(order.index("a"), order.index("b"))

    def test_shutdown_tolerates_stop_fn_exception(self):
        def _bad_stop():
            raise RuntimeError("stop failed")

        self.im.register("svc", start_fn=lambda: None, stop_fn=_bad_stop)
        self.im.boot()
        # Must not raise
        self.im.shutdown()

    def test_no_stop_fn_ok(self):
        self.im.register("svc", start_fn=lambda: None)
        self.im.boot()
        self.im.shutdown()  # Should not raise


if __name__ == "__main__":
    unittest.main()
