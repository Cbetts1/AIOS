"""
EAL Adapter: macOS

Proper macOS adapter with Homebrew integration and launchd auto-start
support (LaunchAgent plist files).
"""

import os
import shutil
import subprocess
from pathlib import Path
from eal.adapters import BaseAdapter


class MacOSAdapter(BaseAdapter):
    """
    Adapter for macOS systems.

    Uses Homebrew for package management and supports LaunchAgent
    plist files for auto-start on login.
    """

    def __init__(self, env_map):
        super().__init__(env_map)

    # ------------------------------------------------------------------ #
    # Package management
    # ------------------------------------------------------------------ #

    def get_package_manager(self):
        if shutil.which("brew"):
            return "brew"
        # MacPorts fallback
        if shutil.which("port"):
            return "port"
        return None

    def install_package(self, package_name):
        pm = self.get_package_manager()
        if not pm:
            return False
        if pm == "brew":
            cmd = ["brew", "install", package_name]
        elif pm == "port":
            cmd = ["sudo", "port", "install", package_name]
        else:
            return False
        rc, _, _ = self.run(cmd, capture=True)
        return rc == 0

    # ------------------------------------------------------------------ #
    # LaunchAgent auto-start
    # ------------------------------------------------------------------ #

    def setup_launchagent(self, label: str, exec_path: str,
                          description: str = "AURA OS Service"):
        """
        Install a LaunchAgent plist so AURA starts on user login.
        Returns True if successful.
        """
        agents_dir = Path.home() / "Library" / "LaunchAgents"
        agents_dir.mkdir(parents=True, exist_ok=True)
        plist_path = agents_dir / f"{label}.plist"

        plist_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{label}</string>
    <key>ProgramArguments</key>
    <array>
        <string>{exec_path}</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <false/>
    <key>StandardOutPath</key>
    <string>{Path.home()}/.aura/logs/{label}.stdout.log</string>
    <key>StandardErrorPath</key>
    <string>{Path.home()}/.aura/logs/{label}.stderr.log</string>
</dict>
</plist>
"""
        try:
            plist_path.write_text(plist_content)
            # Load the agent
            rc, _, _ = self.run(["launchctl", "load", str(plist_path)], capture=True)
            return rc == 0
        except Exception:
            return False

    # ------------------------------------------------------------------ #
    # Storage info
    # ------------------------------------------------------------------ #

    def storage_info(self):
        stat = shutil.disk_usage(str(Path.home()))
        return {
            "total_mb": stat.total // (1024 * 1024),
            "used_mb": stat.used // (1024 * 1024),
            "free_mb": stat.free // (1024 * 1024),
        }
