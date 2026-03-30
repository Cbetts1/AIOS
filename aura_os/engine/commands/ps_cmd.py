"""``aura ps`` command handler — list processes."""

from typing import Optional

from aura_os.kernel.process import ProcessManager


# Module-level singleton so all commands share one table
_pm: Optional[ProcessManager] = None


def get_process_manager() -> ProcessManager:
    """Return (or create) the shared ProcessManager instance."""
    global _pm
    if _pm is None:
        _pm = ProcessManager()
    return _pm


class PsCommand:
    """Display the AURA OS process table.

    Similar to ``ps`` on a real Unix system.
    """

    def execute(self, args, eal) -> int:
        """Print a formatted process list.

        Returns 0.
        """
        pm = get_process_manager()
        procs = pm.list_processes()

        if not procs:
            print("  No tracked processes.")
            return 0

        # Header
        print(f"  {'PID':<8} {'PPID':<8} {'STATUS':<10} {'ELAPSED':>10}  {'COMMAND'}")
        print("  " + "─" * 60)

        for p in procs:
            elapsed = p["elapsed"]
            if elapsed >= 3600:
                elapsed_str = f"{elapsed / 3600:.1f}h"
            elif elapsed >= 60:
                elapsed_str = f"{elapsed / 60:.1f}m"
            else:
                elapsed_str = f"{elapsed:.1f}s"

            print(
                f"  {p['pid']:<8} {p['ppid']:<8} {p['status']:<10} "
                f"{elapsed_str:>10}  {p['command']}"
            )

        return 0
