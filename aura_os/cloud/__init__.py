"""Cloud and distributed network extension layer for AURA OS.

Provides real cloud/network capabilities:
- HTTP/HTTPS service calls to remote APIs
- Remote node registration and health pinging
- Distributed command dispatch
- Cloud configuration management
- Network diagnostics

Usage::

    from aura_os.cloud import CloudClient, NodeRegistry
    cc = CloudClient()
    cc.ping("https://example.com")
    nr = NodeRegistry()
    nr.register("node-1", "http://10.0.0.2:7070")
"""

from .client import CloudClient
from .nodes import NodeRegistry

__all__ = ["CloudClient", "NodeRegistry"]
