"""``aura sys`` command handler."""

import os
import time

from aura_os import __version__
from aura_os.kernel.memory import MemoryTracker


def _uptime() -> str:
    """Return a human-readable uptime string by reading /proc/uptime."""
    try:
        with open("/proc/uptime", "r", encoding="utf-8") as fh:
            seconds = float(fh.read().split()[0])
        days = int(seconds // 86400)
        hours = int((seconds % 86400) // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        parts = []
        if days:
            parts.append(f"{days}d")
        if hours:
            parts.append(f"{hours}h")
        if minutes:
            parts.append(f"{minutes}m")
        parts.append(f"{secs}s")
        return " ".join(parts)
    except OSError:
        return "unknown"


def _disk_usage(path: str = "/") -> dict:
    """Return disk usage stats for *path* using os.statvfs."""
    try:
        st = os.statvfs(path)
        total = st.f_blocks * st.f_frsize
        free = st.f_bfree * st.f_frsize
        used = total - free
        percent = (used / total * 100) if total else 0.0
        return {
            "total_gb": round(total / 1024 ** 3, 1),
            "used_gb": round(used / 1024 ** 3, 1),
            "free_gb": round(free / 1024 ** 3, 1),
            "percent": round(percent, 1),
        }
    except OSError:
        return {}


def _process_count() -> int:
    """Count entries in /proc that look like PIDs."""
    try:
        return sum(1 for e in os.listdir("/proc") if e.isdigit())
    except OSError:
        return 0


def _render(eal) -> str:
    """Build the sys-status string."""
    tracker = MemoryTracker()
    mem = tracker.get_system_memory()
    disk = _disk_usage()
    proc_count = _process_count()
    uptime_str = _uptime()

    total_mb = mem.get("total", 0) // 1024 // 1024
    used_mb = mem.get("used", 0) // 1024 // 1024
    avail_mb = mem.get("available", 0) // 1024 // 1024
    mem_pct = mem.get("percent", 0)

    lines = [
        "─" * 50,
        f"  AURA OS {__version__}  —  System Status",
        "─" * 50,
        f"  Platform   : {eal.platform}",
        f"  Uptime     : {uptime_str}",
        f"  Processes  : {proc_count}",
        "",
        f"  Memory     : {used_mb} MB used / {total_mb} MB total  ({mem_pct}%)",
        f"               {avail_mb} MB available",
    ]

    if disk:
        lines += [
            "",
            f"  Disk (/)   : {disk['used_gb']} GB used / {disk['total_gb']} GB total  ({disk['percent']}%)",
            f"               {disk['free_gb']} GB free",
        ]

    lines.append("")
    return "\n".join(lines)


class SysCommand:
    """Display system status information.

    With ``--watch``, refreshes every 2 seconds until interrupted.
    """

    def execute(self, args, eal) -> int:
        """Print system status.

        Returns 0.
        """
        watch = getattr(args, "watch", False)

        if watch:
            try:
                while True:
                    # Clear screen portably
                    print("\033[2J\033[H", end="")
                    print(_render(eal))
                    print("  (Press Ctrl-C to exit)")
                    time.sleep(2)
            except KeyboardInterrupt:
                print()
            return 0

        print(_render(eal))
        return 0
