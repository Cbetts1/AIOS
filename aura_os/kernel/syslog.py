"""Centralized system logger for AURA OS.

Provides a syslog-style logging facility with severity levels and
facility tags.  Logs are written to ``~/.aura/logs/syslog.log`` as
well as optionally printed to the console.
"""

import datetime
import os
import threading
from typing import List, Optional


# Severity constants (lower = more severe)
EMERG = 0
ALERT = 1
CRIT = 2
ERR = 3
WARNING = 4
NOTICE = 5
INFO = 6
DEBUG = 7

_SEVERITY_NAMES = {
    EMERG: "emerg",
    ALERT: "alert",
    CRIT: "crit",
    ERR: "err",
    WARNING: "warning",
    NOTICE: "notice",
    INFO: "info",
    DEBUG: "debug",
}

_NAME_TO_SEVERITY = {v: k for k, v in _SEVERITY_NAMES.items()}


class Syslog:
    """Singleton-style centralized system logger.

    Messages are written as one-line records to the log file with the
    format::

        <timestamp> [<facility>.<severity>] <message>

    Example::

        2025-07-04T12:00:01 [kern.info] AURA OS booted successfully
    """

    _instance: Optional["Syslog"] = None
    _init_lock = threading.Lock()

    def __new__(cls, log_path: str = None):
        with cls._init_lock:
            if cls._instance is None:
                inst = super().__new__(cls)
                inst._initialized = False
                cls._instance = inst
        return cls._instance

    def __init__(self, log_path: str = None):
        if self._initialized:
            return
        aura_home = os.environ.get("AURA_HOME", os.path.expanduser("~/.aura"))
        self._log_path = log_path or os.path.join(aura_home, "logs", "syslog.log")
        os.makedirs(os.path.dirname(self._log_path), exist_ok=True)
        self._lock = threading.Lock()
        self._min_severity = INFO
        self._console = False
        self._initialized = True

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    def set_level(self, severity: int):
        """Set the minimum severity level.  Messages below this are dropped."""
        self._min_severity = severity

    def set_console(self, enabled: bool):
        """Enable or disable echoing log messages to stdout."""
        self._console = enabled

    # ------------------------------------------------------------------
    # Logging
    # ------------------------------------------------------------------

    def log(self, facility: str, severity: int, message: str):
        """Write a log record.

        Parameters
        ----------
        facility : str
            The subsystem that generated the message (e.g. ``kern``,
            ``daemon``, ``user``, ``service``, ``shell``).
        severity : int
            One of the module-level severity constants.
        message : str
            The log text.
        """
        if severity > self._min_severity:
            return

        sev_name = _SEVERITY_NAMES.get(severity, "info")
        ts = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        line = f"{ts} [{facility}.{sev_name}] {message}\n"

        with self._lock:
            with open(self._log_path, "a", encoding="utf-8") as fh:
                fh.write(line)

        if self._console:
            print(line, end="")

    # Convenience helpers ------------------------------------------------

    def info(self, facility: str, message: str):
        self.log(facility, INFO, message)

    def warning(self, facility: str, message: str):
        self.log(facility, WARNING, message)

    def error(self, facility: str, message: str):
        self.log(facility, ERR, message)

    def debug(self, facility: str, message: str):
        self.log(facility, DEBUG, message)

    # ------------------------------------------------------------------
    # Reading
    # ------------------------------------------------------------------

    def tail(self, lines: int = 25) -> List[str]:
        """Return the last *lines* entries from the log file."""
        if not os.path.isfile(self._log_path):
            return []
        with self._lock:
            with open(self._log_path, "r", encoding="utf-8") as fh:
                all_lines = fh.readlines()
        return [ln.rstrip("\n") for ln in all_lines[-lines:]]

    def search(self, pattern: str, max_results: int = 50) -> List[str]:
        """Return log lines containing *pattern* (case-insensitive)."""
        if not os.path.isfile(self._log_path):
            return []
        pattern_lower = pattern.lower()
        results: List[str] = []
        with self._lock:
            with open(self._log_path, "r", encoding="utf-8") as fh:
                for raw_line in fh:
                    if pattern_lower in raw_line.lower():
                        results.append(raw_line.rstrip("\n"))
                        if len(results) >= max_results:
                            break
        return results

    def clear(self):
        """Truncate the log file."""
        with self._lock:
            with open(self._log_path, "w", encoding="utf-8") as fh:
                fh.truncate(0)

    @classmethod
    def reset_instance(cls):
        """Reset the singleton — only for testing."""
        with cls._init_lock:
            cls._instance = None
