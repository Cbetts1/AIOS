"""Advanced task scheduler for AURA OS kernel.

Enhancements vs original:
- **Thread-pool execution**: configurable worker count for true parallelism
- **Task timeouts**: tasks that exceed their deadline are cancelled
- **Retry policy**: automatic retries with configurable count and delay
- **Delayed / deferred tasks**: run a task after N seconds
- **Task cancellation**: cancel a pending task before it starts
- **Metrics**: per-task timing (enqueued_at, started_at, finished_at)
"""

import threading
import time
import uuid
from concurrent.futures import Future, ThreadPoolExecutor, TimeoutError as _FutureTimeout
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional


@dataclass
class Task:
    """Represents a schedulable unit of work.

    Attributes:
        id: Unique task identifier (UUID).
        name: Human-readable task name.
        func: Callable to execute.
        status: One of 'pending', 'running', 'done', 'error', 'cancelled', 'timeout'.
        priority: Lower numbers run first (for sequential mode).
        result: Return value after execution (None until run).
        error: Exception message if the task failed.
        enqueued_at: Timestamp when the task was registered.
        started_at: Timestamp when execution began (None until started).
        finished_at: Timestamp when execution ended (None until finished).
        run_after: If set, do not start the task before this epoch timestamp.
        timeout: Maximum seconds the task may run (None = unlimited).
        max_retries: Number of additional attempts on error.
        retry_delay: Seconds to wait between retries.
    """

    id: str
    name: str
    func: Callable
    status: str = "pending"
    priority: int = 5
    result: object = None
    error: Optional[str] = None
    enqueued_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    finished_at: Optional[float] = None
    run_after: Optional[float] = None
    timeout: Optional[float] = None
    max_retries: int = 0
    retry_delay: float = 1.0
    _attempt: int = field(default=0, repr=False)
    _future: Optional[Future] = field(default=None, repr=False)
    _cancelled: bool = field(default=False, repr=False)


