"""Package manager for AURA OS."""

import json
import os
import shutil
import subprocess
from typing import List, Optional

from .registry import LocalRegistry


class PackageManager:
    """High-level package management interface.

    Packages can be installed from:
    - A local ``.aura-pkg.json`` manifest file
    - A name looked up in the local :class:`LocalRegistry`

    Installed packages are tracked in ``~/.aura/pkg/installed/``.
    """

    def __init__(self, registry: LocalRegistry = None):
        aura_home = os.environ.get("AURA_HOME", os.path.expanduser("~/.aura"))
        self._install_dir = os.path.join(aura_home, "pkg", "installed")
        os.makedirs(self._install_dir, exist_ok=True)
        self._registry = registry or LocalRegistry()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _installed_manifest_path(self, name: str) -> str:
        return os.path.join(self._install_dir, f"{name}.json")

    def _is_installed(self, name: str) -> bool:
        return os.path.isfile(self._installed_manifest_path(name))

    def _save_installed(self, manifest: dict):
        path = self._installed_manifest_path(manifest["name"])
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(manifest, fh, indent=2)

    def _load_installed(self, name: str) -> Optional[dict]:
        path = self._installed_manifest_path(name)
        if not os.path.isfile(path):
            return None
        try:
            with open(path, "r", encoding="utf-8") as fh:
                return json.load(fh)
        except (json.JSONDecodeError, OSError):
            return None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def install(self, name_or_path: str) -> bool:
        """Install a package from a manifest file path or registry name.

        Returns True on success, False on failure.
        """
        manifest = None

        # Check if it looks like a file path
        if os.path.isfile(name_or_path):
            try:
                with open(name_or_path, "r", encoding="utf-8") as fh:
                    manifest = json.load(fh)
            except (json.JSONDecodeError, OSError) as exc:
                print(f"[pkg] Error reading manifest: {exc}")
                return False
        else:
            manifest = self._registry.get_package(name_or_path)
            if manifest is None:
                print(f"[pkg] Package '{name_or_path}' not found in registry.")
                return False

        name = manifest.get("name", "unknown")
        version = manifest.get("version", "?")

        if self._is_installed(name):
            print(f"[pkg] '{name}' is already installed.")
            return True

        # Run install_cmd if specified
        install_cmd = manifest.get("install_cmd")
        if install_cmd:
            print(f"[pkg] Running install command for '{name}'...")
            # Use shlex.split to avoid shell=True and reduce injection risk
            import shlex
            try:
                cmd_list = shlex.split(install_cmd)
            except ValueError as exc:
                print(f"[pkg] Invalid install_cmd for '{name}': {exc}")
                return False
            result = subprocess.run(cmd_list, text=True)
            if result.returncode != 0:
                print(f"[pkg] Install command failed for '{name}'.")
                return False

        # Register as installed
        self._save_installed(manifest)
        # Also ensure it's in the registry
        self._registry.add_package(manifest)
        print(f"[pkg] Installed '{name}' v{version}.")
        return True

    def remove(self, name: str) -> bool:
        """Uninstall a package by name.

        Returns True if the package was removed, False if not installed.
        """
        if not self._is_installed(name):
            print(f"[pkg] '{name}' is not installed.")
            return False
        os.remove(self._installed_manifest_path(name))
        print(f"[pkg] Removed '{name}'.")
        return True

    def list_installed(self) -> List[dict]:
        """Return a list of manifests for all installed packages."""
        packages = []
        for fname in os.listdir(self._install_dir):
            if fname.endswith(".json"):
                pkg_name = fname[:-5]
                manifest = self._load_installed(pkg_name)
                if manifest:
                    packages.append(manifest)
        return sorted(packages, key=lambda p: p.get("name", ""))

    def search(self, query: str) -> List[dict]:
        """Search the registry for packages matching *query* (case-insensitive).

        Matches against name and description fields.
        """
        query_lower = query.lower()
        results = []
        for pkg in self._registry.list_packages():
            name = pkg.get("name", "").lower()
            desc = pkg.get("description", "").lower()
            if query_lower in name or query_lower in desc:
                results.append(pkg)
        return results
