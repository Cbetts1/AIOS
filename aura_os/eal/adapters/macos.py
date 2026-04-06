"""macOS environment adapter for AURA OS."""

import os
import platform
import shutil
import subprocess
from typing import Dict, Optional, Tuple


class MacOSAdapter:
    """Adapter for macOS environments.

    Uses ``sysctl`` for hardware/memory info, ``sw_vers`` for OS version,
    and Homebrew (``brew``) as the primary package manager.  Detects Apple
    Silicon by checking for ``/opt/homebrew``.
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
        """Return the Homebrew prefix (differs on Apple Silicon vs Intel)."""
        if os.path.isdir("/opt/homebrew"):
            return "/opt/homebrew"
        return "/usr/local"

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
        """Return the first available macOS package manager, or None."""
        for mgr in ("brew", "port"):
            if shutil.which(mgr):
                return mgr
        return None

    # ------------------------------------------------------------------
    # System information
    # ------------------------------------------------------------------

    def get_system_info(self) -> Dict:
        """Return macOS system information using sysctl and sw_vers."""
        uname = platform.uname()
        arch = self._detect_arch()
        return {
            "platform": "macos",
            "arch": arch,
            "kernel": uname.release,
            "hostname": uname.node,
            "cpu_count": os.cpu_count() or 1,
            "cpu_model": self._cpu_model(),
            "memory": self._read_memory(),
            "os_version": self._os_version(),
            "apple_silicon": arch == "arm64" or os.path.isdir("/opt/homebrew"),
        }

    @staticmethod
    def _detect_arch() -> str:
        """Return the machine architecture string."""
        try:
            rc, out, _ = 0, "", ""
            result = subprocess.run(
                ["uname", "-m"], capture_output=True, text=True
            )
            return result.stdout.strip() or platform.machine()
        except Exception:
            return platform.machine() or "unknown"

    @staticmethod
    def _cpu_model() -> str:
        """Return the CPU model string via sysctl."""
        try:
            result = subprocess.run(
                ["sysctl", "-n", "machdep.cpu.brand_string"],
                capture_output=True, text=True, timeout=5,
            )
            model = result.stdout.strip()
            if model:
                return model
        except Exception:
            pass
        return platform.processor() or "unknown"

    @staticmethod
    def _read_memory() -> Dict:
        """Return physical memory stats via sysctl."""
        total_bytes = 0
        try:
            result = subprocess.run(
                ["sysctl", "-n", "hw.memsize"],
                capture_output=True, text=True, timeout=5,
            )
            total_bytes = int(result.stdout.strip())
        except Exception:
            pass

        # vm_stat for free/available pages
        page_size = 4096
        free_pages = 0
        try:
            result = subprocess.run(
                ["vm_stat"], capture_output=True, text=True, timeout=5,
            )
            for line in result.stdout.splitlines():
                if line.startswith("Pages free"):
                    free_pages = int(line.split(":")[1].strip().rstrip("."))
                    break
                if "page size" in line.lower():
                    # "Mach Virtual Memory Statistics: (page size of 4096 bytes)"
                    import re
                    m = re.search(r"page size of (\d+)", line)
                    if m:
                        page_size = int(m.group(1))
        except Exception:
            pass

        available_bytes = free_pages * page_size
        used_bytes = max(0, total_bytes - available_bytes)
        total_kb = total_bytes // 1024
        available_kb = available_bytes // 1024
        used_kb = used_bytes // 1024
        percent = (used_kb / total_kb * 100) if total_kb else 0.0

        return {
            "total_kb": total_kb,
            "available_kb": available_kb,
            "used_kb": used_kb,
            "percent": round(percent, 1),
        }

    @staticmethod
    def _os_version() -> str:
        """Return the macOS version string via sw_vers."""
        try:
            result = subprocess.run(
                ["sw_vers", "-productVersion"],
                capture_output=True, text=True, timeout=5,
            )
            return result.stdout.strip()
        except Exception:
            return platform.mac_ver()[0] or "unknown"
