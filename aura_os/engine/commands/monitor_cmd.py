"""Real-time resource monitor command for AURA OS.

``aura monitor`` displays a continuously-refreshing live view of:
  - CPU usage (overall + per-core)
  - Memory / swap usage
  - Disk I/O rates
  - Network I/O rates
  - Top-N processes

Refresh interval defaults to 2 s.  Press Ctrl-C to exit.
"""

from __future__ import annotations

import sys
import time


def _fmt_bytes(n: float) -> str:
    for unit, thr in (("GB", 1e9), ("MB", 1e6), ("KB", 1e3)):
        if n >= thr:
            return f"{n / thr:.1f}{unit}"
    return f"{n:.0f}B"


def _bar(pct: float, width: int = 18) -> str:
    filled = int(min(pct, 100) / 100 * width)
    return "[" + "█" * filled + "░" * (width - filled) + f"] {pct:5.1f}%"


class MonitorCommand:
    """Real-time system resource monitor."""

    def execute(self, args, eal) -> int:
        interval = getattr(args, "interval", 2)
        top_n = getattr(args, "top", 10)
        try:
            import psutil  # noqa: F401
        except ImportError:
            print(
                "[monitor] psutil is required for real-time monitoring.\n"
                "Install it with: pip install psutil"
            )
            return 1

        print("[monitor] Press Ctrl-C to exit.\n")
        try:
            self._run(interval, top_n)
        except KeyboardInterrupt:
            print("\n[monitor] Stopped.")
        return 0

    def _run(self, interval: float, top_n: int):
        import psutil

        # Prime per-second counters
        net_before = psutil.net_io_counters()
        disk_before = psutil.disk_io_counters()
        prev_time = time.monotonic()

        while True:
            time.sleep(interval)
            now = time.monotonic()
            elapsed = now - prev_time or interval

            # Gather stats
            cpu_pct = psutil.cpu_percent(percpu=True)
            mem = psutil.virtual_memory()
            swap = psutil.swap_memory()
            net_after = psutil.net_io_counters()
            disk_after = psutil.disk_io_counters() if psutil.disk_io_counters() else None

            net_rx = (net_after.bytes_recv - net_before.bytes_recv) / elapsed
            net_tx = (net_after.bytes_sent - net_before.bytes_sent) / elapsed
            disk_r = (
                (disk_after.read_bytes - disk_before.read_bytes) / elapsed
                if disk_before and disk_after else 0
            )
            disk_w = (
                (disk_after.write_bytes - disk_before.write_bytes) / elapsed
                if disk_before and disk_after else 0
            )

            net_before = net_after
            disk_before = disk_after
            prev_time = now

            procs = []
            for p in psutil.process_iter(
                ["pid", "name", "cpu_percent", "memory_info", "status"]
            ):
                try:
                    procs.append(p.info)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass

            procs.sort(key=lambda x: x.get("cpu_percent") or 0, reverse=True)

            # Clear screen
            sys.stdout.write("\033[2J\033[H")  # ANSI: clear + move to top
            sys.stdout.flush()

            ts = time.strftime("%H:%M:%S")
            print(f"AURA Monitor  [{ts}]  interval={interval}s  Ctrl-C to stop")
            print("─" * 60)

            # CPU
            avg = sum(cpu_pct) / len(cpu_pct) if cpu_pct else 0
            print(f"CPU (avg)  {_bar(avg)}")
            for i, pct in enumerate(cpu_pct[:8]):
                print(f"  Core{i:<2}   {_bar(pct, 12)}")
            if len(cpu_pct) > 8:
                print(f"  … (+{len(cpu_pct) - 8} more cores)")

            # Memory
            print()
            print(
                f"RAM   {_bar(mem.percent)}  "
                f"{_fmt_bytes(mem.used)}/{_fmt_bytes(mem.total)}"
            )
            print(
                f"Swap  {_bar(swap.percent)}  "
                f"{_fmt_bytes(swap.used)}/{_fmt_bytes(swap.total)}"
            )

            # Disk / Net I/O
            print()
            print(f"Disk  Read: {_fmt_bytes(disk_r)}/s   Write: {_fmt_bytes(disk_w)}/s")
            print(f"Net   RX:   {_fmt_bytes(net_rx)}/s   TX:    {_fmt_bytes(net_tx)}/s")

            # Top processes
            print()
            print(f"{'PID':>7}  {'NAME':<22}  {'CPU%':>6}  {'RSS':>8}  STATUS")
            print("─" * 60)
            for info in procs[:top_n]:
                mem_info = info.get("memory_info")
                rss = _fmt_bytes(mem_info.rss) if mem_info else "?"
                name = (info.get("name") or "?")[:21]
                print(
                    f"{info['pid']:>7}  {name:<22}  "
                    f"{info.get('cpu_percent', 0):>6.1f}  "
                    f"{rss:>8}  {info.get('status', '?')}"
                )
