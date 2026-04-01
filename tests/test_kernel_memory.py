"""Tests for aura_os/kernel/memory.py — MemoryTracker."""

import io
import os
import sys
import unittest
from unittest.mock import MagicMock, mock_open, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from aura_os.kernel.memory import MemoryTracker


class TestGetSystemMemory(unittest.TestCase):
    """Tests for MemoryTracker.get_system_memory()."""

    def test_returns_dict(self):
        result = MemoryTracker.get_system_memory()
        self.assertIsInstance(result, dict)

    def test_has_required_keys(self):
        result = MemoryTracker.get_system_memory()
        for key in ("total", "available", "used", "percent"):
            self.assertIn(key, result)

    def test_values_are_numeric(self):
        result = MemoryTracker.get_system_memory()
        self.assertIsInstance(result["total"], (int, float))
        self.assertIsInstance(result["percent"], (int, float))

    def test_percent_in_valid_range(self):
        result = MemoryTracker.get_system_memory()
        self.assertGreaterEqual(result["percent"], 0.0)
        self.assertLessEqual(result["percent"], 100.0)

    def test_fallback_when_proc_missing(self):
        with patch("builtins.open", side_effect=OSError("no /proc")):
            result = MemoryTracker.get_system_memory()
        # Should not raise; may return zeros or psutil values
        self.assertIsInstance(result, dict)

    def test_psutil_fallback_returns_valid_dict(self):
        """When /proc/meminfo is unavailable, psutil (if present) is used."""
        with patch("builtins.open", side_effect=OSError):
            try:
                import psutil  # noqa: F401
                result = MemoryTracker.get_system_memory()
                self.assertIn("total", result)
            except ImportError:
                pass  # psutil not installed; skip


class TestReadProcMeminfo(unittest.TestCase):
    """Tests for MemoryTracker._read_proc_meminfo()."""

    def test_parses_well_formed_meminfo(self):
        fake_meminfo = (
            "MemTotal:       16000000 kB\n"
            "MemFree:          500000 kB\n"
            "MemAvailable:    4000000 kB\n"
            "Buffers:          200000 kB\n"
        )
        with patch("builtins.open", mock_open(read_data=fake_meminfo)):
            result = MemoryTracker._read_proc_meminfo()
        self.assertEqual(result["total"], 16000000 * 1024)
        self.assertEqual(result["available"], 4000000 * 1024)
        self.assertGreater(result["used"], 0)
        self.assertGreaterEqual(result["percent"], 0.0)

    def test_returns_empty_dict_on_oserror(self):
        with patch("builtins.open", side_effect=OSError):
            result = MemoryTracker._read_proc_meminfo()
        self.assertEqual(result, {})

    def test_uses_memfree_when_memavailable_missing(self):
        fake_meminfo = (
            "MemTotal:       8000000 kB\n"
            "MemFree:        2000000 kB\n"
        )
        with patch("builtins.open", mock_open(read_data=fake_meminfo)):
            result = MemoryTracker._read_proc_meminfo()
        self.assertEqual(result["available"], 2000000 * 1024)

    def test_percent_zero_when_total_zero(self):
        fake_meminfo = "MemTotal: 0 kB\nMemFree: 0 kB\n"
        with patch("builtins.open", mock_open(read_data=fake_meminfo)):
            result = MemoryTracker._read_proc_meminfo()
        self.assertEqual(result.get("percent", 0.0), 0.0)


class TestGetProcessMemory(unittest.TestCase):
    """Tests for MemoryTracker.get_process_memory()."""

    def test_returns_dict_with_rss_and_pid(self):
        result = MemoryTracker.get_process_memory()
        self.assertIn("rss", result)
        self.assertIn("pid", result)

    def test_pid_matches_current_process(self):
        result = MemoryTracker.get_process_memory()
        self.assertEqual(result["pid"], os.getpid())

    def test_rss_is_positive(self):
        result = MemoryTracker.get_process_memory()
        self.assertGreaterEqual(result["rss"], 0)

    def test_fallback_to_resource_module(self):
        with patch("builtins.open", side_effect=OSError):
            result = MemoryTracker.get_process_memory()
        self.assertIn("rss", result)
        self.assertGreaterEqual(result["rss"], 0)


class TestTrackContextManager(unittest.TestCase):
    """Tests for MemoryTracker.track() context manager."""

    def test_track_does_not_raise(self):
        tracker = MemoryTracker()
        with tracker.track("unit_test"):
            _ = list(range(1000))

    def test_track_prints_output(self, ):
        tracker = MemoryTracker()
        import io
        from contextlib import redirect_stdout
        buf = io.StringIO()
        with redirect_stdout(buf):
            with tracker.track("my_block"):
                pass
        output = buf.getvalue()
        self.assertIn("memory:my_block", output)
        self.assertIn("KB", output)

    def test_track_custom_label(self):
        tracker = MemoryTracker()
        from contextlib import redirect_stdout
        buf = io.StringIO()
        with redirect_stdout(buf):
            with tracker.track("custom_label"):
                pass
        self.assertIn("custom_label", buf.getvalue())

    def test_track_default_label(self):
        tracker = MemoryTracker()
        from contextlib import redirect_stdout
        buf = io.StringIO()
        with redirect_stdout(buf):
            with tracker.track():
                pass
        self.assertIn("block", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
