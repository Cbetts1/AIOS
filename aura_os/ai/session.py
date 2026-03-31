"""Aura conversation-session manager.

Tracks conversation history and allows save/load to disk (and later to a
remote cloud endpoint).  Each session is JSON-serialisable so it can be
exported to a webpage or cloud storage.
"""

from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional


@dataclass
class Message:
    """A single message in a conversation."""
    role: str          # "user" or "aura"
    content: str
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {"role": self.role, "content": self.content, "timestamp": self.timestamp}

    @classmethod
    def from_dict(cls, data: dict) -> "Message":
        return cls(role=data["role"], content=data["content"], timestamp=data.get("timestamp", 0.0))


@dataclass
class Session:
    """A conversation session between the user and Aura."""

    session_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    created_at: float = field(default_factory=time.time)
    messages: List[Message] = field(default_factory=list)
    metadata: Dict[str, str] = field(default_factory=dict)

    # ── conversation API ────────────────────────────────────────────

    def add_user_message(self, content: str) -> Message:
        msg = Message(role="user", content=content)
        self.messages.append(msg)
        return msg

    def add_aura_message(self, content: str) -> Message:
        msg = Message(role="aura", content=content)
        self.messages.append(msg)
        return msg

    def get_history(self, last_n: int = 0) -> List[Message]:
        """Return message history.  If *last_n* > 0, return last N messages."""
        if last_n > 0:
            return self.messages[-last_n:]
        return list(self.messages)

    def clear(self) -> None:
        self.messages.clear()

    # ── persistence ─────────────────────────────────────────────────

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "created_at": self.created_at,
            "messages": [m.to_dict() for m in self.messages],
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Session":
        msgs = [Message.from_dict(m) for m in data.get("messages", [])]
        return cls(
            session_id=data.get("session_id", uuid.uuid4().hex[:12]),
            created_at=data.get("created_at", time.time()),
            messages=msgs,
            metadata=data.get("metadata", {}),
        )

    def save(self, path: Optional[str] = None) -> str:
        """Save session to a JSON file.  Returns the path used."""
        if path is None:
            aura_home = os.environ.get("AURA_HOME", os.path.expanduser("~/.aura"))
            path = os.path.join(aura_home, "data", "sessions", f"{self.session_id}.json")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(self.to_dict(), fh, indent=2)
        return path

    @classmethod
    def load(cls, path: str) -> "Session":
        """Load a session from a JSON file."""
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return cls.from_dict(data)


class SessionManager:
    """Manages multiple conversation sessions on disk.

    Sessions are stored as JSON files under ``~/.aura/data/sessions/``.
    This design makes it trivial to sync sessions to cloud storage or a
    web server later.
    """

    def __init__(self, sessions_dir: Optional[str] = None):
        if sessions_dir is None:
            aura_home = os.environ.get("AURA_HOME", os.path.expanduser("~/.aura"))
            sessions_dir = os.path.join(aura_home, "data", "sessions")
        self._dir = sessions_dir
        os.makedirs(self._dir, exist_ok=True)

    @staticmethod
    def _safe_id(session_id: str) -> str:
        """Sanitise a session ID to prevent path-traversal attacks."""
        # Only allow alphanumeric characters, hyphens, and underscores
        safe = "".join(c for c in os.path.basename(session_id) if c.isalnum() or c in "-_")
        if not safe:
            raise ValueError("Invalid session ID")
        return safe

    def new_session(self) -> Session:
        """Create and persist a fresh session."""
        session = Session()
        safe_id = self._safe_id(session.session_id)
        session.save(os.path.join(self._dir, f"{safe_id}.json"))
        return session

    def list_sessions(self) -> List[str]:
        """Return session IDs available on disk."""
        ids = []
        try:
            for fname in sorted(os.listdir(self._dir)):
                if fname.endswith(".json"):
                    ids.append(fname[:-5])
        except OSError:
            pass
        return ids

    def get_session(self, session_id: str) -> Optional[Session]:
        """Load a session by ID, or return None."""
        safe_id = self._safe_id(session_id)
        path = os.path.join(self._dir, f"{safe_id}.json")
        if not os.path.isfile(path):
            return None
        return Session.load(path)

    def delete_session(self, session_id: str) -> bool:
        """Delete a session file.  Returns True on success."""
        safe_id = self._safe_id(session_id)
        path = os.path.join(self._dir, f"{safe_id}.json")
        try:
            os.remove(path)
            return True
        except OSError:
            return False

    def export_session(self, session_id: str) -> Optional[dict]:
        """Return session data as a JSON-serialisable dict (for cloud upload)."""
        session = self.get_session(session_id)
        if session is None:
            return None
        return session.to_dict()
