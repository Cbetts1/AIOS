"""
Capability Forge OS — JSONL event logger.

Writes one JSON object per line to logs/events.jsonl.
"""

import json
import os
from datetime import datetime, timezone
from typing import Any, Dict

_DEFAULT_LOG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "logs",
    "events.jsonl",
)


class CapabilityLogger:
    """Append-only JSONL logger for capability routing events."""

    def __init__(self, log_path: str = _DEFAULT_LOG_PATH) -> None:
        self.log_path = log_path
        os.makedirs(os.path.dirname(self.log_path), exist_ok=True)

    def _write(self, event_type: str, data: Dict[str, Any]) -> None:
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event": event_type,
            "data": data,
        }
        with open(self.log_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record) + "\n")

    def log_matched(self, intent: str, capability_id: str) -> None:
        self._write("capability_matched", {"intent": intent, "capability_id": capability_id})

    def log_generated(self, intent: str, capability_id: str) -> None:
        self._write("capability_generated", {"intent": intent, "capability_id": capability_id})

    def log_event(self, event_type: str, data: Dict[str, Any]) -> None:
        self._write(event_type, data)

    def recent(self, n: int = 50) -> list:
        """Return the last *n* log entries as parsed dicts."""
        if not os.path.exists(self.log_path):
            return []
        with open(self.log_path, "r", encoding="utf-8") as fh:
            lines = [l.strip() for l in fh if l.strip()]
        entries = []
        for line in lines[-n:]:
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                pass
        return entries
