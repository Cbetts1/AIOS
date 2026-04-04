"""Process manager for AURA OS kernel.

Provides a process table that tracks spawned subprocesses with PIDs,
status, and metadata — similar to a real OS process table.

Enhancements vs original:
- **System-wide listing** via psutil (``list_system_processes``)
- **CPU / memory usage** per tracked process
- **Process-tree walk**: children of a given PID
- **Resource limits**: optional soft CPU-time / memory caps enforced by a
  background watchdog thread
- **Graceful shutdown**: ``terminate_all`` sends SIGTERM then SIGKILL after
  a configurable grace period
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
        cpu_limit: Max CPU seconds (soft limit).  None = unlimited.
        mem_limit_mb: Max resident memory in MiB.  None = unlimited.
    """

    pid: int
    name: str
    status: str = "running"
    exit_code: Optional[int] = None
    started_at: float = 0.0
    ppid: int = 0
    command: list = field(default_factory=list)
    cpu_limit: Optional[float] = None
    mem_limit_mb: Optional[float] = None
    _popen: Optional[subprocess.Popen] = field(default=None, repr=False)


def _get_psutil():
    """Return the psutil module or None if not installed."""
    try:
        import psutil  # noqa: F401
        return psutil
    except ImportError:
        return None


class ProcessManager:
    """Manages a process table of spawned child processes.

    Tracks processes by their real OS PID.  Supports spawning foreground
    and background processes, listing, and sending signals.

    Optional resource watchdog (started via :meth:`start_watchdog`) polls
    each tracked process for CPU-time and RSS violations every 5 seconds
    and terminates offenders.
    """

    def __init__(self):
        self._table: Dict[int, ProcessEntry] = {}
        self._lock = threading.Lock()
        self._watchdog_thread: Optional[threading.Thread] = None
        self._watchdog_stop = threading.Event()

    # ------------------------------------------------------------------
    # Spawn
    # ------------------------------------------------------------------

    def spawn(
        self,
        cmd: list,
        name: str = None,
        background: bool = False,
        cpu_limit: Optional[float] = None,
        mem_limit_mb: Optional[float] = None,
    ) -> ProcessEntry:
        """Spawn a new process from *cmd*.

        If *background* is True the process runs detached and the call
        returns immediately.  Otherwise the call blocks until the child exits.

        Args:
            cmd: Command and arguments list.
            name: Human-readable name (defaults to cmd[0]).
            background: Run without blocking if True.
            cpu_limit: Soft CPU-time limit in seconds.  Requires watchdog.
            mem_limit_mb: Soft RSS limit in MiB.  Requires watchdog.

        Returns:
            The :class:`ProcessEntry` for the new process.
        """
        display_name = name or (cmd[0] if cmd else "unknown")

        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL if background else None,
            stderr=subprocess.DEVNULL if background else None,
        )

        entry = ProcessEntry(
            pid=proc.pid,
            name=display_name,
            status="running",
            started_at=time.time(),
            ppid=os.getpid(),
            command=list(cmd),
            cpu_limit=cpu_limit,
            mem_limit_mb=mem_limit_mb,
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
    # Listing — AURA-tracked processes
    # ------------------------------------------------------------------

    def list_processes(self) -> List[Dict]:
        """Return a snapshot of all AURA-tracked processes (with resource stats)."""
        self._reap()
        psutil = _get_psutil()
        with self._lock:
            result = []
            for e in self._table.values():
                row = {
                    "pid": e.pid,
                    "ppid": e.ppid,
                    "name": e.name,
                    "status": e.status,
                    "exit_code": e.exit_code,
                    "started_at": e.started_at,
                    "elapsed": round(time.time() - e.started_at, 1),
                    "command": " ".join(e.command),
                    "cpu_pct": None,
                    "mem_rss_mb": None,
                }
                if psutil and e.status == "running":
                    try:
                        p = psutil.Process(e.pid)
                        row["cpu_pct"] = p.cpu_percent(interval=0)
                        row["mem_rss_mb"] = round(
                            p.memory_info().rss / (1024 * 1024), 2
                        )
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass
                result.append(row)
        return result

    # ------------------------------------------------------------------
    # Listing — system-wide (requires psutil)
    # ------------------------------------------------------------------

    def list_system_processes(
        self,
        sort_by: str = "cpu",
        limit: int = 50,
    ) -> List[Dict]:
        """Return a snapshot of *all* running system processes.

        Requires ``psutil``.  Returns an empty list if not installed.

        Args:
            sort_by: Sort field — ``"cpu"`` (default), ``"mem"``, ``"pid"``,
                     or ``"name"``.
            limit: Maximum number of entries to return.

        Each dict contains:
            pid, ppid, name, status, cpu_pct, mem_rss_mb, num_threads,
            username, cmdline, create_time.
        """
        psutil = _get_psutil()
        if psutil is None:
            return []

        procs = []
        for p in psutil.process_iter(
            ["pid", "ppid", "name", "status", "cpu_percent",
             "memory_info", "num_threads", "username", "cmdline", "create_time"]
        ):
            try:
                info = p.info
                mem = info.get("memory_info")
                procs.append({
                    "pid": info["pid"],
                    "ppid": info.get("ppid", 0),
                    "name": info.get("name", ""),
                    "status": info.get("status", ""),
                    "cpu_pct": info.get("cpu_percent", 0.0),
                    "mem_rss_mb": round(mem.rss / (1024 * 1024), 2) if mem else 0.0,
                    "num_threads": info.get("num_threads", 0),
                    "username": info.get("username", ""),
                    "cmdline": " ".join(info.get("cmdline") or [])[:120],
                    "create_time": info.get("create_time", 0.0),
                })
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass

        _sort_keys = {
            "cpu": lambda r: r["cpu_pct"],
            "mem": lambda r: r["mem_rss_mb"],
            "pid": lambda r: r["pid"],
            "name": lambda r: (r["name"] or "").lower(),
        }
        key_fn = _sort_keys.get(sort_by, _sort_keys["cpu"])
        procs.sort(key=key_fn, reverse=(sort_by in ("cpu", "mem")))
        return procs[:limit]

    def get_process_tree(self, pid: int) -> Dict:
        """Return a dict representing the process subtree rooted at *pid*.

        Requires ``psutil``.  Returns ``{}`` if pid is not found or psutil
        is unavailable.
        """
        psutil = _get_psutil()
        if psutil is None:
            return {}
        try:
            p = psutil.Process(pid)

            def _node(proc):
                try:
                    return {
                        "pid": proc.pid,
                        "name": proc.name(),
                        "status": proc.status(),
                        "children": [_node(c) for c in proc.children()],
                    }
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    return {"pid": proc.pid, "name": "?", "status": "gone", "children": []}

            return _node(p)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return {}

    def get_process(self, pid: int) -> Optional[ProcessEntry]:
        """Return the AURA-tracked entry for *pid*, or None."""
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

    def terminate_all(self, grace_period: float = 5.0):
        """Send SIGTERM to all running tracked processes, then SIGKILL after
        *grace_period* seconds for those that haven't exited yet."""
        with self._lock:
            running = [
                e for e in self._table.values() if e.status == "running"
            ]
        for entry in running:
            try:
                os.kill(entry.pid, signal.SIGTERM)
            except OSError:
                pass
        time.sleep(grace_period)
        for entry in running:
            if entry.status == "running":
                try:
                    os.kill(entry.pid, signal.SIGKILL)
                except OSError:
                    pass

    # ------------------------------------------------------------------
    # Resource watchdog
    # ------------------------------------------------------------------

    def start_watchdog(self, interval: float = 5.0):
        """Start a background thread that enforces cpu_limit / mem_limit_mb."""
        if self._watchdog_thread and self._watchdog_thread.is_alive():
            return
        self._watchdog_stop.clear()
        self._watchdog_thread = threading.Thread(
            target=self._watchdog_loop,
            args=(interval,),
            daemon=True,
            name="aura-watchdog",
        )
        self._watchdog_thread.start()

    def stop_watchdog(self):
        """Stop the background resource watchdog."""
        self._watchdog_stop.set()

    def _watchdog_loop(self, interval: float):
        psutil = _get_psutil()
        while not self._watchdog_stop.wait(interval):
            if psutil is None:
                continue
            with self._lock:
                entries = list(self._table.values())
            for entry in entries:
                if entry.status != "running":
                    continue
                try:
                    p = psutil.Process(entry.pid)
                    if entry.mem_limit_mb is not None:
                        rss_mb = p.memory_info().rss / (1024 * 1024)
                        if rss_mb > entry.mem_limit_mb:
                            self.terminate(entry.pid)
                            continue
                    if entry.cpu_limit is not None:
                        cpu_times = p.cpu_times()
                        total = cpu_times.user + cpu_times.system
                        if total > entry.cpu_limit:
                            self.terminate(entry.pid)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass

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