class Scheduler:
    """Advanced task scheduler with thread-pool and cooperative modes.

    **Thread-pool mode** (default via :meth:`submit`):
        Tasks run immediately in a pool of workers.  Up to *max_workers*
        tasks execute in parallel.  Timeouts are enforced.

    **Sequential / cooperative mode** (via :meth:`add_task` + :meth:`run_all`):
        Tasks run in priority order in the calling thread.  Useful for
        deterministic unit-testing.

    Example::

        sched = Scheduler(max_workers=4)

        # Fire-and-forget
        tid = sched.submit("fetch_data", lambda: fetch_url("https://example.com"),
                           timeout=10, max_retries=2)

        # Wait for result
        result = sched.wait(tid, timeout=30)

        # Deferred (run after 5 s)
        sched.submit("deferred", my_func, run_after=time.time() + 5)
    """

    def __init__(self, max_workers: int = 4):
        self._tasks: Dict[str, Task] = {}
        self._lock = threading.Lock()
        self._counter = 0
        self._pool = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="aura-task")

    # ------------------------------------------------------------------
    # Task management (sequential / legacy API)
    # ------------------------------------------------------------------

    def add_task(self, name: str, func: Callable, priority: int = 5,
                 timeout: Optional[float] = None,
                 max_retries: int = 0,
                 run_after: Optional[float] = None) -> str:
        """Register a task for later sequential execution.  Returns task ID."""
        task_id = str(uuid.uuid4())[:12]
        task = Task(
            id=task_id,
            name=name,
            func=func,
            priority=priority,
            timeout=timeout,
            max_retries=max_retries,
            run_after=run_after,
        )
        with self._lock:
            self._tasks[task_id] = task
        return task_id

    def cancel(self, task_id: str) -> bool:
        """Cancel a pending task.  Running tasks cannot be cancelled.

        Returns True if the task was found and marked cancelled.
        """
        with self._lock:
            task = self._tasks.get(task_id)
        if task is None:
            return False
        if task.status == "pending":
            task.status = "cancelled"
            task._cancelled = True
            return True
        # For pool futures: try to cancel the future
        if task._future is not None:
            cancelled = task._future.cancel()
            if cancelled:
                task.status = "cancelled"
                task._cancelled = True
            return cancelled
        return False

    def get_status(self) -> List[Dict]:
        """Return a list of dicts describing all tasks."""
        with self._lock:
            tasks = list(self._tasks.values())
        return [
            {
                "id": t.id,
                "name": t.name,
                "status": t.status,
                "priority": t.priority,
                "error": t.error,
                "enqueued_at": t.enqueued_at,
                "started_at": t.started_at,
                "finished_at": t.finished_at,
                "duration_s": (
                    round(t.finished_at - t.started_at, 3)
                    if t.started_at and t.finished_at
                    else None
                ),
            }
            for t in tasks
        ]

    # ------------------------------------------------------------------
    # Thread-pool submission (preferred for real workloads)
    # ------------------------------------------------------------------

    def submit(
        self,
        name: str,
        func: Callable,
        priority: int = 5,
        timeout: Optional[float] = None,
        max_retries: int = 0,
        retry_delay: float = 1.0,
        run_after: Optional[float] = None,
    ) -> str:
        """Submit *func* to the thread pool and return its task ID.

        The task begins executing immediately (subject to worker availability
        and *run_after* delay).
        """
        task_id = str(uuid.uuid4())[:12]
        task = Task(
            id=task_id,
            name=name,
            func=func,
            priority=priority,
            timeout=timeout,
            max_retries=max_retries,
            retry_delay=retry_delay,
            run_after=run_after,
        )
        with self._lock:
            self._tasks[task_id] = task

        future = self._pool.submit(self._run_task, task)
        task._future = future
        return task_id

    def wait(self, task_id: str, timeout: float = None) -> object:
        """Block until the task with *task_id* completes and return its result.

        Raises :class:`TimeoutError` if *timeout* seconds elapse.
        Raises :class:`RuntimeError` if the task errored.
        Raises :class:`KeyError` if *task_id* is unknown.
        """
        with self._lock:
            task = self._tasks.get(task_id)
        if task is None:
            raise KeyError(f"Unknown task ID: {task_id}")
        if task._future is None:
            # Sequential task — poll
            deadline = time.time() + timeout if timeout else None
            while task.status in ("pending", "running"):
                if deadline and time.time() > deadline:
                    raise TimeoutError(f"Task {task_id} did not finish in time")
                time.sleep(0.05)
        else:
            try:
                task._future.result(timeout=timeout)
            except _FutureTimeout as exc:
                raise TimeoutError(f"Task {task_id} did not finish in time") from exc
        if task.status == "error":
            raise RuntimeError(task.error)
        return task.result

    # ------------------------------------------------------------------
    # Sequential execution (legacy / cooperative)
    # ------------------------------------------------------------------

    def _pending_sorted(self) -> List[Task]:
        now = time.time()
        return sorted(
            (
                t for t in self._tasks.values()
                if t.status == "pending"
                and (t.run_after is None or now >= t.run_after)
                and not t._cancelled
            ),
            key=lambda t: t.priority,
        )

    def run_once(self) -> Optional[Task]:
        """Execute the highest-priority ready pending task sequentially.

        Returns the Task that was run, or None if no ready tasks exist.
        """
        with self._lock:
            pending = self._pending_sorted()
            if not pending:
                return None
            task = pending[0]
            task.status = "running"
            task.started_at = time.time()

        self._execute_with_retry(task)
        return task

    def run_all(self):
        """Execute all ready pending tasks sequentially in priority order."""
        while True:
            task = self.run_once()
            if task is None:
                break

    def run_in_thread(self) -> threading.Thread:
        """Run all pending tasks sequentially in a background thread.

        Returns the :class:`threading.Thread` object (already started).
        """
        thread = threading.Thread(target=self.run_all, daemon=True)
        thread.start()
        return thread

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _run_task(self, task: Task):
        """Thread-pool worker entry point."""
        # Honor run_after delay
        if task.run_after:
            delay = task.run_after - time.time()
            if delay > 0:
                time.sleep(delay)

        if task._cancelled:
            return

        task.status = "running"
        task.started_at = time.time()
        self._execute_with_retry(task)

    def _execute_with_retry(self, task: Task):
        """Execute *task*, retrying on error up to task.max_retries times."""
        for attempt in range(task.max_retries + 1):
            if task._cancelled:
                task.status = "cancelled"
                task.finished_at = time.time()
                return
            try:
                if task.timeout is not None:
                    result = self._run_with_timeout(task.func, task.timeout)
                else:
                    result = task.func()
                task.result = result
                task.status = "done"
                task.finished_at = time.time()
                return
            except TimeoutError as exc:
                task.error = str(exc)
                task.status = "timeout"
                task.finished_at = time.time()
                return
            except Exception as exc:  # noqa: BLE001
                task.error = str(exc)
                task._attempt = attempt + 1
                if attempt < task.max_retries:
                    time.sleep(task.retry_delay * (2 ** attempt))
                else:
                    task.status = "error"
                    task.finished_at = time.time()

    @staticmethod
    def _run_with_timeout(func: Callable, timeout: float) -> object:
        """Run *func* in a thread and raise TimeoutError if it exceeds *timeout* s."""
        result_holder: List = [None]
        exc_holder: List = [None]

        def _target():
            try:
                result_holder[0] = func()
            except Exception as e:  # noqa: BLE001
                exc_holder[0] = e

        t = threading.Thread(target=_target, daemon=True)
        t.start()
        t.join(timeout)
        if t.is_alive():
            raise TimeoutError(f"Task exceeded {timeout}s timeout")
        if exc_holder[0] is not None:
            raise exc_holder[0]
        return result_holder[0]

    def shutdown(self, wait: bool = True):
        """Shut down the thread pool.  Call when the scheduler is no longer needed."""
        self._pool.shutdown(wait=wait)
