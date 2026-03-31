"""Tests for aura_os.kernel.memory — MemoryTracker."""

import io
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault("AURA_HOME", str(Path(tempfile.gettempdir()) / "aura_os_test"))

from aura_os.kernel.memory import MemoryTracker


class TestMemoryTrackerSystemMemory(unittest.TestCase):
    """Tests for MemoryTracker.get_system_memory()."""

    def test_returns_dict(self):
        result = MemoryTracker.get_system_memory()
        self.assertIsInstance(result, dict)

    def test_has_required_keys(self):
        result = MemoryTracker.get_system_memory()
        for key in ("total", "available", "used", "percent"):
            self.assertIn(key, result)

    def test_total_is_positive(self):
        result = MemoryTracker.get_system_memory()
        # On Linux CI, /proc/meminfo should be available
        self.assertGreater(result["total"], 0)

    def test_percent_is_reasonable(self):
        result = MemoryTracker.get_system_memory()
        self.assertGreaterEqual(result["percent"], 0)
        self.assertLessEqual(result["percent"], 100)


class TestMemoryTrackerProcMeminfo(unittest.TestCase):
    """Tests for _read_proc_meminfo with mocked /proc/meminfo."""

    def test_parses_proc_meminfo(self):
        fake_meminfo = (
            "MemTotal:       8192000 kB\n"
            "MemFree:        2048000 kB\n"
            "MemAvailable:   4096000 kB\n"
            "Buffers:         512000 kB\n"
        )
        with mock.patch("builtins.open", mock.mock_open(read_data=fake_meminfo)):
            result = MemoryTracker._read_proc_meminfo()
        self.assertEqual(result["total"], 8192000 * 1024)
        self.assertEqual(result["available"], 4096000 * 1024)
        self.assertEqual(result["used"], (8192000 - 4096000) * 1024)

    def test_returns_empty_dict_on_oserror(self):
        with mock.patch("builtins.open", side_effect=OSError("no such file")):
            result = MemoryTracker._read_proc_meminfo()
        self.assertEqual(result, {})

    def test_handles_missing_mem_available(self):
        """Falls back to MemFree when MemAvailable is absent."""
        fake_meminfo = (
            "MemTotal:       4096000 kB\n"
            "MemFree:        1024000 kB\n"
        )
        with mock.patch("builtins.open", mock.mock_open(read_data=fake_meminfo)):
            result = MemoryTracker._read_proc_meminfo()
        self.assertEqual(result["available"], 1024000 * 1024)


class TestMemoryTrackerProcessMemory(unittest.TestCase):
    """Tests for MemoryTracker.get_process_memory()."""

    def test_returns_dict(self):
        result = MemoryTracker.get_process_memory()
        self.assertIsInstance(result, dict)

    def test_has_rss_and_pid(self):
        result = MemoryTracker.get_process_memory()
        self.assertIn("rss", result)
        self.assertIn("pid", result)

    def test_pid_matches_current_process(self):
        result = MemoryTracker.get_process_memory()
        self.assertEqual(result["pid"], os.getpid())

    def test_rss_is_non_negative(self):
        result = MemoryTracker.get_process_memory()
        self.assertGreaterEqual(result["rss"], 0)


class TestMemoryTrackerContextManager(unittest.TestCase):
    """Tests for MemoryTracker.track() context manager."""

    def test_track_prints_output(self):
        tracker = MemoryTracker()
        with mock.patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
            with tracker.track("test-block"):
                _ = [0] * 100
        output = mock_stdout.getvalue()
        self.assertIn("[memory:test-block]", output)
        self.assertIn("KB", output)

    def test_track_default_label(self):
        tracker = MemoryTracker()
        with mock.patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
            with tracker.track():
                pass
        output = mock_stdout.getvalue()
        self.assertIn("[memory:block]", output)

    def test_track_does_not_suppress_exceptions(self):
        tracker = MemoryTracker()
        with self.assertRaises(ValueError):
            with tracker.track("fail"):
                raise ValueError("inner error")


if __name__ == "__main__":
    unittest.main()
