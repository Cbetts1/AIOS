"""Memory usage tracking for AURA OS kernel."""

import contextlib
import os
import resource
from typing import Dict


class MemoryTracker:
    """Utilities for inspecting memory usage.

    Reads /proc/meminfo for system-level data and uses the ``resource``
    module for per-process data.  ``psutil`` is used opportunistically if
    available, but is never required.
    """

    # ------------------------------------------------------------------
    # System memory
    # ------------------------------------------------------------------

    @staticmethod
    def get_system_memory() -> Dict:
        """Return system-wide memory statistics.

        Tries /proc/meminfo first; falls back to psutil if present.
        All sizes are in bytes unless noted otherwise in the key name.
        """
        info = MemoryTracker._read_proc_meminfo()
        if info:
            return info

        # Optional psutil fallback
        try:
            import psutil  # type: ignore
            vm = psutil.virtual_memory()
            return {
                "total": vm.total,
                "available": vm.available,
                "used": vm.used,
                "percent": vm.percent,
            }
        except ImportError:
            pass

        return {"total": 0, "available": 0, "used": 0, "percent": 0.0}

    @staticmethod
    def _read_proc_meminfo() -> Dict:
        """Parse /proc/meminfo into a memory summary dict (bytes)."""
        raw: Dict = {}
        try:
            with open("/proc/meminfo", "r", encoding="utf-8") as fh:
                for line in fh:
                    parts = line.split()
                    if len(parts) >= 2:
                        key = parts[0].rstrip(":")
                        try:
                            raw[key] = int(parts[1]) * 1024  # kB → bytes
                        except ValueError:
                            pass
        except OSError:
            return {}

        total = raw.get("MemTotal", 0)
        available = raw.get("MemAvailable", raw.get("MemFree", 0))
        used = total - available
        percent = (used / total * 100) if total else 0.0
        return {
            "total": total,
            "available": available,
            "used": used,
            "percent": round(percent, 1),
        }

    # ------------------------------------------------------------------
    # Process memory
    # ------------------------------------------------------------------

    @staticmethod
    def get_process_memory() -> Dict:
        """Return memory usage for the current process (bytes)."""
        pid = os.getpid()

        # Try /proc/<pid>/status
        try:
            with open(f"/proc/{pid}/status", "r", encoding="utf-8") as fh:
                for line in fh:
                    if line.startswith("VmRSS:"):
                        rss_kb = int(line.split()[1])
                        return {"rss": rss_kb * 1024, "pid": pid}
        except OSError:
            pass

        # Fall back to resource module (maxrss is in KB on Linux, bytes on macOS)
        try:
            usage = resource.getrusage(resource.RUSAGE_SELF)
            import platform
            if platform.system() == "Darwin":
                rss = usage.ru_maxrss
            else:
                rss = usage.ru_maxrss * 1024
            return {"rss": rss, "pid": pid}
        except Exception:  # noqa: BLE001
            pass

        return {"rss": 0, "pid": pid}

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    @contextlib.contextmanager
    def track(self, label: str = "block"):
        """Context manager that prints memory delta for the wrapped block."""
        before = self.get_process_memory().get("rss", 0)
        try:
            yield
        finally:
            after = self.get_process_memory().get("rss", 0)
            delta = after - before
            sign = "+" if delta >= 0 else ""
            print(f"[memory:{label}] {sign}{delta / 1024:.1f} KB")
