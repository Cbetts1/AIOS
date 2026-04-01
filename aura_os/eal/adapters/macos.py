"""macOS environment adapter."""

import os
import platform
import shutil
import subprocess
from typing import Dict, Optional, Tuple


class MacOSAdapter:
    """Adapter for macOS systems.

    Uses Homebrew / MacPorts for package management and exposes standard
    macOS paths.
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
        """Return the system prefix (Homebrew default)."""
        # Apple Silicon uses /opt/homebrew, Intel uses /usr/local
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
        if shutil.which("brew"):
            return "brew"
        if shutil.which("port"):
            return "port"
        return None

    # ------------------------------------------------------------------
    # System information
    # ------------------------------------------------------------------

    def get_system_info(self) -> Dict:
        """Return basic system information for macOS."""
        uname = platform.uname()
        return {
            "platform": "macos",
            "arch": uname.machine,
            "kernel": uname.release,
            "hostname": uname.node,
            "cpu_count": os.cpu_count() or 1,
            "cpu_model": self._cpu_model(),
            "memory": self._read_memory(),
            "macos_version": platform.mac_ver()[0] or "unknown",
        }

    @staticmethod
    def _cpu_model() -> str:
        """Get the CPU brand string via sysctl."""
        try:
            result = subprocess.run(
                ["sysctl", "-n", "machdep.cpu.brand_string"],
                capture_output=True, text=True,
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
        except OSError:
            pass
        return platform.processor() or "unknown"

    @staticmethod
    def _read_memory() -> Dict:
        """Read memory information using sysctl."""
        try:
            result = subprocess.run(
                ["sysctl", "-n", "hw.memsize"],
                capture_output=True, text=True,
            )
            if result.returncode == 0:
                total_bytes = int(result.stdout.strip())
                total_kb = total_bytes // 1024
                return {
                    "total_kb": total_kb,
                    "available_kb": 0,  # not available via sysctl
                    "used_kb": 0,       # not available via sysctl
                    "percent": 0.0,     # not available via sysctl
                }
        except (OSError, ValueError):
            pass
        return {}
