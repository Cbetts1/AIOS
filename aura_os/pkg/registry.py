"""Local package registry for AURA OS."""

import json
import os
from typing import Dict, List, Optional


class LocalRegistry:
    """JSON-backed local package registry.

    The registry file lives at ``~/.aura/pkg/registry.json``.  Each entry is a
    *package manifest* dict with at minimum the keys: ``name``, ``version``,
    ``description``, ``files``, ``install_cmd``, and ``dependencies``.
    """

    REQUIRED_FIELDS = {"name", "version"}

    def __init__(self, registry_path: str = None):
        if registry_path is None:
            aura_home = os.environ.get("AURA_HOME", os.path.expanduser("~/.aura"))
            registry_path = os.path.join(aura_home, "pkg", "registry.json")
        self._path = registry_path
        os.makedirs(os.path.dirname(self._path), exist_ok=True)
        if not os.path.isfile(self._path):
            self._write({})

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _read(self) -> Dict[str, dict]:
        try:
            with open(self._path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
                if isinstance(data, dict):
                    return data
        except (json.JSONDecodeError, OSError):
            pass
        return {}

    def _write(self, data: Dict[str, dict]):
        with open(self._path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)

    def _validate(self, manifest: dict):
        missing = self.REQUIRED_FIELDS - set(manifest.keys())
        if missing:
            raise ValueError(f"Package manifest missing required fields: {missing}")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def list_packages(self) -> List[dict]:
        """Return a list of all registered package manifests."""
        return list(self._read().values())

    def get_package(self, name: str) -> Optional[dict]:
        """Return the manifest for *name*, or None if not found."""
        return self._read().get(name)

    def add_package(self, manifest: dict):
        """Add or update a package entry in the registry.

        The manifest must contain at least ``name`` and ``version``.
        """
        self._validate(manifest)
        data = self._read()
        data[manifest["name"]] = manifest
        self._write(data)

    def remove_package(self, name: str) -> bool:
        """Remove *name* from the registry.

        Returns True if the package was found and removed, False otherwise.
        """
        data = self._read()
        if name in data:
            del data[name]
            self._write(data)
            return True
        return False
