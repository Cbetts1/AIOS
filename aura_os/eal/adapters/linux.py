"""Standard Linux environment adapter."""

import os
import platform
import shutil
import subprocess
from typing import Dict, Optional, Tuple


class LinuxAdapter:
    """Adapter for standard Linux environments.

    Detects available package managers and exposes standard Linux paths.
    """

    def __init__(self):
        self._home = os.path.expanduser("~")
        self._tmp = os.environ.get("TMPDIR", "/tmp")

    # ------------------------------------------------------------------
    # Path helpers
    # ------------------------------------------------------------------

    def get_home(self) -> str:
        """Return the user home directory."""
        return self._home

    def get_prefix(self) -> str:
        """Return the system prefix."""
        return "/usr"

    def get_tmp(self) -> str:
        """Return the temporary directory."""
        return self._tmp

    # ------------------------------------------------------------------
    # Command execution
    # ------------------------------------------------------------------

    def run_command(self, cmd: list, capture: bool = True) -> Tuple[int, str, str]:
        """Run *cmd* as a subprocess.

        Returns ``(returncode, stdout, stderr)``.
        """
        try:
            result = subprocess.run(
                cmd,
                capture_output=capture,
                text=True,
            )
            return result.returncode, result.stdout or "", result.stderr or ""
        except FileNotFoundError as exc:
            return 127, "", str(exc)
        except OSError as exc:
            return 1, "", str(exc)

    # ------------------------------------------------------------------
    # Package manager
    # ------------------------------------------------------------------

    def available_pkg_manager(self) -> Optional[str]:
        """Return the first available system package manager, or None."""
        for mgr in ("apt", "dnf", "pacman", "zypper", "apk"):
            if shutil.which(mgr):
                return mgr
        return None

    # ------------------------------------------------------------------
    # System information
    # ------------------------------------------------------------------

    def get_system_info(self) -> Dict:
        """Return basic system information gathered from /proc and platform."""
        uname = platform.uname()
        return {
            "platform": "linux",
            "arch": uname.machine,
            "kernel": uname.release,
            "hostname": uname.node,
            "cpu_count": os.cpu_count() or 1,
            "cpu_model": self._cpu_model(),
            "memory": self._read_meminfo(),
        }

    @staticmethod
    def _cpu_model() -> str:
        try:
            with open("/proc/cpuinfo", "r", encoding="utf-8") as fh:
                for line in fh:
                    if line.startswith("model name"):
                        return line.split(":", 1)[1].strip()
        except OSError:
            pass
        return platform.processor() or "unknown"

    @staticmethod
    def _read_meminfo() -> Dict:
        """Parse /proc/meminfo and return a small summary dict."""
        meminfo: Dict = {}
        try:
            with open("/proc/meminfo", "r", encoding="utf-8") as fh:
                for line in fh:
                    parts = line.split()
                    if len(parts) >= 2:
                        key = parts[0].rstrip(":")
                        try:
                            meminfo[key] = int(parts[1])
                        except ValueError:
                            pass
        except OSError:
            return {}

        total_kb = meminfo.get("MemTotal", 0)
        available_kb = meminfo.get("MemAvailable", meminfo.get("MemFree", 0))
        used_kb = total_kb - available_kb
        percent = (used_kb / total_kb * 100) if total_kb else 0.0

        return {
            "total_kb": total_kb,
            "available_kb": available_kb,
            "used_kb": used_kb,
            "percent": round(percent, 1),
        }
