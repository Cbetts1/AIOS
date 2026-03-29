"""
EAL Adapter: Linux (and macOS)
"""

import os
import shutil
import platform
from pathlib import Path
from eal.adapters import BaseAdapter


class LinuxAdapter(BaseAdapter):
    """
    Adapter for standard Linux and macOS systems.
    """

    def __init__(self, env_map):
        super().__init__(env_map)
        self._system = platform.system().lower()

    # ------------------------------------------------------------------ #
    # Package management
    # ------------------------------------------------------------------ #

    def get_package_manager(self):
        for pm in ("apt-get", "apt", "dnf", "yum", "pacman", "brew", "zypper"):
            if shutil.which(pm):
                return pm
        return None

    def install_package(self, package_name):
        pm = self.get_package_manager()
        if not pm:
            return False

        if pm in ("apt-get", "apt"):
            cmd = ["sudo", pm, "install", "-y", package_name]
        elif pm in ("dnf", "yum"):
            cmd = ["sudo", pm, "install", "-y", package_name]
        elif pm == "pacman":
            cmd = ["sudo", pm, "-S", "--noconfirm", package_name]
        elif pm == "brew":
            cmd = ["brew", "install", package_name]
        elif pm == "zypper":
            cmd = ["sudo", pm, "install", "-y", package_name]
        else:
            return False

        rc, _, _ = self.run(cmd, capture=True)
        return rc == 0

    # ------------------------------------------------------------------ #
    # Systemd / launchd auto-start
    # ------------------------------------------------------------------ #

    def setup_systemd_service(self, service_name, exec_start, description="AURA OS Service"):
        """
        Install a systemd user service so AURA starts on login.
        Returns True if successful.
        """
        if self._system != "linux" or not shutil.which("systemctl"):
            return False

        service_dir = Path.home() / ".config" / "systemd" / "user"
        service_dir.mkdir(parents=True, exist_ok=True)
        service_file = service_dir / f"{service_name}.service"
        content = f"""[Unit]
Description={description}
After=default.target

[Service]
Type=simple
ExecStart={exec_start}
Restart=on-failure

[Install]
WantedBy=default.target
"""
        service_file.write_text(content)
        rc1, _, _ = self.run(["systemctl", "--user", "daemon-reload"], capture=True)
        rc2, _, _ = self.run(["systemctl", "--user", "enable", service_name], capture=True)
        return rc1 == 0 and rc2 == 0

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
