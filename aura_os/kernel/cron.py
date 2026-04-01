"""Cron-like periodic task scheduler for AURA OS.

Extends the basic cooperative scheduler with time-based recurring tasks:
- Simple interval expressions (``every 5m``, ``every 1h``)
- Standard cron-style fields (``*/5 * * * *``)
- Persistent job definitions stored under ``~/.aura/cron/``
"""

import json
import os
import threading
import time
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional


@dataclass
class CronJob:
    """Represents a periodic task."""
    id: str
    name: str
    schedule: str          # cron expression or interval string
    command: str           # shell command to run
    enabled: bool = True
    last_run: Optional[float] = None
    next_run: Optional[float] = None
    run_count: int = 0
    last_error: Optional[str] = None


class CronScheduler:
    """File-backed cron scheduler with interval and cron-expression support.

    Jobs are persisted under ``~/.aura/cron/jobs.json`` so they survive
    restarts.  The scheduler tick loop runs in a daemon thread.
    """

    def __init__(self, base_dir: str = None):
        aura_home = os.environ.get("AURA_HOME",
                                   os.path.expanduser("~/.aura"))
        self._dir = base_dir or os.path.join(aura_home, "cron")
        os.makedirs(self._dir, exist_ok=True)
        self._jobs: Dict[str, CronJob] = {}
        self._lock = threading.Lock()
        self._counter = 0
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._executor: Optional[Callable] = None
        self._load()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _store_path(self) -> str:
        return os.path.join(self._dir, "jobs.json")

    def _load(self):
        path = self._store_path()
        if not os.path.isfile(path):
            return
        try:
            with open(path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            for item in data:
                job = CronJob(**item)
                self._jobs[job.id] = job
                self._counter = max(self._counter,
                                    int(job.id.split("-")[-1] or 0))
        except (json.JSONDecodeError, TypeError):
            pass

    def _save(self):
        path = self._store_path()
        data = []
        for job in self._jobs.values():
            data.append({
                "id": job.id, "name": job.name, "schedule": job.schedule,
                "command": job.command, "enabled": job.enabled,
                "last_run": job.last_run, "next_run": job.next_run,
                "run_count": job.run_count, "last_error": job.last_error,
            })
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)

    # ------------------------------------------------------------------
    # Job management
    # ------------------------------------------------------------------

    def add_job(self, name: str, schedule: str, command: str) -> CronJob:
        """Add a periodic job.

        *schedule* can be:
        - An interval string: ``every 30s``, ``every 5m``, ``every 2h``
        - A cron expression: ``*/5 * * * *`` (every 5 minutes)
        """
        with self._lock:
            self._counter += 1
            jid = f"cron-{self._counter}"
            job = CronJob(id=jid, name=name, schedule=schedule,
                          command=command)
            job.next_run = self._calc_next(job)
            self._jobs[jid] = job
            self._save()
        return job

    def remove_job(self, job_id: str) -> bool:
        """Remove a job by ID.  Returns True on success."""
        with self._lock:
            if job_id in self._jobs:
                del self._jobs[job_id]
                self._save()
                return True
        return False

    def enable_job(self, job_id: str) -> bool:
        """Enable a disabled job."""
        with self._lock:
            job = self._jobs.get(job_id)
            if job:
                job.enabled = True
                job.next_run = self._calc_next(job)
                self._save()
                return True
        return False

    def disable_job(self, job_id: str) -> bool:
        """Disable a job (it won't run until re-enabled)."""
        with self._lock:
            job = self._jobs.get(job_id)
            if job:
                job.enabled = False
                self._save()
                return True
        return False

    def list_jobs(self) -> List[Dict]:
        """Return all registered jobs."""
        with self._lock:
            return [
                {
                    "id": j.id, "name": j.name, "schedule": j.schedule,
                    "command": j.command, "enabled": j.enabled,
                    "last_run": j.last_run, "next_run": j.next_run,
                    "run_count": j.run_count, "last_error": j.last_error,
                }
                for j in self._jobs.values()
            ]

    # ------------------------------------------------------------------
    # Schedule parsing
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_interval(schedule: str) -> Optional[float]:
        """Parse ``every Ns/m/h/d`` into seconds, or return None."""
        schedule = schedule.strip().lower()
        if not schedule.startswith("every "):
            return None
        part = schedule[6:].strip()
        multipliers = {"s": 1, "m": 60, "h": 3600, "d": 86400}
        for suffix, mul in multipliers.items():
            if part.endswith(suffix):
                try:
                    return float(part[:-1]) * mul
                except ValueError:
                    return None
        # Bare number → seconds
        try:
            return float(part)
        except ValueError:
            return None

    def _calc_next(self, job: CronJob) -> float:
        """Calculate the next run timestamp for *job*."""
        interval = self._parse_interval(job.schedule)
        if interval is not None:
            base = job.last_run or time.time()
            return base + interval
        # Fall back to cron-style: parse minute field for simple cases
        return self._next_cron(job.schedule)

    @staticmethod
    def _next_cron(expr: str) -> float:
        """Simplified cron expression → next run timestamp.

        Supports ``*/N`` in the minute field, ``*`` for all others.
        Full cron parsing is out of scope for a lightweight OS.
        """
        parts = expr.strip().split()
        if len(parts) < 5:
            return time.time() + 60  # default: 1 minute
        minute_field = parts[0]
        now = time.localtime()
        if minute_field.startswith("*/"):
            try:
                every_n = int(minute_field[2:])
            except ValueError:
                every_n = 5
            current_min = now.tm_min
            next_min = ((current_min // every_n) + 1) * every_n
            delta = (next_min - current_min) * 60 - now.tm_sec
            if delta <= 0:
                delta += every_n * 60
            return time.time() + delta
        return time.time() + 60

    # ------------------------------------------------------------------
    # Tick loop
    # ------------------------------------------------------------------

    def set_executor(self, func: Callable):
        """Set the function that runs commands.

        ``func(command: str) -> str`` should execute a shell command and
        return its output (or raise on error).
        """
        self._executor = func

    def start(self):
        """Start the cron tick loop in a daemon thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        """Stop the cron tick loop."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
            self._thread = None

    def _loop(self):
        """Main scheduler loop — checks once per second."""
        while self._running:
            now = time.time()
            with self._lock:
                due = [j for j in self._jobs.values()
                       if j.enabled and j.next_run and j.next_run <= now]
            for job in due:
                self._run_job(job)
            time.sleep(1)

    def _run_job(self, job: CronJob):
        """Execute a single job and update its metadata."""
        import subprocess
        try:
            if self._executor:
                self._executor(job.command)
            else:
                subprocess.run(job.command, shell=True, capture_output=True,
                               timeout=300, check=False)
            job.last_error = None
        except Exception as exc:
            job.last_error = str(exc)
        job.last_run = time.time()
        job.run_count += 1
        job.next_run = self._calc_next(job)
        with self._lock:
            self._save()
