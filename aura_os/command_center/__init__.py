"""Command Center — the central dashboard of AURA OS.

Provides both a terminal-based dashboard and a lightweight web API so the
user can manage the OS from a browser, a cloud host, or the local shell.
"""

from .dashboard import CommandCenter
from .web import create_app

__all__ = ["CommandCenter", "create_app"]
