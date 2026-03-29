"""Simple cooperative task scheduler for AURA OS kernel."""

import threading
import time
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional


@dataclass
class Task:
    """Represents a schedulable unit of work.

    Attributes:
        id: Unique task identifier.
        name: Human-readable task name.
        func: Callable to execute.
        status: One of 'pending', 'running', 'done', 'error'.
        priority: Lower numbers run first.
        result: Return value after execution (None until run).
        error: Exception message if the task failed.
    """

    id: str
    name: str
    func: Callable
    status: str = "pending"
    priority: int = 5
    result: object = None
    error: Optional[str] = None


class Scheduler:
    """Cooperative task scheduler.

    Tasks are run in priority order (lower priority number = higher urgency).
    Each call to :meth:`run_once` executes one pending task.
    :meth:`run_all` executes all pending tasks sequentially.

    Thread-based execution is available via :meth:`run_in_thread`.
    """

    def __init__(self):
        self._tasks: Dict[str, Task] = {}
        self._lock = threading.Lock()
        self._counter = 0

    # ------------------------------------------------------------------
    # Task management
    # ------------------------------------------------------------------

    def add_task(self, name: str, func: Callable, priority: int = 5) -> str:
        """Register a new task and return its generated ID."""
        with self._lock:
            self._counter += 1
            task_id = f"task-{self._counter}"
            self._tasks[task_id] = Task(id=task_id, name=name, func=func, priority=priority)
        return task_id

    def get_status(self) -> List[Dict]:
        """Return a list of dicts describing all tasks."""
        with self._lock:
            return [
                {
                    "id": t.id,
                    "name": t.name,
                    "status": t.status,
                    "priority": t.priority,
                    "error": t.error,
                }
                for t in self._tasks.values()
            ]

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    def _pending_sorted(self) -> List[Task]:
        """Return pending tasks sorted by priority."""
        return sorted(
            (t for t in self._tasks.values() if t.status == "pending"),
            key=lambda t: t.priority,
        )

    def run_once(self) -> Optional[Task]:
        """Execute the highest-priority pending task.

        Returns the Task that was run, or None if no pending tasks exist.
        """
        with self._lock:
            pending = self._pending_sorted()
            if not pending:
                return None
            task = pending[0]
            task.status = "running"

        try:
            task.result = task.func()
            task.status = "done"
        except Exception as exc:  # noqa: BLE001
            task.status = "error"
            task.error = str(exc)
        return task

    def run_all(self):
        """Execute all pending tasks in priority order."""
        while True:
            task = self.run_once()
            if task is None:
                break

    def run_in_thread(self) -> threading.Thread:
        """Run all pending tasks in a background thread.

        Returns the :class:`threading.Thread` object (already started).
        """
        thread = threading.Thread(target=self.run_all, daemon=True)
        thread.start()
        return thread
