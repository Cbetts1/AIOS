"""Windows environment adapter for AURA OS."""

import os
import platform
import shutil
import subprocess
from typing import Dict, Optional, Tuple


class WindowsAdapter:
    """Adapter for Windows environments.

    Uses ``wmic`` / ``psutil`` for system info and supports ``winget``,
    ``choco``, and ``scoop`` as package managers.
    """

    def __init__(self):
        self._home = os.path.expanduser("~")
        self._tmp = os.environ.get("TEMP", os.environ.get("TMP", "C:\\Temp"))

    # ------------------------------------------------------------------
    # Path helpers
    # ------------------------------------------------------------------

    def get_home(self) -> str:
        """Return the user home directory."""
        return self._home

    def get_prefix(self) -> str:
        """Return a safe prefix path."""
        return os.environ.get("ProgramFiles", "C:\\Program Files")

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
        """Return the first available Windows package manager, or None."""
        for mgr in ("winget", "choco", "scoop"):
            if shutil.which(mgr):
                return mgr
        return None

    # ------------------------------------------------------------------
    # System information
    # ------------------------------------------------------------------

    def get_system_info(self) -> Dict:
        """Return Windows system information."""
        uname = platform.uname()
        return {
            "platform": "windows",
            "arch": uname.machine,
            "kernel": uname.release,
            "hostname": uname.node,
            "cpu_count": os.cpu_count() or 1,
            "cpu_model": self._cpu_model(),
            "memory": self._read_memory(),
            "os_version": platform.version(),
        }

    @staticmethod
    def _cpu_model() -> str:
        """Return the CPU model string."""
        try:
            import winreg  # type: ignore
            key = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"HARDWARE\DESCRIPTION\System\CentralProcessor\0",
            )
            model, _ = winreg.QueryValueEx(key, "ProcessorNameString")
            winreg.CloseKey(key)
            return model.strip()
        except Exception:
            pass
        return platform.processor() or "unknown"

    @staticmethod
    def _read_memory() -> Dict:
        """Return physical memory stats via psutil or wmic."""
        try:
            import psutil  # type: ignore
            vm = psutil.virtual_memory()
            total_kb = vm.total // 1024
            available_kb = vm.available // 1024
            used_kb = (vm.total - vm.available) // 1024
            return {
                "total_kb": total_kb,
                "available_kb": available_kb,
                "used_kb": used_kb,
                "percent": round(vm.percent, 1),
            }
        except Exception:
            pass

        # Fallback: wmic
        try:
            result = subprocess.run(
                ["wmic", "OS", "get", "TotalVisibleMemorySize,FreePhysicalMemory",
                 "/Value"],
                capture_output=True, text=True, timeout=10,
            )
            total_kb = 0
            free_kb = 0
            for line in result.stdout.splitlines():
                if "TotalVisibleMemorySize=" in line:
                    total_kb = int(line.split("=")[1].strip())
                elif "FreePhysicalMemory=" in line:
                    free_kb = int(line.split("=")[1].strip())
            used_kb = total_kb - free_kb
            percent = (used_kb / total_kb * 100) if total_kb else 0.0
            return {
                "total_kb": total_kb,
                "available_kb": free_kb,
                "used_kb": used_kb,
                "percent": round(percent, 1),
            }
        except Exception:
            return {}
