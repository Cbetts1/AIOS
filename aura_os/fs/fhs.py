"""Virtual Filesystem Hierarchy Standard (FHS) for AURA OS."""

import socket

from aura_os.fs.vfs import VirtualFS


class VirtualFHS(VirtualFS):
    """A VirtualFS pre-populated with a standard FHS-like directory tree."""

    def __init__(self, base_dir: str = None):
        super().__init__(base_dir=base_dir)
        self._init_hierarchy()

    def _init_hierarchy(self) -> None:
        """Create standard FHS directories and system files."""
        dirs = [
            "etc", "etc/aura",
            "var", "var/log", "var/run", "var/cache",
            "home", "tmp",
            "bin", "lib",
            "usr", "usr/bin", "usr/lib", "usr/share",
        ]
        for d in dirs:
            self.mkdir(d)
        self._init_system_files()

    def _init_system_files(self) -> None:
        """Write standard system config files if they do not already exist."""
        from aura_os import __version__

        files = {
            "etc/hostname": socket.gethostname(),
            "etc/os-release": (
                'NAME="AURA OS"\n'
                f'VERSION="{__version__}"\n'
                'ID=aura\n'
                f'PRETTY_NAME="AURA OS {__version__}"\n'
            ),
            "etc/hosts": (
                "127.0.0.1   localhost\n"
                "::1         localhost\n"
            ),
            "etc/fstab": (
                "# AURA OS fstab\n"
                "tmpfs  /tmp     tmpfs  defaults  0 0\n"
                "tmpfs  /var/run tmpfs  defaults  0 0\n"
            ),
            "etc/aura/version": __version__,
            "etc/shells": "/aura/bin/sh\n/bin/sh\n/bin/bash\n",
        }
        for path, content in files.items():
            if not self.exists(path):
                self.write(path, content)

    # ------------------------------------------------------------------
    # Convenience helpers
    # ------------------------------------------------------------------

    def read_etc(self, name: str) -> str:
        """Read a file from the ``etc/`` directory."""
        return self.read(f"etc/{name}")

    def write_etc(self, name: str, content: str) -> None:
        """Write a file into the ``etc/`` directory."""
        self.write(f"etc/{name}", content)
