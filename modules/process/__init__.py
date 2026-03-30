"""
Process Management Module — ps, kill, and background job tracking for AURA OS.

Provides cross-platform process listing, process termination, and a simple
background-job registry so AURA can track processes it starts itself.
"""

from __future__ import annotations

import os
import signal
import time
from pathlib import Path
from typing import Optional


class ProcessModule:
    """
    Cross-platform process manager for AURA OS.

    Uses the EAL adapter to execute platform-specific commands while
    maintaining its own lightweight job registry for AURA-spawned
    background processes.
    """

    def __init__(self, env_map: dict, adapter):
        self.env = env_map
        self.adapter = adapter
        # In-memory registry of background jobs started via ``spawn``
        self._jobs: dict[int, dict] = {}
        self._next_job = 1

    # ------------------------------------------------------------------ #
    # Process listing
    # ------------------------------------------------------------------ #

    def ps(self, user_only: bool = True):
        """
        Print a process listing.
        On POSIX, uses ``ps``; on Windows, uses ``tasklist``.
        """
        env_type = self.env.get("env_type", "unknown")
        if env_type == "windows":
            cmd = ["tasklist"]
        else:
            cmd = ["ps", "aux"] if not user_only else ["ps", "ux"]

        rc, out, _ = self.adapter.run(cmd, capture=True, timeout=10)
        if rc == 0 and out:
            print(out)
        else:
            print("[aura ps] Unable to list processes.")

    # ------------------------------------------------------------------ #
    # Process termination
    # ------------------------------------------------------------------ #

    def kill(self, pid: int, sig: int = 15) -> bool:
        """
        Send a signal to a process.  Default is SIGTERM (15).
        Returns True if successful.
        """
        try:
            os.kill(pid, sig)
            print(f"[aura kill] Signal {sig} sent to PID {pid}.")
            return True
        except ProcessLookupError:
            print(f"[aura kill] No such process: {pid}")
            return False
        except PermissionError:
            print(f"[aura kill] Permission denied for PID {pid}.")
            return False

    # ------------------------------------------------------------------ #
    # Background job management
    # ------------------------------------------------------------------ #

    def spawn(self, cmd: list[str] | str, name: Optional[str] = None) -> int:
        """
        Start *cmd* in the background, register it as an AURA job,
        and return the job number.
        """
        proc = self.adapter.run_bg(cmd)
        jid = self._next_job
        self._next_job += 1
        self._jobs[jid] = {
            "pid": proc.pid,
            "cmd": cmd if isinstance(cmd, str) else " ".join(cmd),
            "name": name or f"job-{jid}",
            "started": time.time(),
            "proc": proc,
        }
        print(f"[aura] Job [{jid}] started — PID {proc.pid}: {self._jobs[jid]['cmd']}")
        return jid

    def jobs(self):
        """Print all tracked background jobs and their status."""
        if not self._jobs:
            print("[aura jobs] No background jobs.")
            return

        print("\n  AURA Background Jobs")
        print("  " + "─" * 55)
        print(f"  {'JID':<5} {'PID':<8} {'STATUS':<10} {'NAME':<16} CMD")
        print("  " + "─" * 55)
        for jid, info in sorted(self._jobs.items()):
            proc = info["proc"]
            poll = proc.poll()
            status = "running" if poll is None else f"exited({poll})"
            print(f"  {jid:<5} {info['pid']:<8} {status:<10} {info['name']:<16} {info['cmd']}")
        print()

    def stop_job(self, jid: int) -> bool:
        """Terminate background job by AURA job-ID."""
        info = self._jobs.get(jid)
        if info is None:
            print(f"[aura jobs] No such job: {jid}")
            return False
        proc = info["proc"]
        if proc.poll() is None:
            proc.terminate()
            print(f"[aura jobs] Job [{jid}] (PID {info['pid']}) terminated.")
        else:
            print(f"[aura jobs] Job [{jid}] already exited.")
        return True

    # ------------------------------------------------------------------ #
    # System info helpers
    # ------------------------------------------------------------------ #

    def uptime(self):
        """Print system uptime (POSIX only)."""
        rc, out, _ = self.adapter.run(["uptime"], capture=True, timeout=5)
        if rc == 0 and out:
            print(out.strip())
        else:
            print("[aura] Uptime not available on this platform.")

    def top(self, lines: int = 20):
        """Print top resource-consuming processes."""
        env_type = self.env.get("env_type", "unknown")
        if env_type == "windows":
            cmd = ["tasklist", "/FI", "STATUS eq running"]
        else:
            cmd = ["ps", "aux", "--sort=-%cpu"]

        rc, out, _ = self.adapter.run(cmd, capture=True, timeout=10)
        if rc == 0 and out:
            for i, line in enumerate(out.splitlines()):
                if i >= lines:
                    break
                print(line)
        else:
            print("[aura top] Unable to retrieve process info.")
