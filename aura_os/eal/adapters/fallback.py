"""Fallback adapter for unknown / minimal POSIX-like environments."""

import os
import subprocess
from typing import Dict, Optional, Tuple


class FallbackAdapter:
    """Minimal safe adapter that works on any POSIX-like system.

    Uses Python stdlib only; no assumptions about the host OS beyond POSIX.
    """

    def __init__(self):
        self._home = os.path.expanduser("~")
        self._tmp = os.environ.get("TMPDIR", os.path.join(self._home, ".cache", "aura", "tmp"))

    # ------------------------------------------------------------------
    # Path helpers
    # ------------------------------------------------------------------

    def get_home(self) -> str:
        """Return the user home directory."""
        return self._home

    def get_prefix(self) -> str:
        """Return a safe prefix path."""
        return "/usr/local"

    def get_tmp(self) -> str:
        """Return a temporary directory path."""
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
        """Return None — no known package manager in fallback mode."""
        return None

    # ------------------------------------------------------------------
    # System information
    # ------------------------------------------------------------------

    def get_system_info(self) -> Dict:
        """Return minimal system information using only stdlib."""
        import platform
        uname = platform.uname()
        return {
            "platform": uname.system or "unknown",
            "arch": uname.machine or "unknown",
            "cpu_count": os.cpu_count() or 1,
            "memory": {},
        }
