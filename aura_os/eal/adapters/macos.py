"""macOS environment adapter."""

import os
import platform
import shutil
import subprocess
from typing import Dict, Optional, Tuple


class MacOSAdapter:
    """Adapter for macOS environments.

    Uses ``sysctl`` for memory information, ``sw_vers`` for OS version, and
    detects Homebrew or MacPorts for package management.
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
        # Apple Silicon uses /opt/homebrew; Intel uses /usr/local
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
        """Return macOS-specific system information."""
        uname = platform.uname()
        return {
            "platform": "macos",
            "arch": uname.machine,
            "kernel": uname.release,
            "hostname": uname.node,
            "cpu_count": os.cpu_count() or 1,
            "cpu_model": self._cpu_model(),
            "memory": self._read_memory(),
            "macos_version": self._macos_version(),
        }

    @staticmethod
    def _cpu_model() -> str:
        """Read CPU brand string via sysctl."""
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
        """Read memory information via sysctl."""
        mem: Dict = {}
        try:
            result = subprocess.run(
                ["sysctl", "-n", "hw.memsize"],
                capture_output=True, text=True,
            )
            if result.returncode == 0:
                total_bytes = int(result.stdout.strip())
                total_kb = total_bytes // 1024
                mem["total_kb"] = total_kb
        except (OSError, ValueError):
            pass
        return mem

    @staticmethod
    def _macos_version() -> str:
        """Return the macOS marketing version string (e.g. '14.3.1')."""
        try:
            result = subprocess.run(
                ["sw_vers", "-productVersion"],
                capture_output=True, text=True,
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except OSError:
            pass
        return platform.mac_ver()[0] or "unknown"
