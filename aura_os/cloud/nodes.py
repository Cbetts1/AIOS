"""Remote node registry for AURA OS cloud layer.

Tracks remote AURA OS nodes for fleet management:
- Register/deregister nodes
- Ping nodes for liveness
- Query remote node status via the AURA web API
- Persist node registry to AURA_HOME/cloud/nodes.json
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional


class NodeRegistry:
    """Registry of remote AURA OS nodes.

    Nodes are persisted as JSON under ``<aura_home>/cloud/nodes.json``.

    Each node record::

        {
            "name": "worker-1",
            "url": "http://10.0.0.2:7070",
            "registered_at": "2025-01-01T00:00:00",
            "last_seen": "2025-01-01T00:05:00",
            "status": "online"
        }
    """

    def __init__(self, aura_home: str = None):
        self._home = Path(aura_home or os.environ.get(
            "AURA_HOME", os.path.expanduser("~/.aura")
        ))
        self._registry_path = self._home / "cloud" / "nodes.json"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def register(self, name: str, url: str) -> Dict[str, Any]:
        """Add or update a node in the registry."""
        nodes = self._load()
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        existing = next((n for n in nodes if n["name"] == name), None)
        if existing:
            existing["url"] = url
            existing["last_seen"] = now
        else:
            nodes.append({
                "name": name,
                "url": url.rstrip("/"),
                "registered_at": now,
                "last_seen": now,
                "status": "unknown",
            })
        self._save(nodes)
        return next(n for n in nodes if n["name"] == name)

    def deregister(self, name: str) -> bool:
        """Remove a node from the registry.  Returns True if it existed."""
        nodes = self._load()
        new_nodes = [n for n in nodes if n["name"] != name]
        if len(new_nodes) == len(nodes):
            return False
        self._save(new_nodes)
        return True

    def list_nodes(self) -> List[Dict[str, Any]]:
        """Return all registered nodes."""
        return self._load()

    def get_node(self, name: str) -> Optional[Dict[str, Any]]:
        """Return a node by name, or None."""
        return next((n for n in self._load() if n["name"] == name), None)

    def ping_node(self, name: str) -> bool:
        """Ping a node and update its status.  Returns True if online."""
        node = self.get_node(name)
        if not node:
            return False
        from aura_os.cloud.client import CloudClient
        client = CloudClient(timeout=5)
        reachable, code, _ = client.ping(node["url"])
        status = "online" if reachable and code < 500 else "offline"
        self._update_status(name, status)
        return reachable

    def ping_all(self) -> Dict[str, bool]:
        """Ping all registered nodes.  Returns {name: online} map."""
        results = {}
        for node in self.list_nodes():
            results[node["name"]] = self.ping_node(node["name"])
        return results

    def query_status(self, name: str) -> Optional[Dict[str, Any]]:
        """Query the ``/api/status`` endpoint of a remote node."""
        node = self.get_node(name)
        if not node:
            return None
        from aura_os.cloud.client import CloudClient
        client = CloudClient(base_url=node["url"], timeout=5)
        code, body = client.get("/api/status")
        if code == 200 and isinstance(body, dict):
            return body
        return None

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load(self) -> List[Dict[str, Any]]:
        if not self._registry_path.exists():
            return []
        try:
            return json.loads(self._registry_path.read_text())
        except (json.JSONDecodeError, OSError):
            return []

    def _save(self, nodes: List[Dict[str, Any]]) -> None:
        self._registry_path.parent.mkdir(parents=True, exist_ok=True)
        self._registry_path.write_text(json.dumps(nodes, indent=2))

    def _update_status(self, name: str, status: str) -> None:
        nodes = self._load()
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        for node in nodes:
            if node["name"] == name:
                node["status"] = status
                node["last_seen"] = now
                break
        self._save(nodes)
