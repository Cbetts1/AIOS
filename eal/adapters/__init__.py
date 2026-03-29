"""
EAL Adapter: Base class shared by all environment adapters.
"""

import os
import subprocess
import shutil
from pathlib import Path


class BaseAdapter:
    """
    Common interface that all environment adapters must implement.
    Subclasses override methods to provide platform-specific behaviour.
    """

    def __init__(self, env_map):
        self.env = env_map
        self.storage_root = Path(env_map.get("storage_root", Path.home() / ".aura"))
        self.storage_root.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------ #
    # File operations
    # ------------------------------------------------------------------ #

    def read_file(self, path):
        """Return contents of *path* as a string."""
        with open(path, "r", errors="replace") as f:
            return f.read()

    def write_file(self, path, content, mode="w"):
        """Write *content* to *path*, creating parent directories as needed."""
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, mode) as f:
            f.write(content)

    def list_dir(self, path="."):
        """Return a list of (name, is_dir) tuples for *path*."""
        entries = []
        for entry in sorted(Path(path).iterdir()):
            entries.append((entry.name, entry.is_dir()))
        return entries

    def exists(self, path):
        return Path(path).exists()

    def delete(self, path):
        p = Path(path)
        if p.is_dir():
            shutil.rmtree(p)
        else:
            p.unlink(missing_ok=True)

    def move(self, src, dst):
        shutil.move(str(src), str(dst))

    def copy(self, src, dst):
        src, dst = Path(src), Path(dst)
        if src.is_dir():
            shutil.copytree(str(src), str(dst), dirs_exist_ok=True)
        else:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(src), str(dst))

    # ------------------------------------------------------------------ #
    # Process execution
    # ------------------------------------------------------------------ #

    def run(self, cmd, capture=False, timeout=60, cwd=None, env=None):
        """
        Execute *cmd* (list or string).
        Returns (returncode, stdout, stderr).
        """
        try:
            result = subprocess.run(
                cmd,
                shell=isinstance(cmd, str),
                capture_output=capture,
                text=True,
                timeout=timeout,
                cwd=cwd,
                env=env,
            )
            return result.returncode, result.stdout or "", result.stderr or ""
        except FileNotFoundError as e:
            return 1, "", str(e)
        except subprocess.TimeoutExpired:
            return 1, "", "Command timed out"

    def run_bg(self, cmd, cwd=None):
        """Start *cmd* in the background and return the Popen object."""
        return subprocess.Popen(
            cmd,
            shell=isinstance(cmd, str),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            cwd=cwd,
        )

    # ------------------------------------------------------------------ #
    # Networking helpers
    # ------------------------------------------------------------------ #

    def has_network(self):
        return self.env.get("has_network", False)

    # ------------------------------------------------------------------ #
    # Package management (to be overridden)
    # ------------------------------------------------------------------ #

    def install_package(self, package_name):
        """Install a system-level package. Returns True on success."""
        raise NotImplementedError

    def get_package_manager(self):
        """Return the name of the system package manager, or None."""
        return None

    # ------------------------------------------------------------------ #
    # Misc helpers
    # ------------------------------------------------------------------ #

    def get_temp_dir(self):
        import tempfile
        return Path(tempfile.gettempdir())

    def which(self, binary):
        return shutil.which(binary)

    def home_dir(self):
        return Path.home()

    def env_info(self):
        return self.env
