"""Event bus and notification subsystem for AURA OS.

Provides:
- Publish / subscribe event bus (in-process)
- Persistent notification queue (file-backed)
- System event hooks (startup, shutdown, error, etc.)
"""

import json
import os
import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional


# ------------------------------------------------------------------
# Event bus (in-process pub/sub)
# ------------------------------------------------------------------

@dataclass
class Event:
    """Represents a single event."""
    topic: str
    data: dict
    ts: float = field(default_factory=time.time)
    source: str = "system"


class EventBus:
    """Thread-safe publish/subscribe event bus.

    Subscribers register a callback for a topic pattern.
    Publishing an event invokes all matching callbacks synchronously
    (or in a background thread with ``emit_async``).
    """

    def __init__(self):
        self._subscribers: Dict[str, List[Callable]] = defaultdict(list)
        self._lock = threading.Lock()
        self._history: List[Event] = []
        self._max_history = 500

    # ------------------------------------------------------------------
    # Subscribe / unsubscribe
    # ------------------------------------------------------------------

    def subscribe(self, topic: str, callback: Callable):
        """Register *callback* for events matching *topic*.

        ``topic`` can be exact (``"fs.write"``) or a wildcard prefix
        (``"fs.*"``).  The callback receives one :class:`Event` argument.
        """
        with self._lock:
            self._subscribers[topic].append(callback)

    def unsubscribe(self, topic: str, callback: Callable):
        """Remove *callback* from *topic*."""
        with self._lock:
            cbs = self._subscribers.get(topic, [])
            if callback in cbs:
                cbs.remove(callback)

    # ------------------------------------------------------------------
    # Publish
    # ------------------------------------------------------------------

    def emit(self, topic: str, data: dict = None, source: str = "system"):
        """Publish an event and invoke subscribers synchronously."""
        event = Event(topic=topic, data=data or {}, source=source)
        with self._lock:
            self._history.append(event)
            if len(self._history) > self._max_history:
                self._history = self._history[-self._max_history:]
        self._dispatch(event)

    def emit_async(self, topic: str, data: dict = None,
                   source: str = "system"):
        """Publish an event and invoke subscribers in a background thread."""
        event = Event(topic=topic, data=data or {}, source=source)
        with self._lock:
            self._history.append(event)
            if len(self._history) > self._max_history:
                self._history = self._history[-self._max_history:]
        t = threading.Thread(target=self._dispatch, args=(event,),
                             daemon=True)
        t.start()

    def _dispatch(self, event: Event):
        """Invoke all subscribers whose topic matches *event.topic*."""
        with self._lock:
            callbacks = []
            for pattern, cbs in self._subscribers.items():
                if self._match(pattern, event.topic):
                    callbacks.extend(cbs)
        for cb in callbacks:
            try:
                cb(event)
            except Exception:
                pass  # subscriber errors must not crash the bus

    @staticmethod
    def _match(pattern: str, topic: str) -> bool:
        """Return True if *pattern* matches *topic*.

        Supports exact match and ``prefix.*`` wildcard.
        """
        if pattern == topic:
            return True
        if pattern.endswith(".*"):
            prefix = pattern[:-2]
            return topic == prefix or topic.startswith(prefix + ".")
        return False

    # ------------------------------------------------------------------
    # History
    # ------------------------------------------------------------------

    def history(self, topic: Optional[str] = None,
                limit: int = 50) -> List[Dict]:
        """Return recent events, optionally filtered by *topic*."""
        with self._lock:
            items = list(self._history)
        if topic:
            items = [e for e in items if self._match(topic, e.topic)]
        items = items[-limit:]
        return [{"topic": e.topic, "data": e.data, "ts": e.ts,
                 "source": e.source} for e in items]


# ------------------------------------------------------------------
# Persistent notification queue
# ------------------------------------------------------------------

class NotificationManager:
    """File-backed notification queue stored under ``~/.aura/notifications/``.

    Notifications are JSON objects with ``id``, ``title``, ``body``,
    ``level`` (info / warn / error / success), and ``read`` flag.
    """

    def __init__(self, base_dir: str = None):
        aura_home = os.environ.get("AURA_HOME",
                                   os.path.expanduser("~/.aura"))
        self._dir = base_dir or os.path.join(aura_home, "notifications")
        os.makedirs(self._dir, exist_ok=True)
        self._lock = threading.Lock()
        self._counter = 0

    def _store_path(self) -> str:
        return os.path.join(self._dir, "queue.json")

    def _load(self) -> List[Dict]:
        path = self._store_path()
        if not os.path.isfile(path):
            return []
        with open(path, "r", encoding="utf-8") as fh:
            try:
                return json.load(fh)
            except json.JSONDecodeError:
                return []

    def _save(self, items: List[Dict]):
        path = self._store_path()
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(items, fh, indent=2)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def send(self, title: str, body: str = "",
             level: str = "info") -> Dict:
        """Create a new notification and return it."""
        with self._lock:
            items = self._load()
            self._counter += 1
            nid = f"notif-{int(time.time())}-{self._counter}"
            notif = {
                "id": nid,
                "title": title,
                "body": body,
                "level": level,
                "read": False,
                "ts": time.time(),
            }
            items.append(notif)
            self._save(items)
        return notif

    def list_all(self, unread_only: bool = False) -> List[Dict]:
        """Return notifications, optionally only unread ones."""
        with self._lock:
            items = self._load()
        if unread_only:
            items = [n for n in items if not n.get("read")]
        return items

    def mark_read(self, notif_id: str) -> bool:
        """Mark a notification as read.  Returns True on success."""
        with self._lock:
            items = self._load()
            for n in items:
                if n["id"] == notif_id:
                    n["read"] = True
                    self._save(items)
                    return True
        return False

    def clear(self):
        """Delete all notifications."""
        with self._lock:
            self._save([])

    def unread_count(self) -> int:
        """Return count of unread notifications."""
        return len(self.list_all(unread_only=True))
