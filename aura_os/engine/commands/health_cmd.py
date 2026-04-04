"""System health dashboard command for AURA OS.

``aura health`` prints a concise, human-readable dashboard showing:
  - CPU load averages and per-core usage (requires psutil)
  - Memory usage (RAM + swap)
  - Disk usage summary for the root filesystem
  - Network connectivity (online/offline)
  - AURA services status
  - Top-5 processes by CPU and memory
"""

from __future__ import annotations

import os
import time


def _bar(pct: float, width: int = 20) -> str:
    """Return a simple ASCII progress bar for *pct* (0–100)."""
    filled = int(pct / 100 * width)
    bar = "█" * filled + "░" * (width - filled)
    return f"[{bar}] {pct:.1f}%"


def _fmt_bytes(n: float) -> str:
    for unit, thr in (("GiB", 1 << 30), ("MiB", 1 << 20), ("KiB", 1 << 10)):
        if n >= thr:
            return f"{n / thr:.1f} {unit}"
    return f"{n:.0f} B"


class HealthCommand:
    """System health dashboard."""

    def execute(self, args, eal) -> int:
        verbose = getattr(args, "verbose", False)
        self._print_health(verbose)
        return 0

    def _print_health(self, verbose: bool = False):
        print("=" * 60)
        print("  AURA OS — System Health Dashboard")
        print(f"  {time.strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 60)

        self._section_cpu(verbose)
        self._section_memory()
        self._section_disk()
        self._section_network()
        self._section_services()
        if verbose:
            self._section_top_processes()

        print("=" * 60)

    # ------------------------------------------------------------------

    def _section_cpu(self, verbose: bool):
        print("\n── CPU ──────────────────────────────────────────────────")
        try:
            import psutil
            load = os.getloadavg() if hasattr(os, "getloadavg") else (0, 0, 0)
            print(f"  Load avg (1m/5m/15m): {load[0]:.2f}  {load[1]:.2f}  {load[2]:.2f}")
            cpu_total = psutil.cpu_percent(interval=0.5)
            print(f"  Overall CPU:          {_bar(cpu_total)}")
            if verbose:
                per_cpu = psutil.cpu_percent(percpu=True)
                for i, pct in enumerate(per_cpu):
                    print(f"    Core {i:2d}:           {_bar(pct, 15)}")
            cpu_freq = psutil.cpu_freq()
            if cpu_freq:
                print(f"  Frequency:            {cpu_freq.current:.0f} MHz  "
                      f"(max {cpu_freq.max:.0f} MHz)")
            print(f"  Logical CPUs:         {psutil.cpu_count(logical=True)}")
        except ImportError:
            _cpu_fallback()

    def _section_memory(self):
        print("\n── Memory ───────────────────────────────────────────────")
        try:
            import psutil
            mem = psutil.virtual_memory()
            swap = psutil.swap_memory()
            print(f"  RAM  Total: {_fmt_bytes(mem.total):<10}  Used: {_fmt_bytes(mem.used):<10}  "
                  f"{_bar(mem.percent)}")
            print(f"  Swap Total: {_fmt_bytes(swap.total):<10}  Used: {_fmt_bytes(swap.used):<10}  "
                  f"{_bar(swap.percent)}")
        except ImportError:
            _mem_fallback()

    def _section_disk(self):
        print("\n── Disk ─────────────────────────────────────────────────")
        try:
            import psutil
            for part in psutil.disk_partitions(all=False):
                try:
                    usage = psutil.disk_usage(part.mountpoint)
                    print(
                        f"  {part.mountpoint:<18} {_fmt_bytes(usage.total):>8} total  "
                        f"{_bar(usage.percent)}"
                    )
                except PermissionError:
                    pass
        except ImportError:
            import shutil
            total, used, free = shutil.disk_usage("/")
            pct = used / total * 100 if total else 0
            print(f"  /  {_fmt_bytes(total)} total  {_bar(pct)}")

    def _section_network(self):
        print("\n── Network ──────────────────────────────────────────────")
        from aura_os.net.manager import NetworkManager
        nm = NetworkManager()
        online = nm.check_connectivity()
        status = "\033[32m● online\033[0m" if online else "\033[31m✕ offline\033[0m"
        print(f"  Connectivity:  {status}")
        gw = nm.get_default_gateway()
        print(f"  Gateway:       {gw or 'unknown'}")
        ifaces = nm.list_interfaces()
        up = [i["name"] for i in ifaces if i.get("is_up") and not i.get("is_loopback")]
        print(f"  Active ifaces: {', '.join(up) if up else 'none'}")

    def _section_services(self):
        print("\n── AURA Services ────────────────────────────────────────")
        try:
            from aura_os.kernel.service import ServiceManager
            sm = ServiceManager()
            services = sm.list_services()
            if not services:
                print("  (no registered services)")
            else:
                for s in services[:10]:
                    st = s.get("status", "?")
                    icon = "●" if st == "running" else "○"
                    print(f"  {icon} {s.get('name', '?'):<20} {st}")
        except Exception as exc:
            print(f"  (unavailable: {exc})")

    def _section_top_processes(self):
        print("\n── Top Processes (CPU) ──────────────────────────────────")
        try:
            import psutil
            procs = sorted(
                psutil.process_iter(["pid", "name", "cpu_percent", "memory_info"]),
                key=lambda p: p.info.get("cpu_percent") or 0,
                reverse=True,
            )[:5]
            print(f"  {'PID':>7}  {'NAME':<25}  {'CPU%':>6}  {'RSS':>8}")
            for p in procs:
                info = p.info
                mem = info.get("memory_info")
                rss = _fmt_bytes(mem.rss) if mem else "?"
                print(
                    f"  {info['pid']:>7}  {(info.get('name') or '?')[:24]:<25}  "
                    f"{info.get('cpu_percent', 0):>6.1f}  {rss:>8}"
                )
        except Exception:
            pass


def _cpu_fallback():
    """Print CPU info without psutil."""
    import subprocess
    try:
        r = subprocess.run(["cat", "/proc/loadavg"], capture_output=True, text=True)
        parts = r.stdout.split()
        if parts:
            print(f"  Load avg: {parts[0]} / {parts[1]} / {parts[2]}")
    except Exception:
        print("  (psutil not installed — limited CPU info)")


def _mem_fallback():
    """Print memory info without psutil."""
    try:
        with open("/proc/meminfo") as fh:
            lines = {k.strip(): v.strip() for k, v in
                     (l.split(":", 1) for l in fh if ":" in l)}
        total = int(lines.get("MemTotal", "0").split()[0]) * 1024
        avail = int(lines.get("MemAvailable", "0").split()[0]) * 1024
        used = total - avail
        pct = used / total * 100 if total else 0
        print(f"  RAM  Total: {_fmt_bytes(total):<10}  Used: {_fmt_bytes(used):<10}  {_bar(pct)}")
    except Exception:
        print("  (psutil not installed — limited memory info)")
