"""JSON-backed key-value store for AURA OS."""

import json
import os
import threading
from typing import Any, List


class KVStore:
    """Thread-safe persistent key-value store backed by a JSON file.

    Default store path: ``~/.aura/data/store.json``.
    All read/write operations acquire a threading lock and re-read/re-write
    the file to ensure consistency between threads.
    """

    def __init__(self, store_path: str = None):
        if store_path is None:
            aura_home = os.environ.get("AURA_HOME", os.path.expanduser("~/.aura"))
            store_path = os.path.join(aura_home, "data", "store.json")
        self._path = store_path
        self._lock = threading.Lock()
        os.makedirs(os.path.dirname(self._path), exist_ok=True)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _read(self) -> dict:
        if not os.path.isfile(self._path):
            return {}
        try:
            with open(self._path, "r", encoding="utf-8") as fh:
                return json.load(fh)
        except (json.JSONDecodeError, OSError):
            return {}

    def _write(self, data: dict):
        with open(self._path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get(self, key: str, default: Any = None) -> Any:
        """Return the value for *key*, or *default* if not found."""
        with self._lock:
            return self._read().get(key, default)

    def set(self, key: str, value: Any):
        """Persist *value* under *key*."""
        with self._lock:
            data = self._read()
            data[key] = value
            self._write(data)

    def delete(self, key: str):
        """Remove *key* from the store (no-op if absent)."""
        with self._lock:
            data = self._read()
            data.pop(key, None)
            self._write(data)

    def keys(self) -> List[str]:
        """Return a list of all keys currently in the store."""
        with self._lock:
            return list(self._read().keys())

    def clear(self):
        """Remove all key-value pairs from the store."""
        with self._lock:
            self._write({})
