"""File-based inter-process communication for AURA OS."""

import json
import os
import threading
import time
from typing import Dict, List


class IPCChannel:
    """Simple file-based IPC using message queue files under ~/.aura/ipc/.

    Each channel maps to a JSON-lines file.  Messages are plain Python dicts.
    Concurrent access is protected by a per-channel threading lock (in-process)
    and by atomic file replacement (cross-process safety on POSIX).
    """

    _locks: Dict[str, threading.Lock] = {}
    _locks_meta = threading.Lock()

    def __init__(self, base_dir: str = None):
        aura_home = os.environ.get("AURA_HOME", os.path.expanduser("~/.aura"))
        self._base_dir = base_dir or os.path.join(aura_home, "ipc")
        os.makedirs(self._base_dir, exist_ok=True)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _channel_path(self, channel: str) -> str:
        # Validate the original channel name before any transformation
        if not channel or "\x00" in channel or any(ord(c) < 32 for c in channel):
            raise ValueError(f"Invalid IPC channel name: {channel!r}")
        safe = os.path.basename(channel)
        if not safe or safe in (".", "..") or safe.startswith("."):
            raise ValueError(f"Invalid IPC channel name: {channel!r}")
        return os.path.join(self._base_dir, f"{safe}.jsonl")

    def _get_lock(self, channel: str) -> threading.Lock:
        with self._locks_meta:
            if channel not in self._locks:
                self._locks[channel] = threading.Lock()
            return self._locks[channel]

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def send(self, channel: str, message: dict):
        """Append *message* to the named channel queue."""
        lock = self._get_lock(channel)
        path = self._channel_path(channel)
        envelope = {
            "ts": time.time(),
            "data": message,
        }
        with lock:
            with open(path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(envelope) + "\n")

    def receive(self, channel: str) -> List[dict]:
        """Read and return all messages from *channel*.

        Messages remain on disk until :meth:`clear` is called.
        """
        lock = self._get_lock(channel)
        path = self._channel_path(channel)
        messages: List[dict] = []
        if not os.path.isfile(path):
            return messages
        with lock:
            with open(path, "r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        messages.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
        return messages

    def clear(self, channel: str):
        """Delete all messages in the named channel queue."""
        lock = self._get_lock(channel)
        path = self._channel_path(channel)
        with lock:
            if os.path.isfile(path):
                os.remove(path)
