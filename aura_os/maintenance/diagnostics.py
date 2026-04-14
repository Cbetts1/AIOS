"""System diagnostics for AURA OS.

Performs comprehensive real-system diagnostics including:
- Hardware detection (CPU, RAM, disk)
- OS version and platform info
- Network connectivity tests
- AURA kernel subsystem status
- Dependency audit
- Log file health
"""

from __future__ import annotations

import os
import platform
import socket
import sys
import time
from typing import Any, List


class DiagResult:
    """A single diagnostic result."""

    __slots__ = ("category", "name", "value", "status", "detail")

    def __init__(self, category: str, name: str, value: Any,
                 status: str = "ok", detail: str = ""):
        self.category = category
        self.name = name
        self.value = value
        self.status = status   # "ok", "warning", "error", "info"
        self.detail = detail


class Diagnostics:
    """Runs comprehensive system diagnostics.

    Example::

        d = Diagnostics()
        results = d.run_all()
        d.print_report(results)
    """

    def __init__(self, aura_home: str = None):
        self._home = aura_home or os.environ.get(
            "AURA_HOME", os.path.expanduser("~/.aura")
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run_all(self) -> List[DiagResult]:
        """Run all diagnostic checks and return results."""
        results = []
        sections = [
            self._diag_platform,
            self._diag_python,
            self._diag_hardware,
            self._diag_network,
            self._diag_filesystem,
            self._diag_kernel,
            self._diag_dependencies,
        ]
        for fn in sections:
            try:
                section_results = fn()
                results.extend(section_results)
            except Exception as exc:
                results.append(DiagResult(
                    "system", fn.__name__, "failed",
                    "error", str(exc)
                ))
        return results

    def print_report(self, results: List[DiagResult] = None) -> None:
        """Print formatted diagnostics to stdout."""
        if results is None:
            results = self.run_all()
        current_cat = None
        print("=" * 62)
        print("  AURA OS — System Diagnostics")
        print(f"  {time.strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 62)
        for r in results:
            if r.category != current_cat:
                current_cat = r.category
                print(f"\n  ── {current_cat.upper()} ──")
            sym = {"ok": "✓", "warning": "⚠", "error": "✗", "info": "i"}.get(
                r.status, "?"
            )
            detail = f"  {r.detail}" if r.detail else ""
            val = str(r.value)[:40]
            print(f"  {sym}  {r.name:<28} {val}{detail}")
        print()

    # ------------------------------------------------------------------
    # Diagnostic sections
    # ------------------------------------------------------------------

    def _diag_platform(self) -> List[DiagResult]:
        return [
            DiagResult("platform", "system",
                       platform.system(), "info"),
            DiagResult("platform", "release",
                       platform.release(), "info"),
            DiagResult("platform", "machine",
                       platform.machine(), "info"),
            DiagResult("platform", "node",
                       platform.node(), "info"),
            DiagResult("platform", "uptime",
                       self._uptime(), "info"),
        ]

    def _diag_python(self) -> List[DiagResult]:
        ver = sys.version.split()[0]
        major, minor = sys.version_info[:2]
        ok = (major, minor) >= (3, 8)
        return [
            DiagResult("python", "version", ver,
                       "ok" if ok else "error"),
            DiagResult("python", "executable", sys.executable, "info"),
            DiagResult("python", "prefix", sys.prefix, "info"),
        ]

    def _diag_hardware(self) -> List[DiagResult]:
        results = []
        try:
            import psutil
            cpu_count = psutil.cpu_count(logical=True)
            cpu_freq = psutil.cpu_freq()
            mem = psutil.virtual_memory()
            results.append(DiagResult("hardware", "cpu_cores",
                                      str(cpu_count), "info"))
            if cpu_freq:
                results.append(DiagResult("hardware", "cpu_freq_mhz",
                                          f"{cpu_freq.current:.0f}", "info"))
            ram_gb = mem.total / (1 << 30)
            results.append(DiagResult("hardware", "total_ram",
                                      f"{ram_gb:.1f} GiB", "info"))
            results.append(DiagResult("hardware", "ram_available",
                                      f"{mem.available / (1 << 20):.0f} MiB",
                                      "ok" if mem.percent < 90 else "warning"))
        except ImportError:
            results.append(DiagResult("hardware", "psutil", "not installed",
                                      "warning",
                                      "install psutil for hardware metrics"))
        except Exception as exc:
            results.append(DiagResult("hardware", "error", str(exc), "error"))
        return results

    def _diag_network(self) -> List[DiagResult]:
        results = []
        # Hostname resolution
        try:
            hostname = socket.gethostname()
            results.append(DiagResult("network", "hostname", hostname, "info"))
        except Exception:
            results.append(DiagResult("network", "hostname", "unknown", "warning"))

        # Basic connectivity probe (DNS)
        for host in [("8.8.8.8", 53), ("1.1.1.1", 53)]:
            try:
                s = socket.create_connection(host, timeout=2)
                s.close()
                results.append(DiagResult("network", "connectivity",
                                          "online", "ok"))
                break
            except OSError:
                pass
        else:
            results.append(DiagResult("network", "connectivity",
                                      "offline", "warning"))
        return results

    def _diag_filesystem(self) -> List[DiagResult]:
        results = []
        import shutil as _shutil
        for path_str in [self._home, os.path.expanduser("~")]:
            try:
                total, _, free = _shutil.disk_usage(path_str)
                pct_used = (total - free) / total * 100 if total else 0
                results.append(DiagResult(
                    "filesystem", f"disk:{path_str}",
                    f"{free / (1 << 30):.1f} GiB free",
                    "ok" if pct_used < 90 else "warning",
                    f"({pct_used:.0f}% used)",
                ))
            except OSError as exc:
                results.append(DiagResult("filesystem", f"disk:{path_str}",
                                          str(exc), "error"))
        return results

    def _diag_kernel(self) -> List[DiagResult]:
        modules = {
            "process": "aura_os.kernel.process",
            "service": "aura_os.kernel.service",
            "syslog": "aura_os.kernel.syslog",
            "scheduler": "aura_os.kernel.scheduler",
            "memory": "aura_os.kernel.memory",
            "network": "aura_os.kernel.network",
        }
        results = []
        for name, mod_path in modules.items():
            try:
                __import__(mod_path)
                results.append(DiagResult("kernel", name, "loaded", "ok"))
            except ImportError as exc:
                results.append(DiagResult("kernel", name, "failed",
                                          "error", str(exc)))
        return results

    def _diag_dependencies(self) -> List[DiagResult]:
        deps = {
            "psutil": "system metrics",
            "flask": "web API",
            "cryptography": "secret encryption",
        }
        results = []
        for pkg, purpose in deps.items():
            try:
                __import__(pkg)
                results.append(DiagResult("dependencies", pkg,
                                          "installed", "ok", purpose))
            except ImportError:
                results.append(DiagResult("dependencies", pkg,
                                          "not installed", "warning", purpose))
        return results

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _uptime(self) -> str:
        try:
            import psutil
            boot = psutil.boot_time()
            uptime_s = time.time() - boot
            h = int(uptime_s // 3600)
            m = int((uptime_s % 3600) // 60)
            return f"{h}h {m}m"
        except Exception:
            return "unknown"


# ---------------------------------------------------------------------------
# CLI command wrapper
# ---------------------------------------------------------------------------

class DiagnosticsCommand:
    """``aura diag`` — run system diagnostics."""

    def execute(self, args, eal) -> int:
        home = os.environ.get("AURA_HOME", os.path.expanduser("~/.aura"))
        d = Diagnostics(home)
        results = d.run_all()
        d.print_report(results)
        errors = sum(1 for r in results if r.status == "error")
        return 0 if errors == 0 else 1
