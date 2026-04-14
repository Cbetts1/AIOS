"""AI session manager for AURA OS.

Manages multi-turn conversation context for the AURA AI persona.
Sessions are persisted under AURA_HOME/ai/sessions/ as JSON files.

Usage::

    from aura_os.ai.session import AuraSession
    session = AuraSession("operator")
    session.add_exchange("What is the system health?", "CPU 20%, RAM 40%.")
    history = session.recent_exchanges(5)
    session.save()
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional


class AuraSession:
    """Conversation session for the AURA AI assistant.

    Stores the exchange history (user/AURA message pairs) and provides
    context windows for multi-turn inference.

    Args:
        name: Session name (used as the filename slug).
        aura_home: Override AURA_HOME path.
        max_history: Maximum number of exchanges to keep in memory.
    """

    def __init__(
        self,
        name: str = "default",
        aura_home: Optional[str] = None,
        max_history: int = 50,
    ):
        self._name = name
        self._home = Path(
            aura_home or os.environ.get("AURA_HOME", os.path.expanduser("~/.aura"))
        )
        self._max_history = max_history
        self._exchanges: List[Dict[str, Any]] = []
        self._created_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        self._session_path = self._home / "ai" / "sessions" / f"{name}.json"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add_exchange(self, user: str, aura: str) -> None:
        """Record a user→AURA exchange."""
        self._exchanges.append({
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "user": user,
            "aura": aura,
        })
        # Trim to max_history
        if len(self._exchanges) > self._max_history:
            self._exchanges = self._exchanges[-self._max_history:]

    def recent_exchanges(self, n: int = 5) -> List[Dict[str, Any]]:
        """Return the *n* most recent exchanges."""
        return self._exchanges[-n:]

    def clear(self) -> None:
        """Clear all exchanges from memory (does not delete the file)."""
        self._exchanges = []

    def save(self) -> None:
        """Persist the session to disk."""
        self._session_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "name": self._name,
            "created_at": self._created_at,
            "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "exchanges": self._exchanges,
        }
        self._session_path.write_text(json.dumps(data, indent=2))

    def load(self) -> bool:
        """Load session from disk.  Returns True if found and loaded."""
        if not self._session_path.exists():
            return False
        try:
            data = json.loads(self._session_path.read_text())
            self._exchanges = data.get("exchanges", [])
            self._created_at = data.get("created_at", self._created_at)
            return True
        except (json.JSONDecodeError, OSError):
            return False

    def delete(self) -> bool:
        """Delete the persisted session file.  Returns True if deleted."""
        if self._session_path.exists():
            self._session_path.unlink()
            return True
        return False

    @classmethod
    def list_sessions(cls, aura_home: Optional[str] = None) -> List[str]:
        """Return names of all persisted sessions."""
        home = Path(aura_home or os.environ.get(
            "AURA_HOME", os.path.expanduser("~/.aura")
        ))
        session_dir = home / "ai" / "sessions"
        if not session_dir.exists():
            return []
        return [p.stem for p in sorted(session_dir.glob("*.json"))]

    @property
    def name(self) -> str:
        return self._name

    @property
    def exchange_count(self) -> int:
        return len(self._exchanges)
