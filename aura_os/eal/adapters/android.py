"""Android / Termux environment adapter."""

import os
import platform
import subprocess
from typing import Dict, Tuple


class AndroidAdapter:
    """Adapter for Android environments, primarily Termux.

    Provides access to Termux-specific paths and the ``pkg`` package manager.
    """

    def __init__(self):
        self._home = "/data/data/com.termux/files/home"
        self._prefix = "/data/data/com.termux/files/usr"
        self._tmp = "/data/data/com.termux/files/usr/tmp"
        # Fall back to real $HOME if the Termux path doesn't exist
        if not os.path.isdir(self._home):
            self._home = os.path.expanduser("~")

    # ------------------------------------------------------------------
    # Path helpers
    # ------------------------------------------------------------------

    def get_home(self) -> str:
        """Return the Termux home directory."""
        return self._home

    def get_prefix(self) -> str:
        """Return the Termux installation prefix."""
        return self._prefix

    def get_tmp(self) -> str:
        """Return a suitable temporary directory."""
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

    def available_pkg_manager(self) -> str:
        """Return the Termux package manager name."""
        return "pkg"

    # ------------------------------------------------------------------
    # System information
    # ------------------------------------------------------------------

    def get_system_info(self) -> Dict:
        """Return basic system information as a dict."""
        info: Dict = {
            "platform": "android/termux",
            "arch": platform.machine(),
            "cpu_count": os.cpu_count() or 1,
            "memory": self._read_meminfo(),
        }
        return info

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
