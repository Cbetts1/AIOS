"""Settings loader for AURA OS."""

import json
import os
import threading
from typing import Any

from .defaults import DEFAULT_CONFIG


def _deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge override into base, returning new dict."""
    result = dict(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


class Settings:
    """Singleton settings manager with dot-notation access.

    Loads ~/.aura/config/settings.json and merges with DEFAULT_CONFIG.
    Supports dot-notation for nested keys, e.g. settings.get("ai.default_model").
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls, config_path: str = None):
        with cls._lock:
            if cls._instance is None:
                instance = super().__new__(cls)
                instance._initialized = False
                cls._instance = instance
            return cls._instance

    def __init__(self, config_path: str = None):
        if self._initialized:
            return
        aura_home = os.environ.get("AURA_HOME", os.path.expanduser("~/.aura"))
        self._config_path = config_path or os.path.join(aura_home, "config", "settings.json")
        self._data: dict = {}
        self._file_lock = threading.Lock()
        self._load()
        self._initialized = True

    @classmethod
    def reset(cls):
        """Reset singleton (primarily for testing)."""
        with cls._lock:
            cls._instance = None

    def _load(self):
        """Load settings from disk and merge with defaults."""
        disk_config = {}
        if os.path.isfile(self._config_path):
            try:
                with open(self._config_path, "r", encoding="utf-8") as fh:
                    disk_config = json.load(fh)
            except (json.JSONDecodeError, OSError) as exc:
                print(f"[aura] Warning: could not read settings ({exc}); using defaults.")
        self._data = _deep_merge(DEFAULT_CONFIG, disk_config)

    def _save(self):
        """Persist current settings to disk."""
        os.makedirs(os.path.dirname(self._config_path), exist_ok=True)
        with self._file_lock:
            with open(self._config_path, "w", encoding="utf-8") as fh:
                json.dump(self._data, fh, indent=2)

    def get(self, key: str, default: Any = None) -> Any:
        """Retrieve a value using dot-notation key (e.g. 'ai.default_model')."""
        parts = key.split(".")
        node = self._data
        for part in parts:
            if not isinstance(node, dict) or part not in node:
                return default
            node = node[part]
        return node

    def set(self, key: str, value: Any):
        """Set a value using dot-notation key and persist to disk."""
        parts = key.split(".")
        node = self._data
        for part in parts[:-1]:
            if part not in node or not isinstance(node[part], dict):
                node[part] = {}
            node = node[part]
        node[parts[-1]] = value
        self._save()

    def as_dict(self) -> dict:
        """Return a shallow copy of the full settings dict."""
        return dict(self._data)
