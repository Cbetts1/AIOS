"""
Permission System — Capability-based safety checks for AURA OS.

AURA OS runs as a user-space overlay and NEVER modifies the host core
system without explicit permission.  This module gates dangerous
operations behind permission checks.
"""

from __future__ import annotations

import os
import sys

# Actions requiring explicit confirmation
DANGEROUS_ACTIONS = {
    "pkg_install":  "Install system packages",
    "pkg_remove":   "Remove system packages",
    "fs_delete":    "Delete files or directories",
    "process_kill": "Terminate a running process",
    "host_shell":   "Execute a raw host shell command",
    "systemd":      "Install or modify a systemd service",
    "sudo":         "Execute a command with elevated privileges",
}


def check_permission(action: str, detail: str = "", *, auto_approve: bool = False) -> bool:
    """
    Prompt the user for permission before a dangerous operation.

    Parameters
    ----------
    action : str
        A key from ``DANGEROUS_ACTIONS``.
    detail : str
        Human-readable description of the specific operation.
    auto_approve : bool
        If True, skip the prompt (for non-interactive / automation use).

    Returns
    -------
    bool
        True if the user grants permission.
    """
    if auto_approve:
        return True

    desc = DANGEROUS_ACTIONS.get(action, action)
    print(f"\n  ⚠  Permission required: {desc}")
    if detail:
        print(f"     {detail}")

    # Non-interactive (piped stdin) → deny by default
    if not sys.stdin.isatty():
        print("     [denied — non-interactive mode]")
        return False

    try:
        answer = input("     Allow? [y/N] ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return False

    return answer in ("y", "yes")


def require_permission(action: str, detail: str = "", *, auto_approve: bool = False):
    """
    Like ``check_permission`` but raises ``PermissionError`` on denial.
    """
    if not check_permission(action, detail, auto_approve=auto_approve):
        raise PermissionError(f"Permission denied: {action}")
