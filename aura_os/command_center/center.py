"""Real operator Command Center for AURA OS.

Provides a unified system status dashboard and operator control interface.
All data is sourced from live kernel subsystems — no simulation.
"""

from __future__ import annotations

import os
import time
from typing import List


def _fmt_bytes(n: float) -> str:
    for unit, thr in (("GiB", 1 << 30), ("MiB", 1 << 20), ("KiB", 1 << 10)):
        if n >= thr:
            return f"{n / thr:.1f} {unit}"
    return f"{n:.0f} B"


def _bar(pct: float, width: int = 20) -> str:
    filled = int(min(pct, 100) / 100 * width)
    return "[" + "█" * filled + "░" * (width - filled) + f"] {pct:.1f}%"


class CommandCenter:
    """Operator Command Center.

    Aggregates live system data from kernel subsystems and presents it as
    a structured dashboard.  The center itself does not duplicate kernel
    logic — it reads from existing AURA kernel modules.

    Args:
        eal: The Environment Abstraction Layer instance.
    """

    def __init__(self, eal=None):
        self._eal = eal

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def show(self) -> None:
        """Print a one-shot system status dashboard to stdout."""
        self._render_dashboard()

    def run_tui(self, interval: float = 3.0) -> None:
        """Run an interactive refresh loop.  Press Ctrl-C to exit."""
        try:
            while True:
                os.system("clear" if os.name != "nt" else "cls")
                self._render_dashboard()
                print(f"\n  [Refreshing every {interval:.0f}s — Ctrl-C to exit]")
                time.sleep(interval)
        except KeyboardInterrupt:
            print("\n[command_center] Exited.")

    def summary(self) -> dict:
        """Return a dict with key system metrics for programmatic use."""
        return {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "cpu": self._cpu_summary(),
            "memory": self._memory_summary(),
            "disk": self._disk_summary(),
            "processes": self._process_count(),
            "services": self._service_summary(),
            "network": self._network_status(),
            "health": self._health_score(),
        }

    # ------------------------------------------------------------------
    # Dashboard rendering
    # ------------------------------------------------------------------

    def _render_dashboard(self) -> None:
        width = 60
        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        print("=" * width)
        print("  AURA OS — Command Center")
        print(f"  {ts}")
        print("=" * width)
        self._section_system()
        self._section_cpu()
        self._section_memory()
        self._section_disk()
        self._section_processes()
        self._section_services()
        self._section_network()
        self._section_logs()
        print("=" * width)

    # ------------------------------------------------------------------
    # System info
    # ------------------------------------------------------------------

    def _section_system(self) -> None:
        print("\n  ── System ──")
        try:
            import platform
            print(f"  OS       : {platform.system()} {platform.release()}")
            print(f"  Python   : {platform.python_version()}")
            print(f"  Node     : {platform.node()}")
        except Exception:
            print("  System info unavailable.")
        if self._eal:
            try:
                info = self._eal.get_env_info()
                env_type = info.get("env_type", "unknown")
                print(f"  Env type : {env_type}")
            except Exception:
                pass

    # ------------------------------------------------------------------
    # CPU
    # ------------------------------------------------------------------

    def _section_cpu(self) -> None:
        print("\n  ── CPU ──")
        summary = self._cpu_summary()
        if "error" in summary:
            print(f"  {summary['error']}")
            return
        if summary.get("percent") is not None:
            print(f"  Overall  : {_bar(summary['percent'])}")
        if summary.get("load_avg"):
            la = summary["load_avg"]
            print(f"  Load avg : {la[0]:.2f}  {la[1]:.2f}  {la[2]:.2f}  (1/5/15 min)")
        if summary.get("cores"):
            for i, pct in enumerate(summary["cores"][:8]):
                print(f"  Core {i:<3}  : {_bar(pct, 15)}")

    def _cpu_summary(self) -> dict:
        try:
            import psutil
            pct = psutil.cpu_percent(interval=0.2)
            cores = psutil.cpu_percent(interval=0.2, percpu=True)
            la = os.getloadavg() if hasattr(os, "getloadavg") else None
            return {"percent": pct, "cores": cores, "load_avg": la}
        except ImportError:
            try:
                la = os.getloadavg() if hasattr(os, "getloadavg") else None
                return {"load_avg": la}
            except Exception:
                return {"error": "CPU info unavailable (install psutil for full data)"}
        except Exception as exc:
            return {"error": str(exc)}

    # ------------------------------------------------------------------
    # Memory
    # ------------------------------------------------------------------

    def _section_memory(self) -> None:
        print("\n  ── Memory ──")
        summary = self._memory_summary()
        if "error" in summary:
            print(f"  {summary['error']}")
            return
        if summary.get("total"):
            print(f"  RAM      : {_bar(summary['percent'])} "
                  f"  {_fmt_bytes(summary['used'])} / {_fmt_bytes(summary['total'])}")
        if summary.get("swap_total"):
            print(f"  Swap     : {_bar(summary['swap_percent'])} "
                  f"  {_fmt_bytes(summary['swap_used'])} / {_fmt_bytes(summary['swap_total'])}")

    def _memory_summary(self) -> dict:
        try:
            import psutil
            vm = psutil.virtual_memory()
            sw = psutil.swap_memory()
            return {
                "total": vm.total,
                "used": vm.used,
                "available": vm.available,
                "percent": vm.percent,
                "swap_total": sw.total,
                "swap_used": sw.used,
                "swap_percent": sw.percent,
            }
        except ImportError:
            return {"error": "Memory info unavailable (install psutil for full data)"}
        except Exception as exc:
            return {"error": str(exc)}

    # ------------------------------------------------------------------
    # Disk
    # ------------------------------------------------------------------

    def _section_disk(self) -> None:
        print("\n  ── Storage ──")
        summary = self._disk_summary()
        if "error" in summary:
            print(f"  {summary['error']}")
            return
        for entry in summary.get("partitions", []):
            pct = entry.get("percent", 0)
            used = entry.get("used", 0)
            total = entry.get("total", 0)
            mp = entry.get("mountpoint", "?")
            print(f"  {mp:<12}: {_bar(pct, 15)}  "
                  f"{_fmt_bytes(used)} / {_fmt_bytes(total)}")

    def _disk_summary(self) -> dict:
        try:
            import psutil
            partitions = []
            for part in psutil.disk_partitions(all=False):
                try:
                    usage = psutil.disk_usage(part.mountpoint)
                    partitions.append({
                        "mountpoint": part.mountpoint,
                        "fstype": part.fstype,
                        "total": usage.total,
                        "used": usage.used,
                        "free": usage.free,
                        "percent": usage.percent,
                    })
                except (PermissionError, OSError):
                    continue
            return {"partitions": partitions}
        except ImportError:
            return {"error": "Disk info unavailable (install psutil for full data)"}
        except Exception as exc:
            return {"error": str(exc)}

    # ------------------------------------------------------------------
    # Processes
    # ------------------------------------------------------------------

    def _section_processes(self) -> None:
        print("\n  ── Processes ──")
        count = self._process_count()
        print(f"  System   : {count.get('system', '?')} processes running")
        print(f"  AURA     : {count.get('aura', 0)} tracked processes")

    def _process_count(self) -> dict:
        result: dict = {}
        try:
            import psutil
            result["system"] = len(psutil.pids())
        except ImportError:
            pass
        except Exception:
            pass
        try:
            from aura_os.kernel.process import ProcessManager
            pm = ProcessManager()
            result["aura"] = len(pm.list_processes())
        except Exception:
            result["aura"] = 0
        return result

    # ------------------------------------------------------------------
    # Services
    # ------------------------------------------------------------------

    def _section_services(self) -> None:
        print("\n  ── Services ──")
        summary = self._service_summary()
        if not summary:
            print("  No services registered.")
            return
        for svc in summary[:8]:
            status = svc.get("status", "unknown")
            sym = "✓" if status == "running" else "✗"
            print(f"  {sym} {svc.get('name', '?'):<20} {status}")
        if len(summary) > 8:
            print(f"  … {len(summary) - 8} more")

    def _service_summary(self) -> List[dict]:
        try:
            from aura_os.kernel.service import ServiceManager
            sm = ServiceManager()
            return sm.list_services()
        except Exception:
            return []

    # ------------------------------------------------------------------
    # Network
    # ------------------------------------------------------------------

    def _section_network(self) -> None:
        print("\n  ── Network ──")
        status = self._network_status()
        online = status.get("online", False)
        print(f"  Status   : {'Online ✓' if online else 'Offline ✗'}")
        for iface in status.get("interfaces", [])[:4]:
            print(f"  {iface.get('name', '?'):<10}: {iface.get('addr', '?')}")

    def _network_status(self) -> dict:
        result: dict = {"online": False, "interfaces": []}
        try:
            import psutil
            stats = psutil.net_if_addrs()
            ifaces = []
            for name, addrs in stats.items():
                for a in addrs:
                    if a.family.name == "AF_INET":
                        ifaces.append({"name": name, "addr": a.address})
                        break
            result["interfaces"] = ifaces
            result["online"] = any(
                i["addr"] not in ("127.0.0.1", "0.0.0.0") for i in ifaces
            )
        except ImportError:
            pass
        except Exception:
            pass
        if not result["online"]:
            try:
                import socket
                socket.setdefaulttimeout(2)
                socket.getaddrinfo("8.8.8.8", 53)
                result["online"] = True
            except Exception:
                pass
        return result

    # ------------------------------------------------------------------
    # Logs
    # ------------------------------------------------------------------

    def _section_logs(self) -> None:
        print("\n  ── Recent Log Entries ──")
        try:
            from aura_os.kernel.syslog import Syslog
            entries = Syslog().tail(5)
            if not entries:
                print("  (no log entries yet)")
                return
            for entry in entries:
                facility = entry.get("facility", "?")
                msg = entry.get("message", "")
                ts = entry.get("timestamp", "")
                print(f"  {ts}  [{facility}]  {msg}")
        except Exception:
            print("  Log unavailable.")

    # ------------------------------------------------------------------
    # Health score
    # ------------------------------------------------------------------

    def _health_score(self) -> str:
        """Return a simple health rating: healthy / warning / critical."""
        cpu = self._cpu_summary()
        mem = self._memory_summary()
        issues = []
        if cpu.get("percent", 0) > 90:
            issues.append("high CPU")
        if mem.get("percent", 0) > 90:
            issues.append("high memory")
        if not issues:
            return "healthy"
        if len(issues) >= 2:
            return "critical"
        return "warning"


# ---------------------------------------------------------------------------
# CLI command wrapper
# ---------------------------------------------------------------------------

class CenterCommand:
    """``aura center`` — launch the Command Center dashboard."""

    def execute(self, args, eal) -> int:
        watch = getattr(args, "watch", False)
        interval = getattr(args, "interval", 3.0)
        cc = CommandCenter(eal)
        if watch:
            cc.run_tui(interval=interval)
        else:
            cc.show()
        return 0
