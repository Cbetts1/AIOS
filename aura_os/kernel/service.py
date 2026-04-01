"""Service / daemon manager for AURA OS kernel.

Provides start / stop / restart / status / enable / disable of
long-running background services — conceptually similar to systemd or
init.d on a real Linux system.

Services are defined by JSON manifest files stored under
``~/.aura/services/``.
"""

import json
import os
import subprocess
import threading
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class ServiceEntry:
    """Runtime state of a managed service.

    Attributes:
        name: Unique service name.
        command: Shell command to start the service.
        description: Human-readable description.
        enabled: Whether the service should start automatically on boot.
        status: One of 'stopped', 'running', 'failed'.
        pid: Real OS PID while running (None otherwise).
        restarts: Number of times the service has been restarted.
        started_at: Unix timestamp of the last start.
    """

    name: str
    command: str
    description: str = ""
    enabled: bool = False
    status: str = "stopped"
    pid: Optional[int] = None
    restarts: int = 0
    started_at: float = 0.0
    _popen: Optional[subprocess.Popen] = field(default=None, repr=False)
    _log_fh: object = field(default=None, repr=False)


class ServiceManager:
    """Manages long-running background services for AURA OS.

    Service manifests are stored as JSON files under
    ``<aura_home>/services/<name>.json``:

    .. code-block:: json

        {
            "name": "my-service",
            "command": "python3 -m http.server 9000",
            "description": "Simple HTTP file server",
            "enabled": true
        }
    """

    def __init__(self, services_dir: str = None):
        aura_home = os.environ.get("AURA_HOME", os.path.expanduser("~/.aura"))
        self._dir = services_dir or os.path.join(aura_home, "services")
        os.makedirs(self._dir, exist_ok=True)
        self._services: Dict[str, ServiceEntry] = {}
        self._lock = threading.Lock()
        self._load_manifests()

    # ------------------------------------------------------------------
    # Manifest I/O
    # ------------------------------------------------------------------

    def _manifest_path(self, name: str) -> str:
        safe = os.path.basename(name)
        if not safe or safe in (".", ".."):
            raise ValueError(f"Invalid service name: {name!r}")
        return os.path.join(self._dir, f"{safe}.json")

    def _load_manifests(self):
        """Load all service manifests from disk into memory."""
        for fname in os.listdir(self._dir):
            if not fname.endswith(".json"):
                continue
            path = os.path.join(self._dir, fname)
            try:
                with open(path, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
                name = data.get("name", fname[:-5])
                self._services[name] = ServiceEntry(
                    name=name,
                    command=data.get("command", ""),
                    description=data.get("description", ""),
                    enabled=data.get("enabled", False),
                )
            except (json.JSONDecodeError, OSError):
                pass

    def _save_manifest(self, entry: ServiceEntry):
        """Persist a service manifest to disk."""
        path = self._manifest_path(entry.name)
        data = {
            "name": entry.name,
            "command": entry.command,
            "description": entry.description,
            "enabled": entry.enabled,
        }
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def create(self, name: str, command: str, description: str = "", enabled: bool = False):
        """Create a new service definition.

        If a service with this name already exists it is updated.
        """
        with self._lock:
            entry = self._services.get(name)
            if entry is None:
                entry = ServiceEntry(name=name, command=command, description=description, enabled=enabled)
                self._services[name] = entry
            else:
                entry.command = command
                entry.description = description
                entry.enabled = enabled
            self._save_manifest(entry)

    def start(self, name: str) -> bool:
        """Start the service named *name*.

        Returns True on success, False if the service is unknown or
        already running.
        """
        with self._lock:
            entry = self._services.get(name)

        if entry is None:
            return False

        if entry.status == "running" and entry._popen is not None:
            if entry._popen.poll() is None:
                return True  # already running

        try:
            import shlex
            cmd_list = shlex.split(entry.command)
            log_dir = os.path.join(os.path.dirname(self._dir), "logs")
            os.makedirs(log_dir, exist_ok=True)
            log_path = os.path.join(log_dir, f"svc_{name}.log")
            log_fh = open(log_path, "a", encoding="utf-8")  # noqa: SIM115
            try:
                proc = subprocess.Popen(
                    cmd_list,
                    stdout=log_fh,
                    stderr=log_fh,
                    start_new_session=True,
                )
            except Exception:
                log_fh.close()
                raise
            entry._popen = proc
            entry._log_fh = log_fh
            entry.pid = proc.pid
            entry.status = "running"
            entry.started_at = time.time()
            return True
        except (OSError, ValueError):
            entry.status = "failed"
            return False

    def stop(self, name: str) -> bool:
        """Stop the service named *name*.

        Sends SIGTERM first, then SIGKILL after a short grace period.
        Returns True on success, False if unknown or already stopped.
        """
        with self._lock:
            entry = self._services.get(name)

        if entry is None or entry.status != "running":
            return False

        if entry._popen is not None:
            try:
                entry._popen.terminate()
                try:
                    entry._popen.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    entry._popen.kill()
                    entry._popen.wait(timeout=2)
            except (OSError, ProcessLookupError):
                pass
            entry._popen = None

        if entry._log_fh is not None:
            try:
                entry._log_fh.close()
            except OSError:
                pass
            entry._log_fh = None

        entry.status = "stopped"
        entry.pid = None
        return True

    def restart(self, name: str) -> bool:
        """Stop then start the service.  Returns True on success."""
        self.stop(name)
        result = self.start(name)
        with self._lock:
            entry = self._services.get(name)
        if entry is not None:
            entry.restarts += 1
        return result

    def enable(self, name: str) -> bool:
        """Mark the service to auto-start on boot."""
        with self._lock:
            entry = self._services.get(name)
        if entry is None:
            return False
        entry.enabled = True
        self._save_manifest(entry)
        return True

    def disable(self, name: str) -> bool:
        """Remove auto-start for the service."""
        with self._lock:
            entry = self._services.get(name)
        if entry is None:
            return False
        entry.enabled = False
        self._save_manifest(entry)
        return True

    def status(self, name: str) -> Optional[Dict]:
        """Return a status dict for a single service."""
        self._refresh(name)
        with self._lock:
            entry = self._services.get(name)
        if entry is None:
            return None
        return self._entry_to_dict(entry)

    def list_services(self) -> List[Dict]:
        """Return status dicts for all known services."""
        self._refresh_all()
        with self._lock:
            return [self._entry_to_dict(e) for e in self._services.values()]

    def boot_start(self):
        """Start all enabled services — called during AURA OS init."""
        with self._lock:
            names = [e.name for e in self._services.values() if e.enabled]
        for name in names:
            self.start(name)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _entry_to_dict(entry: ServiceEntry) -> Dict:
        elapsed = 0.0
        if entry.status == "running" and entry.started_at:
            elapsed = round(time.time() - entry.started_at, 1)
        return {
            "name": entry.name,
            "status": entry.status,
            "pid": entry.pid,
            "enabled": entry.enabled,
            "description": entry.description,
            "restarts": entry.restarts,
            "elapsed": elapsed,
            "command": entry.command,
        }

    def _refresh(self, name: str):
        """Check if a running service has exited."""
        entry = self._services.get(name)
        if entry is None:
            return
        if entry.status == "running" and entry._popen is not None:
            if entry._popen.poll() is not None:
                entry.status = "stopped"
                entry.pid = None

    def _refresh_all(self):
        """Refresh status of every service."""
        with self._lock:
            names = list(self._services.keys())
        for name in names:
            self._refresh(name)
