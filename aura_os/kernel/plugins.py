"""Plugin system for AURA OS.

Provides dynamic plugin discovery, loading, and lifecycle management:
- Scan plugin directories for valid plugins
- Load/unload plugins at runtime
- Plugin metadata via ``plugin.json`` manifests
- Hooks for plugin initialization and teardown
"""

import importlib
import importlib.util
import json
import os
import sys
import threading
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional


@dataclass
class PluginMeta:
    """Metadata for a discovered plugin."""
    name: str
    version: str = "0.1.0"
    description: str = ""
    author: str = ""
    entry_point: str = "main.py"
    dependencies: List[str] = field(default_factory=list)
    enabled: bool = True


class PluginManager:
    """Discovers, loads, and manages plugins under ``~/.aura/plugins/``.

    Each plugin is a directory containing at minimum:
    - ``plugin.json``  — manifest with name, version, description
    - ``main.py``      — Python entry point with ``activate(ctx)``
                         and optional ``deactivate(ctx)`` functions

    Example plugin structure::

        ~/.aura/plugins/
            my-plugin/
                plugin.json
                main.py
    """

    def __init__(self, plugin_dir: str = None):
        aura_home = os.environ.get("AURA_HOME",
                                   os.path.expanduser("~/.aura"))
        self._dir = plugin_dir or os.path.join(aura_home, "plugins")
        os.makedirs(self._dir, exist_ok=True)
        self._plugins: Dict[str, PluginMeta] = {}
        self._loaded: Dict[str, object] = {}
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Discovery
    # ------------------------------------------------------------------

    def scan(self) -> List[PluginMeta]:
        """Scan the plugins directory and return found plugin metadata."""
        with self._lock:
            self._plugins.clear()
            if not os.path.isdir(self._dir):
                return []
            for name in sorted(os.listdir(self._dir)):
                plug_dir = os.path.join(self._dir, name)
                if not os.path.isdir(plug_dir):
                    continue
                manifest = os.path.join(plug_dir, "plugin.json")
                if not os.path.isfile(manifest):
                    continue
                try:
                    with open(manifest, "r", encoding="utf-8") as fh:
                        data = json.load(fh)
                    meta = PluginMeta(
                        name=data.get("name", name),
                        version=data.get("version", "0.1.0"),
                        description=data.get("description", ""),
                        author=data.get("author", ""),
                        entry_point=data.get("entry_point", "main.py"),
                        dependencies=data.get("dependencies", []),
                        enabled=data.get("enabled", True),
                    )
                    self._plugins[meta.name] = meta
                except (json.JSONDecodeError, KeyError):
                    continue
            return list(self._plugins.values())

    # ------------------------------------------------------------------
    # Load / unload
    # ------------------------------------------------------------------

    def load(self, name: str, ctx: Optional[Dict] = None) -> bool:
        """Load and activate plugin *name*.

        Returns True on success, False on failure.
        ``ctx`` is an optional context dict passed to the plugin's
        ``activate(ctx)`` function.
        """
        with self._lock:
            meta = self._plugins.get(name)
            if not meta or not meta.enabled:
                return False
            if name in self._loaded:
                return True  # already loaded

        plug_dir = os.path.join(self._dir, name)
        entry = os.path.join(plug_dir, meta.entry_point)
        if not os.path.isfile(entry):
            return False

        try:
            spec = importlib.util.spec_from_file_location(
                f"aura_plugin_{name}", entry)
            if spec is None or spec.loader is None:
                return False
            mod = importlib.util.module_from_spec(spec)
            sys.modules[f"aura_plugin_{name}"] = mod
            spec.loader.exec_module(mod)

            # Call activate() if present
            if hasattr(mod, "activate"):
                mod.activate(ctx or {})

            with self._lock:
                self._loaded[name] = mod
            return True
        except Exception:
            return False

    def unload(self, name: str, ctx: Optional[Dict] = None) -> bool:
        """Deactivate and unload plugin *name*."""
        with self._lock:
            mod = self._loaded.pop(name, None)
        if mod is None:
            return False
        try:
            if hasattr(mod, "deactivate"):
                mod.deactivate(ctx or {})
        except Exception:
            pass
        sys.modules.pop(f"aura_plugin_{name}", None)
        return True

    def reload(self, name: str, ctx: Optional[Dict] = None) -> bool:
        """Reload a plugin (unload then load)."""
        self.unload(name, ctx)
        return self.load(name, ctx)

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def list_plugins(self) -> List[Dict]:
        """Return all discovered plugins with their load status."""
        with self._lock:
            return [
                {
                    "name": m.name,
                    "version": m.version,
                    "description": m.description,
                    "author": m.author,
                    "enabled": m.enabled,
                    "loaded": m.name in self._loaded,
                }
                for m in self._plugins.values()
            ]

    def is_loaded(self, name: str) -> bool:
        """Check whether a plugin is currently loaded."""
        with self._lock:
            return name in self._loaded

    def get_plugin_module(self, name: str) -> Optional[object]:
        """Return the raw module object for a loaded plugin."""
        with self._lock:
            return self._loaded.get(name)

    # ------------------------------------------------------------------
    # Plugin scaffolding
    # ------------------------------------------------------------------

    def create_plugin(self, name: str, description: str = "",
                      author: str = "") -> str:
        """Scaffold a new plugin directory with boilerplate files.

        Returns the path to the new plugin directory.
        """
        plug_dir = os.path.join(self._dir, name)
        os.makedirs(plug_dir, exist_ok=True)

        manifest = {
            "name": name,
            "version": "0.1.0",
            "description": description,
            "author": author,
            "entry_point": "main.py",
            "dependencies": [],
            "enabled": True,
        }
        with open(os.path.join(plug_dir, "plugin.json"), "w",
                  encoding="utf-8") as fh:
            json.dump(manifest, fh, indent=2)

        main_py = (
            '"""AURA OS Plugin: {name}"""\n\n\n'
            'def activate(ctx):\n'
            '    """Called when the plugin is loaded."""\n'
            '    pass\n\n\n'
            'def deactivate(ctx):\n'
            '    """Called when the plugin is unloaded."""\n'
            '    pass\n'
        ).format(name=name)
        with open(os.path.join(plug_dir, "main.py"), "w",
                  encoding="utf-8") as fh:
            fh.write(main_py)

        return plug_dir
