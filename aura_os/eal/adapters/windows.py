"""Windows environment adapter."""

import os
import platform
import shutil
import subprocess
import sys
from typing import Dict, Optional, Tuple


class WindowsAdapter:
    """Adapter for Windows systems.

    Detects available package managers (winget, choco, scoop) and exposes
    standard Windows paths.
    """

    def __init__(self):
        self._home = os.path.expanduser("~")
        self._tmp = os.environ.get("TEMP", os.environ.get(
            "TMP", os.path.join(self._home, "AppData", "Local", "Temp")
        ))

    # ------------------------------------------------------------------
    # Path helpers
    # ------------------------------------------------------------------

    def get_home(self) -> str:
        """Return the user home directory."""
        return self._home

    def get_prefix(self) -> str:
        """Return the Python installation prefix."""
        return sys.prefix

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
                # CREATE_NO_WINDOW prevents console popups on Windows
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
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
        """Return the first available Windows package manager, or None."""
        for mgr in ("winget", "choco", "scoop"):
            if shutil.which(mgr):
                return mgr
        return None

    # ------------------------------------------------------------------
    # System information
    # ------------------------------------------------------------------

    def get_system_info(self) -> Dict:
        """Return basic system information for Windows."""
        uname = platform.uname()
        return {
            "platform": "windows",
            "arch": uname.machine or platform.machine(),
            "version": uname.version,
            "hostname": uname.node,
            "cpu_count": os.cpu_count() or 1,
            "cpu_model": platform.processor() or "unknown",
            "memory": self._read_memory(),
        }

    @staticmethod
    def _read_memory() -> Dict:
        """Read memory information using wmic or ctypes."""
        # Try ctypes first (no subprocess needed)
        try:
            import ctypes

            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            mem = MEMORYSTATUSEX()
            mem.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(mem))
            total_kb = mem.ullTotalPhys // 1024
            avail_kb = mem.ullAvailPhys // 1024
            used_kb = total_kb - avail_kb
            percent = (used_kb / total_kb * 100) if total_kb else 0.0
            return {
                "total_kb": total_kb,
                "available_kb": avail_kb,
                "used_kb": used_kb,
                "percent": round(percent, 1),
            }
        except Exception:
            pass
        return {}
