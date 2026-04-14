"""Environment Abstraction Layer (EAL) for AURA OS."""

import os
from typing import Dict, List, Tuple

from . import detector
from .adapters.android import AndroidAdapter
from .adapters.linux import LinuxAdapter
from .adapters.macos import MacOSAdapter
from .adapters.windows import WindowsAdapter
from .adapters.fallback import FallbackAdapter


class EAL:
    """Environment Abstraction Layer.

    Detects the host environment on instantiation and selects an appropriate
    adapter.  Exposes a unified API for file I/O, command execution, and
    environment introspection regardless of the underlying platform.
    """

    def __init__(self):
        self._platform = detector.get_platform()
        self._adapter = self._select_adapter()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _select_adapter(self):
        """Pick the best adapter for the detected platform."""
        if self._platform in ("termux", "android"):
            return AndroidAdapter()
        if self._platform == "linux":
            return LinuxAdapter()
        if self._platform == "macos":
            return MacOSAdapter()
        if self._platform == "windows":
            return WindowsAdapter()
        return FallbackAdapter()

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def adapter(self):
        """The active platform adapter instance."""
        return self._adapter

    @property
    def platform(self) -> str:
        """Normalised platform identifier string."""
        return self._platform

    # ------------------------------------------------------------------
    # File operations
    # ------------------------------------------------------------------

    def read_file(self, path: str) -> str:
        """Read and return the text content of *path*."""
        with open(path, "r", encoding="utf-8") as fh:
            return fh.read()

    def write_file(self, path: str, content: str):
        """Write *content* to *path*, creating parent directories as needed."""
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(content)

    def delete_file(self, path: str):
        """Delete the file at *path*."""
        os.remove(path)

    def list_dir(self, path: str) -> List[str]:
        """Return a sorted list of names in directory *path*."""
        return sorted(os.listdir(path))

    def make_dir(self, path: str):
        """Create directory *path* (and parents) if they do not exist."""
        os.makedirs(path, exist_ok=True)

    # ------------------------------------------------------------------
    # Command execution
    # ------------------------------------------------------------------

    def run_command(self, cmd: list, capture: bool = True) -> Tuple[int, str, str]:
        """Run *cmd* via the active adapter.

        Returns ``(returncode, stdout, stderr)``.
        """
        return self._adapter.run_command(cmd, capture=capture)

    # ------------------------------------------------------------------
    # Environment info
    # ------------------------------------------------------------------

    def get_env_info(self) -> Dict:
        """Return a combined environment information dict."""
        paths = detector.get_storage_paths()
        binaries = detector.get_available_binaries()
        perms = detector.get_permissions()
        sys_info = self._adapter.get_system_info()

        return {
            "platform": self._platform,
            "paths": paths,
            "binaries": binaries,
            "permissions": perms,
            "system": sys_info,
            "pkg_manager": self._adapter.available_pkg_manager(),
        }
