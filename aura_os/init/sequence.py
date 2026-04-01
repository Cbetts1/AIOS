"""Init/boot sequence manager for AURA OS."""

import logging
import threading
from typing import Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

_STATES = {"pending", "running", "failed", "skipped", "stopped"}


class _Unit:
    __slots__ = (
        "name", "description", "start_fn", "stop_fn",
        "after", "requires", "state", "error",
    )

    def __init__(
        self,
        name: str,
        start_fn: Callable,
        stop_fn: Optional[Callable],
        description: str,
        after: List[str],
        requires: List[str],
    ):
        self.name = name
        self.start_fn = start_fn
        self.stop_fn = stop_fn
        self.description = description
        self.after = after
        self.requires = requires
        self.state = "pending"
        self.error: Optional[str] = None


class InitManager:
    """Systemd-inspired ordered boot sequence manager."""

    def __init__(self):
        self._units: Dict[str, _Unit] = {}
        self._order: List[str] = []
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(
        self,
        name: str,
        start_fn: Callable,
        stop_fn: Optional[Callable] = None,
        description: str = "",
        after: Optional[List[str]] = None,
        requires: Optional[List[str]] = None,
    ) -> None:
        """Register a boot unit."""
        with self._lock:
            self._units[name] = _Unit(
                name=name,
                start_fn=start_fn,
                stop_fn=stop_fn,
                description=description,
                after=after or [],
                requires=requires or [],
            )

    # ------------------------------------------------------------------
    # Topological sort
    # ------------------------------------------------------------------

    def _topo_sort(self) -> List[str]:
        """Return unit names in dependency order."""
        visited: Dict[str, str] = {}
        order: List[str] = []

        def visit(name: str):
            if visited.get(name) == "done":
                return
            if visited.get(name) == "in_progress":
                logger.warning("Circular dependency detected at unit '%s'; skipping.", name)
                return
            visited[name] = "in_progress"
            unit = self._units.get(name)
            if unit:
                for dep in unit.after + unit.requires:
                    if dep in self._units:
                        visit(dep)
            visited[name] = "done"
            order.append(name)

        for n in self._units:
            visit(n)
        return order

    # ------------------------------------------------------------------
    # Boot / shutdown
    # ------------------------------------------------------------------

    def boot(self) -> dict:
        """Run the boot sequence. Returns {ok, failed, skipped}."""
        with self._lock:
            order = self._topo_sort()
            results: dict = {"ok": [], "failed": [], "skipped": []}

            for name in order:
                unit = self._units[name]
                unit.state = "pending"
                unit.error = None

                # Check required dependencies
                skip = False
                for req in unit.requires:
                    dep = self._units.get(req)
                    if dep and dep.state == "failed":
                        unit.state = "skipped"
                        unit.error = f"Required unit '{req}' failed."
                        results["skipped"].append(name)
                        logger.info("Skipping unit '%s': %s", name, unit.error)
                        skip = True
                        break
                if skip:
                    continue

                logger.info("Starting unit '%s' (%s)", name, unit.description)
                try:
                    unit.state = "running"
                    unit.start_fn()
                    results["ok"].append(name)
                    logger.info("Unit '%s' started successfully.", name)
                except Exception as exc:  # noqa: BLE001
                    unit.state = "failed"
                    unit.error = str(exc)
                    results["failed"].append(name)
                    logger.error("Unit '%s' failed: %s", name, exc)

            return results

    def shutdown(self) -> None:
        """Call stop functions in reverse boot order."""
        with self._lock:
            order = self._topo_sort()
            for name in reversed(order):
                unit = self._units.get(name)
                if unit and unit.stop_fn:
                    try:
                        unit.stop_fn()
                        unit.state = "stopped"
                        logger.info("Unit '%s' stopped.", name)
                    except Exception as exc:  # noqa: BLE001
                        logger.error("Unit '%s' stop failed: %s", name, exc)

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def status(self) -> List[dict]:
        """Return a list of status dicts for all registered units."""
        with self._lock:
            return [
                {
                    "name": u.name,
                    "description": u.description,
                    "state": u.state,
                    "error": u.error,
                }
                for u in self._units.values()
            ]
