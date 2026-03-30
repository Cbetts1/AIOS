"""
EAL Adapter: Fallback
Used when the host environment is Windows or unknown.
"""

import os
import shutil
import sys
from pathlib import Path
from eal.adapters import BaseAdapter


class FallbackAdapter(BaseAdapter):
    """
    Minimal adapter for unknown or unsupported environments.
    Attempts best-effort operation using only Python's standard library.
    """

    def __init__(self, env_map):
        super().__init__(env_map)

    # ------------------------------------------------------------------ #
    # Package management
    # ------------------------------------------------------------------ #

    def get_package_manager(self):
        # On Windows, check for winget or chocolatey
        for pm in ("winget", "choco", "scoop"):
            if shutil.which(pm):
                return pm
        return None

    def install_package(self, package_name):
        pm = self.get_package_manager()
        if not pm:
            return False

        if pm == "winget":
            cmd = ["winget", "install", "--accept-source-agreements", package_name]
        elif pm == "choco":
            cmd = ["choco", "install", "-y", package_name]
        elif pm == "scoop":
            cmd = ["scoop", "install", package_name]
        else:
            return False

        rc, _, _ = self.run(cmd, capture=True)
        return rc == 0

    # ------------------------------------------------------------------ #
    # Storage info
    # ------------------------------------------------------------------ #

    def storage_info(self):
        try:
            stat = shutil.disk_usage(str(self.storage_root))
            return {
                "total_mb": stat.total // (1024 * 1024),
                "used_mb": stat.used // (1024 * 1024),
                "free_mb": stat.free // (1024 * 1024),
            }
        except Exception:
            return {"total_mb": 0, "used_mb": 0, "free_mb": 0}
