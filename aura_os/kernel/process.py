"""Process manager for AURA OS kernel.

Provides a process table that tracks spawned subprocesses with PIDs,
status, and metadata — similar to a real OS process table.
"""

import os
import signal
import subprocess
import threading
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class ProcessEntry:
    """Represents a tracked process in the AURA process table.

    Attributes:
        pid: Real OS process ID.
        name: Human-readable name or command string.
        status: One of 'running', 'stopped', 'zombie', 'exited'.
        exit_code: Return code after termination (None while running).
        started_at: Unix timestamp when the process was spawned.
        ppid: Parent PID (the AURA OS process itself).
        command: Full command list used to spawn the process.
    """

    pid: int
    name: str
    status: str = "running"
    exit_code: Optional[int] = None
    started_at: float = 0.0
    ppid: int = 0
    command: list = field(default_factory=list)
    _popen: Optional[subprocess.Popen] = field(default=None, repr=False)


class ProcessManager:
    """Manages a process table of spawned child processes.

    Tracks processes by their real OS PID.  Supports spawning foreground
    and background processes, listing, and sending signals.
    """

    def __init__(self):
        self._table: Dict[int, ProcessEntry] = {}
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Spawn
    # ------------------------------------------------------------------

    def spawn(self, cmd: list, name: str = None, background: bool = False) -> ProcessEntry:
        """Spawn a new process from *cmd*.

        If *background* is True the process runs detached and the call
        returns immediately.  Otherwise the call blocks until the child
        exits.

        Returns the :class:`ProcessEntry` for the new process.
        """
        display_name = name or (cmd[0] if cmd else "unknown")

        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE if background else None,
            stderr=subprocess.PIPE if background else None,
        )

        entry = ProcessEntry(
            pid=proc.pid,
            name=display_name,
            status="running",
            started_at=time.time(),
            ppid=os.getpid(),
            command=list(cmd),
            _popen=proc,
        )

        with self._lock:
            self._table[proc.pid] = entry

        if not background:
            proc.wait()
            entry.exit_code = proc.returncode
            entry.status = "exited"

        return entry

    # ------------------------------------------------------------------
    # Listing
    # ------------------------------------------------------------------

    def list_processes(self) -> List[Dict]:
        """Return a snapshot of all tracked processes.

        Automatically reaps finished processes before returning.
        """
        self._reap()
        with self._lock:
            return [
                {
                    "pid": e.pid,
                    "ppid": e.ppid,
                    "name": e.name,
                    "status": e.status,
                    "exit_code": e.exit_code,
                    "started_at": e.started_at,
                    "elapsed": round(time.time() - e.started_at, 1),
                    "command": " ".join(e.command),
                }
                for e in self._table.values()
            ]

    def get_process(self, pid: int) -> Optional[ProcessEntry]:
        """Return the entry for *pid*, or None."""
        with self._lock:
            return self._table.get(pid)

    # ------------------------------------------------------------------
    # Signals / kill
    # ------------------------------------------------------------------

    def send_signal(self, pid: int, sig: int = signal.SIGTERM) -> bool:
        """Send signal *sig* to the process identified by *pid*.

        Returns True if the signal was sent, False if the PID is unknown
        or the process has already exited.
        """
        with self._lock:
            entry = self._table.get(pid)

        if entry is None:
            return False

        if entry.status != "running":
            return False

        try:
            os.kill(pid, sig)
            if sig in (signal.SIGTERM, signal.SIGKILL):
                entry.status = "exited"
                if entry._popen is not None:
                    entry._popen.wait(timeout=5)
                    entry.exit_code = entry._popen.returncode
            return True
        except (ProcessLookupError, PermissionError):
            entry.status = "exited"
            return False

    def kill(self, pid: int) -> bool:
        """Send SIGKILL to *pid*."""
        return self.send_signal(pid, signal.SIGKILL)

    def terminate(self, pid: int) -> bool:
        """Send SIGTERM to *pid*."""
        return self.send_signal(pid, signal.SIGTERM)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _reap(self):
        """Update status of processes that have exited."""
        with self._lock:
            for entry in self._table.values():
                if entry.status == "running" and entry._popen is not None:
                    retcode = entry._popen.poll()
                    if retcode is not None:
                        entry.status = "exited"
                        entry.exit_code = retcode

    def cleanup(self):
        """Remove all exited process entries from the table."""
        self._reap()
        with self._lock:
            to_remove = [
                pid for pid, e in self._table.items() if e.status == "exited"
            ]
            for pid in to_remove:
                del self._table[pid]
