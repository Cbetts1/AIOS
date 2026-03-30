"""``aura kill`` command handler — send signals to processes."""

import signal

from aura_os.engine.commands.ps_cmd import get_process_manager


class KillCommand:
    """Send a signal to a tracked AURA OS process.

    Defaults to SIGTERM.  Use ``--signal 9`` for SIGKILL.
    """

    def execute(self, args, eal) -> int:
        """Send a signal to the process identified by *args.pid*.

        Returns 0 on success, 1 on failure.
        """
        pm = get_process_manager()
        pid = args.pid
        sig = getattr(args, "signal_num", signal.SIGTERM)

        if pm.send_signal(pid, sig):
            print(f"  Signal {sig} sent to PID {pid}.")
            return 0

        # Fallback: try sending signal to any OS process
        try:
            import os
            os.kill(pid, sig)
            print(f"  Signal {sig} sent to PID {pid} (external process).")
            return 0
        except (ProcessLookupError, PermissionError, OSError) as exc:
            print(f"  Failed to signal PID {pid}: {exc}")
            return 1
