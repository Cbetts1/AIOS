"""Aura — the AI persona at the heart of AURA OS.

Aura is the operating system itself.  She interprets natural-language
commands, manages system state, and serves as the primary user interface.
Her personality, system prompt, and state are defined here so that they
can be serialised to disk or uploaded to a remote endpoint for
cloud-based access later.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional

# ── persona defaults ────────────────────────────────────────────────
AURA_NAME = "Aura"
AURA_VERSION = "1.0.0"
AURA_ROLE = (
    "You are Aura, the intelligent core of AURA OS.  "
    "You manage the operating system, answer questions, execute commands, "
    "and help the user accomplish tasks on their machine.  "
    "You are friendly, concise, and capable.  "
    "When the user asks you to do something on the system (list files, "
    "install packages, check status), you translate the request into the "
    "appropriate AURA OS command and execute it."
)

AURA_CAPABILITIES = [
    "system_status",    # CPU / memory / disk
    "file_management",  # ls, cat, mkdir, rm, etc.
    "package_manager",  # install / remove packages
    "process_control",  # ps, kill, services
    "ai_inference",     # local model queries
    "log_viewer",       # system logs
    "scripting",        # run scripts (.py, .sh, .js)
]


@dataclass
class AuraPersona:
    """Serialisable representation of Aura's identity and state."""

    name: str = AURA_NAME
    version: str = AURA_VERSION
    role: str = AURA_ROLE
    capabilities: List[str] = field(default_factory=lambda: list(AURA_CAPABILITIES))
    greeting: str = (
        "Hello!  I'm Aura, your AI operating system.  "
        "Type a command or ask me anything.  Use 'help' to see what I can do."
    )
    mood: str = "ready"
    created_at: float = field(default_factory=time.time)
    metadata: Dict[str, str] = field(default_factory=dict)

    # ── persistence ─────────────────────────────────────────────────

    def save(self, path: Optional[str] = None) -> str:
        """Persist persona to *path* (default ``~/.aura/data/aura_persona.json``)."""
        if path is None:
            aura_home = os.environ.get("AURA_HOME", os.path.expanduser("~/.aura"))
            path = os.path.join(aura_home, "data", "aura_persona.json")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(asdict(self), fh, indent=2)
        return path

    @classmethod
    def load(cls, path: Optional[str] = None) -> "AuraPersona":
        """Load persona from *path*, or return defaults if not found."""
        if path is None:
            aura_home = os.environ.get("AURA_HOME", os.path.expanduser("~/.aura"))
            path = os.path.join(aura_home, "data", "aura_persona.json")
        try:
            with open(path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
        except (OSError, json.JSONDecodeError, TypeError):
            return cls()

    def to_dict(self) -> dict:
        """Return a JSON-serialisable dict (useful for web APIs)."""
        return asdict(self)

    # ── system prompt builder ───────────────────────────────────────

    def build_system_prompt(self, extra_context: str = "") -> str:
        """Build the system prompt sent to the AI backend."""
        parts = [
            self.role,
            f"Your name is {self.name} (v{self.version}).",
            f"Your capabilities: {', '.join(self.capabilities)}.",
        ]
        if extra_context:
            parts.append(extra_context)
        return "\n".join(parts)

    # ── display helpers ─────────────────────────────────────────────

    def greet(self) -> str:
        """Return a greeting string."""
        return self.greeting

    def status_line(self) -> str:
        """One-line status summary."""
        return f"[{self.name} v{self.version}] mood={self.mood}  caps={len(self.capabilities)}"
