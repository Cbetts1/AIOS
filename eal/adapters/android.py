"""
EAL Adapter: Android / Termux
"""

import os
import shutil
from pathlib import Path
from eal.adapters import BaseAdapter


class AndroidAdapter(BaseAdapter):
    """
    Adapter for Termux on Android.

    Termux uses its own PREFIX at /data/data/com.termux/files/usr and
    stores user files at /data/data/com.termux/files/home.
    """

    TERMUX_PREFIX = Path(os.environ.get("PREFIX", "/data/data/com.termux/files/usr"))
    TERMUX_HOME = Path(os.environ.get("HOME", "/data/data/com.termux/files/home"))

    def __init__(self, env_map):
        super().__init__(env_map)

    # ------------------------------------------------------------------ #
    # Package management
    # ------------------------------------------------------------------ #

    def get_package_manager(self):
        if shutil.which("pkg"):
            return "pkg"
        if shutil.which("apt"):
            return "apt"
        return None

    def install_package(self, package_name):
        pm = self.get_package_manager()
        if not pm:
            return False
        rc, _, _ = self.run([pm, "install", "-y", package_name], capture=True)
        return rc == 0

    # ------------------------------------------------------------------ #
    # Termux-specific helpers
    # ------------------------------------------------------------------ #

    def termux_prefix(self):
        return self.TERMUX_PREFIX

    def termux_home(self):
        return self.TERMUX_HOME

    def setup_termux_boot(self, startup_script_path):
        """
        Register a script with Termux:Boot so that it runs on device boot.
        Returns True if successful.
        """
        boot_dir = self.TERMUX_HOME / ".termux" / "boot"
        try:
            boot_dir.mkdir(parents=True, exist_ok=True)
            dest = boot_dir / "aura_start.sh"
            shutil.copy2(str(startup_script_path), str(dest))
            dest.chmod(0o755)
            return True
        except Exception as e:
            print(f"[WARN] Could not set up Termux:Boot: {e}")
            return False

    def storage_info(self):
        """Return storage statistics for the Termux home directory."""
        stat = shutil.disk_usage(str(self.TERMUX_HOME))
        return {
            "total_mb": stat.total // (1024 * 1024),
            "used_mb": stat.used // (1024 * 1024),
            "free_mb": stat.free // (1024 * 1024),
        }
