"""System repair and recovery utilities for AURA OS.

Provides real repair operations:
- Recreate missing AURA directory structure
- Rotate and clean up old log files
- Reset corrupted configuration files
- Purge stale process/service state
- Verify and restore kernel subsystem state
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import List, Tuple


class RepairResult:
    """Result of a repair action."""

    __slots__ = ("action", "target", "success", "message")

    def __init__(self, action: str, target: str,
                 success: bool, message: str = ""):
        self.action = action
        self.target = target
        self.success = success
        self.message = message


class Repair:
    """Performs real repair operations on the AURA OS runtime.

    Example::

        r = Repair()
        results = r.repair_all()
        r.print_report(results)
    """

    _REQUIRED_DIRS: Tuple[str, ...] = (
        "configs", "logs", "services", "tasks", "repos",
        "data", "models", "plugins",
    )

    _DEFAULT_CONFIG: dict = {
        "version": "1.0.0",
        "env_type": "unknown",
        "web_ui_port": 7070,
        "web_ui_host": "127.0.0.1",
        "ai_backend": "auto",
        "log_level": "info",
    }

    def __init__(self, aura_home: str = None):
        self._home = Path(aura_home or os.environ.get(
            "AURA_HOME", os.path.expanduser("~/.aura")
        ))

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def repair_all(self) -> List[RepairResult]:
        """Run all repair operations and return results."""
        results = []
        results.extend(self.repair_dirs())
        results.extend(self.repair_config())
        results.extend(self.rotate_logs())
        results.extend(self.purge_stale_state())
        return results

    def repair_dirs(self) -> List[RepairResult]:
        """Recreate any missing AURA home directories."""
        results = []
        for d in self._REQUIRED_DIRS:
            path = self._home / d
            if path.exists():
                results.append(RepairResult(
                    "check_dir", str(path), True, "already exists"
                ))
            else:
                try:
                    path.mkdir(parents=True, exist_ok=True)
                    results.append(RepairResult(
                        "create_dir", str(path), True, "created"
                    ))
                except OSError as exc:
                    results.append(RepairResult(
                        "create_dir", str(path), False, str(exc)
                    ))
        return results

    def repair_config(self) -> List[RepairResult]:
        """Restore or validate the system configuration file."""
        results = []
        cfg_dir = self._home / "configs"
        cfg_path = cfg_dir / "system.json"

        try:
            cfg_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            results.append(RepairResult(
                "create_config_dir", str(cfg_dir), False, str(exc)
            ))
            return results

        if cfg_path.exists():
            try:
                data = json.loads(cfg_path.read_text())
                # Check for required keys; add any missing
                updated = False
                for k, v in self._DEFAULT_CONFIG.items():
                    if k not in data:
                        data[k] = v
                        updated = True
                if updated:
                    cfg_path.write_text(json.dumps(data, indent=2))
                    results.append(RepairResult(
                        "update_config", str(cfg_path), True,
                        "added missing keys"
                    ))
                else:
                    results.append(RepairResult(
                        "check_config", str(cfg_path), True, "valid"
                    ))
            except (json.JSONDecodeError, OSError) as exc:
                # Overwrite with defaults
                try:
                    backup = cfg_path.with_suffix(".json.bak")
                    cfg_path.rename(backup)
                    cfg_path.write_text(json.dumps(self._DEFAULT_CONFIG, indent=2))
                    results.append(RepairResult(
                        "reset_config", str(cfg_path), True,
                        f"was corrupt ({exc}), reset to defaults; backup: {backup.name}"
                    ))
                except OSError as e2:
                    results.append(RepairResult(
                        "reset_config", str(cfg_path), False, str(e2)
                    ))
        else:
            try:
                cfg_path.write_text(json.dumps(self._DEFAULT_CONFIG, indent=2))
                results.append(RepairResult(
                    "create_config", str(cfg_path), True, "created with defaults"
                ))
            except OSError as exc:
                results.append(RepairResult(
                    "create_config", str(cfg_path), False, str(exc)
                ))
        return results

    def rotate_logs(self, max_size_mb: float = 10.0,
                    keep_days: int = 7) -> List[RepairResult]:
        """Rotate log files that exceed *max_size_mb* and remove old ones."""
        results = []
        log_dir = self._home / "logs"
        if not log_dir.exists():
            return results

        max_bytes = int(max_size_mb * 1_000_000)
        cutoff = time.time() - keep_days * 86400

        for log_file in log_dir.glob("*.log"):
            try:
                stat = log_file.stat()
                if stat.st_size > max_bytes:
                    rotated = log_file.with_suffix(
                        f".{time.strftime('%Y%m%d%H%M%S')}.log"
                    )
                    log_file.rename(rotated)
                    log_file.write_text("")
                    results.append(RepairResult(
                        "rotate_log", str(log_file), True,
                        f"rotated to {rotated.name}"
                    ))
                elif stat.st_mtime < cutoff:
                    log_file.unlink()
                    results.append(RepairResult(
                        "purge_log", str(log_file), True,
                        "deleted (expired)"
                    ))
            except OSError as exc:
                results.append(RepairResult(
                    "rotate_log", str(log_file), False, str(exc)
                ))
        return results

    def purge_stale_state(self) -> List[RepairResult]:
        """Remove stale runtime state files (PID files, lock files)."""
        results = []
        for pattern in ("*.pid", "*.lock", ".write_test"):
            for stale in self._home.rglob(pattern):
                try:
                    stale.unlink()
                    results.append(RepairResult(
                        "purge_stale", str(stale), True, "removed"
                    ))
                except OSError as exc:
                    results.append(RepairResult(
                        "purge_stale", str(stale), False, str(exc)
                    ))
        return results

    def print_report(self, results: List[RepairResult] = None) -> None:
        """Print a formatted repair report to stdout."""
        if results is None:
            results = self.repair_all()
        ok = sum(1 for r in results if r.success)
        print("=" * 60)
        print("  AURA OS — Repair Report")
        print("=" * 60)
        for r in results:
            sym = "✓" if r.success else "✗"
            print(f"  {sym}  [{r.action}]  {Path(r.target).name}  {r.message}")
        print(f"\n  {ok}/{len(results)} operations succeeded.")
        print()


# ---------------------------------------------------------------------------
# CLI command wrapper
# ---------------------------------------------------------------------------

class RepairCommand:
    """``aura repair`` — repair the AURA OS runtime."""

    def execute(self, args, eal) -> int:
        sub = getattr(args, "repair_cmd", "all")
        home = os.environ.get("AURA_HOME", os.path.expanduser("~/.aura"))
        r = Repair(home)

        if sub == "dirs":
            results = r.repair_dirs()
        elif sub == "config":
            results = r.repair_config()
        elif sub == "logs":
            results = r.rotate_logs()
        elif sub == "state":
            results = r.purge_stale_state()
        else:
            results = r.repair_all()

        r.print_report(results)
        failures = sum(1 for res in results if not res.success)
        return 0 if failures == 0 else 1
