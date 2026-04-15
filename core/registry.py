"""
Core Command Registry
Stores registered commands, their handlers, and metadata.

Also provides the CapabilityRegistry for the Capability Forge OS prototype,
which loads capabilities from config/capabilities.json and from any
capabilities/generated/*/meta.json files written by the generator.

.. deprecated::
    The legacy CommandRegistry class in this module is superseded by
    ``aura_os/engine/``.  New code should import from ``aura_os.engine``
    instead.  The CapabilityRegistry is new and lives here intentionally.
"""

import glob
import json
import os
from typing import Callable, Dict, Any, List, Optional

from core.models import Capability

# Paths are relative to the repository root (parent of this package).
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_CAPABILITIES_JSON = os.path.join(_REPO_ROOT, "config", "capabilities.json")
_GENERATED_GLOB = os.path.join(_REPO_ROOT, "capabilities", "generated", "*", "meta.json")


class CommandRegistry:
    """
    A simple registry that maps command names (strings) to handler functions.

    Each entry stores:
      - handler: callable(args: list, ctx: dict) -> None
      - description: short help text
      - usage: usage string shown in help
    """

    def __init__(self):
        self._commands: Dict[str, Dict[str, Any]] = {}

    def register(
        self,
        name: str,
        handler: Callable,
        description: str = "",
        usage: str = "",
    ):
        self._commands[name] = {
            "handler": handler,
            "description": description,
            "usage": usage or name,
        }

    def get(self, name: str) -> Optional[Dict[str, Any]]:
        return self._commands.get(name)

    def all_commands(self) -> Dict[str, Dict[str, Any]]:
        return dict(self._commands)

    def names(self):
        return list(self._commands.keys())


class CapabilityRegistry:
    """
    Registry of Capability objects for the Capability Forge OS prototype.

    Loads seed capabilities from ``config/capabilities.json`` and
    auto-discovers generated capabilities from
    ``capabilities/generated/*/meta.json``.
    """

    def __init__(self) -> None:
        self._capabilities: Dict[str, Capability] = {}

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    def load(
        self,
        json_path: str = _CAPABILITIES_JSON,
        generated_glob: str = _GENERATED_GLOB,
    ) -> None:
        """Load seed capabilities then generated capabilities from disk."""
        self._load_json(json_path)
        self._load_generated(generated_glob)

    def _load_json(self, path: str) -> None:
        if not os.path.exists(path):
            return
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        for item in data:
            cap = Capability.from_dict(item)
            if cap.id not in self._capabilities:
                self._capabilities[cap.id] = cap

    def _load_generated(self, pattern: str) -> None:
        for meta_path in glob.glob(pattern):
            try:
                with open(meta_path, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
                cap = Capability.from_dict(data)
                if cap.id not in self._capabilities:
                    self._capabilities[cap.id] = cap
            except (json.JSONDecodeError, KeyError):
                pass

    # ------------------------------------------------------------------
    # Mutation
    # ------------------------------------------------------------------

    def add(self, capability: Capability) -> None:
        """Register a Capability in memory (no file I/O)."""
        self._capabilities[capability.id] = capability

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get(self, cap_id: str) -> Optional[Capability]:
        return self._capabilities.get(cap_id)

    def all(self) -> List[Capability]:
        return list(self._capabilities.values())

    def ids(self) -> List[str]:
        return list(self._capabilities.keys())

    def count(self) -> int:
        return len(self._capabilities)
