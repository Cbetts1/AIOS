"""Virtual /proc filesystem for AURA OS.

Exposes system information through a virtual file hierarchy modelled
after Linux's ``/proc`` filesystem.  Each "file" is generated on the
fly from real host data.
"""

import os
import platform
import time
from typing import Dict, Optional

from aura_os import __version__
from aura_os.kernel.memory import MemoryTracker


# Boot timestamp — set once when module loads
_BOOT_TIME = time.time()


class ProcFS:
    """Virtual /proc filesystem.

    Usage::

        pfs = ProcFS()
        print(pfs.read("uptime"))
        print(pfs.read("meminfo"))
        entries = pfs.ls()

    Supported virtual files:
    - ``uptime``   — seconds since AURA OS was loaded
    - ``version``  — AURA OS version string
    - ``meminfo``  — system memory statistics
    - ``cpuinfo``  — CPU model and count
    - ``loadavg``  — load averages (Linux only, fallback to 0)
    - ``self/status`` — current process memory usage
    - ``hostname`` — machine hostname
    - ``cmdline``  — command line that started AURA OS
    """

    _FILES = (
        "uptime",
        "version",
        "meminfo",
        "cpuinfo",
        "loadavg",
        "hostname",
        "cmdline",
        "self/status",
    )

    def ls(self, path: str = "") -> list:
        """List entries in the virtual /proc directory.

        Supports ``""`` (root) and ``"self"`` subdirectory.
        """
        if path in ("", "/"):
            # Top-level: unique first path components
            seen = set()
            entries = []
            for f in self._FILES:
                first = f.split("/")[0]
                if first not in seen:
                    entries.append(first)
                    seen.add(first)
            return entries
        if path in ("self", "self/"):
            return ["status"]
        return []

    def read(self, path: str) -> Optional[str]:
        """Read a virtual proc file.  Returns None if *path* is unknown."""
        path = path.strip("/")
        handler = {
            "uptime": self._uptime,
            "version": self._version,
            "meminfo": self._meminfo,
            "cpuinfo": self._cpuinfo,
            "loadavg": self._loadavg,
            "hostname": self._hostname,
            "cmdline": self._cmdline,
            "self/status": self._self_status,
        }.get(path)

        if handler is None:
            return None
        return handler()

    def exists(self, path: str) -> bool:
        """Check whether *path* exists in /proc."""
        path = path.strip("/")
        return path in self._FILES or path in ("", "self")

    # ------------------------------------------------------------------
    # Virtual file generators
    # ------------------------------------------------------------------

    @staticmethod
    def _uptime() -> str:
        elapsed = time.time() - _BOOT_TIME
        idle = 0.0  # we don't track idle time
        return f"{elapsed:.2f} {idle:.2f}\n"

    @staticmethod
    def _version() -> str:
        uname = platform.uname()
        return (
            f"AURA OS {__version__} "
            f"({uname.system} {uname.release} {uname.machine})\n"
        )

    @staticmethod
    def _meminfo() -> str:
        mem = MemoryTracker.get_system_memory()
        total_kb = mem.get("total", 0) // 1024
        avail_kb = mem.get("available", 0) // 1024
        used_kb = total_kb - avail_kb
        lines = [
            f"MemTotal:       {total_kb} kB",
            f"MemAvailable:   {avail_kb} kB",
            f"MemUsed:        {used_kb} kB",
        ]
        return "\n".join(lines) + "\n"

    @staticmethod
    def _cpuinfo() -> str:
        cpu_count = os.cpu_count() or 1
        model = platform.processor() or "unknown"
        lines = []
        for i in range(cpu_count):
            lines.append(f"processor\t: {i}")
            lines.append(f"model name\t: {model}")
            lines.append("")
        return "\n".join(lines) + "\n"

    @staticmethod
    def _loadavg() -> str:
        try:
            load1, load5, load15 = os.getloadavg()
            return f"{load1:.2f} {load5:.2f} {load15:.2f}\n"
        except (OSError, AttributeError):
            return "0.00 0.00 0.00\n"

    @staticmethod
    def _hostname() -> str:
        return platform.node() + "\n"

    @staticmethod
    def _cmdline() -> str:
        import sys
        return " ".join(sys.argv) + "\n"

    @staticmethod
    def _self_status() -> str:
        mem = MemoryTracker.get_process_memory()
        rss_kb = mem.get("rss", 0) // 1024
        pid = mem.get("pid", os.getpid())
        lines = [
            f"Name:\taura",
            f"Pid:\t{pid}",
            f"PPid:\t{os.getppid()}",
            f"VmRSS:\t{rss_kb} kB",
        ]
        return "\n".join(lines) + "\n"
