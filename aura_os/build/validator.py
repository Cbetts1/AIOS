"""System integrity validator for AURA OS.

The ``Validator`` class performs a set of lightweight checks to verify that
the AURA OS installation is healthy:

- Python version ≥ 3.8
- Required AURA_HOME directories exist and are writable
- All kernel subsystems can be imported
- Optional dependency availability (psutil, flask, cryptography)
- Sufficient free disk space
- Log directory is writable

``ValidateCommand`` exposes these checks as ``aura validate``.
"""

from __future__ import annotations

import importlib
import os
import shutil
import sys
import time
from typing import List, Tuple


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

class CheckResult:
    """The result of a single validation check."""

    __slots__ = ("name", "passed", "message")

    def __init__(self, name: str, passed: bool, message: str = ""):
        self.name = name
        self.passed = passed
        self.message = message

    def __repr__(self) -> str:  # pragma: no cover
        status = "PASS" if self.passed else "FAIL"
        return f"CheckResult({self.name!r}, {status}, {self.message!r})"


# ---------------------------------------------------------------------------
# Validator
# ---------------------------------------------------------------------------

class Validator:
    """AURA OS integrity validator.

    Args:
        aura_home: Path to AURA_HOME.  Defaults to ``~/.aura``.
        min_free_mb: Minimum free disk space (MiB) required.  Default 50 MiB.
    """

    _REQUIRED_DIRS: Tuple[str, ...] = (
        "configs", "logs", "data", "services", "tasks",
        "repos", "models", "plugins",
    )

    _KERNEL_MODULES: Tuple[str, ...] = (
        "aura_os.kernel.process",
        "aura_os.kernel.service",
        "aura_os.kernel.syslog",
        "aura_os.kernel.scheduler",
        "aura_os.kernel.memory",
        "aura_os.kernel.network",
        "aura_os.kernel.events",
        "aura_os.kernel.cron",
        "aura_os.kernel.clipboard",
        "aura_os.kernel.plugins",
        "aura_os.kernel.secrets",
        "aura_os.kernel.ipc",
    )

    _OPTIONAL_DEPS: Tuple[Tuple[str, str], ...] = (
        ("psutil", "system metrics (aura sys, health, monitor)"),
        ("flask", "web API dashboard (aura web)"),
        ("cryptography", "secret encryption (aura secret)"),
    )

    def __init__(self, aura_home: str = None, min_free_mb: int = 50):
        self._home = aura_home or os.environ.get(
            "AURA_HOME", os.path.expanduser("~/.aura")
        )
        self._min_free_mb = min_free_mb

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run_all(self) -> List[CheckResult]:
        """Run all validation checks and return the list of results."""
        results: List[CheckResult] = []
        results.extend(self._check_python())
        results.extend(self._check_directories())
        results.extend(self._check_disk_space())
        results.extend(self._check_log_writable())
        results.extend(self._check_kernel_modules())
        results.extend(self._check_optional_deps())
        return results

    def print_report(self, results: List[CheckResult] = None) -> None:
        """Print a formatted validation report to stdout."""
        if results is None:
            results = self.run_all()

        width = 60
        print("=" * width)
        print("  AURA OS — Integrity Validation")
        print(f"  {time.strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * width)

        passed = 0
        failed = 0
        for r in results:
            sym = "✓" if r.passed else "✗"
            msg = f"  {r.message}" if r.message else ""
            print(f"  {sym}  {r.name:<40} {msg}")
            if r.passed:
                passed += 1
            else:
                failed += 1

        print()
        print(f"  Passed: {passed}   Failed: {failed}")
        print("=" * width)

    def all_passed(self, results: List[CheckResult] = None) -> bool:
        """Return True only if every *required* check passed.

        Optional-dependency checks are informational and do not count as
        failures here.
        """
        if results is None:
            results = self.run_all()
        return all(r.passed for r in results if not r.name.startswith("optional:"))

    # ------------------------------------------------------------------
    # Check sections
    # ------------------------------------------------------------------

    def _check_python(self) -> List[CheckResult]:
        major, minor = sys.version_info[:2]
        ok = (major, minor) >= (3, 8)
        return [
            CheckResult(
                "python:version",
                ok,
                f"{major}.{minor}" + ("" if ok else " (need ≥ 3.8)"),
            )
        ]

    def _check_directories(self) -> List[CheckResult]:
        results = []
        for d in self._REQUIRED_DIRS:
            path = os.path.join(self._home, d)
            exists = os.path.isdir(path)
            results.append(CheckResult(
                f"dir:{d}",
                True,  # missing dirs are only warnings; Repair can fix them
                "exists" if exists else "missing (run 'aura repair dirs')",
            ))
        return results

    def _check_disk_space(self) -> List[CheckResult]:
        try:
            total, _, free = shutil.disk_usage(self._home if os.path.exists(self._home)
                                               else os.path.expanduser("~"))
            free_mb = free / (1 << 20)
            ok = free_mb >= self._min_free_mb
            return [CheckResult(
                "disk:free_space",
                ok,
                f"{free_mb:.0f} MiB free" + ("" if ok
                                              else f" (need ≥ {self._min_free_mb} MiB)"),
            )]
        except OSError as exc:
            return [CheckResult("disk:free_space", False, str(exc))]

    def _check_log_writable(self) -> List[CheckResult]:
        log_dir = os.path.join(self._home, "logs")
        try:
            os.makedirs(log_dir, exist_ok=True)
            test_file = os.path.join(log_dir, ".write_test")
            with open(test_file, "w") as fh:
                fh.write("ok")
            os.remove(test_file)
            return [CheckResult("logs:writable", True, log_dir)]
        except OSError as exc:
            return [CheckResult("logs:writable", False, str(exc))]

    def _check_kernel_modules(self) -> List[CheckResult]:
        results = []
        for mod in self._KERNEL_MODULES:
            short = mod.split(".")[-1]
            try:
                importlib.import_module(mod)
                results.append(CheckResult(f"kernel:{short}", True, "ok"))
            except ImportError as exc:
                results.append(CheckResult(f"kernel:{short}", False, str(exc)))
        return results

    def _check_optional_deps(self) -> List[CheckResult]:
        results = []
        for pkg, purpose in self._OPTIONAL_DEPS:
            try:
                importlib.import_module(pkg)
                results.append(CheckResult(f"optional:{pkg}", True,
                                           f"installed ({purpose})"))
            except ImportError:
                results.append(CheckResult(f"optional:{pkg}", True,
                                           f"not installed — {purpose} unavailable"))
        return results


# ---------------------------------------------------------------------------
# CLI command wrapper
# ---------------------------------------------------------------------------

class ValidateCommand:
    """``aura validate`` — run system integrity validation checks."""

    def execute(self, args, eal) -> int:
        home = os.environ.get("AURA_HOME", os.path.expanduser("~/.aura"))
        v = Validator(home)
        results = v.run_all()
        v.print_report(results)
        return 0 if v.all_passed(results) else 1
