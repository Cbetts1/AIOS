"""``aura log`` command handler — view system logs."""

from aura_os.kernel.syslog import Syslog


class LogCommand:
    """View and manage the AURA OS system log.

    Sub-commands: tail (default), search, clear.
    """

    def execute(self, args, eal) -> int:
        """Dispatch to the appropriate log sub-command.

        Returns 0.
        """
        syslog = Syslog()
        sub = getattr(args, "log_command", "tail")

        if sub == "tail" or sub is None:
            return self._tail(syslog, args)
        if sub == "search":
            return self._search(syslog, args)
        if sub == "clear":
            syslog.clear()
            print("  System log cleared.")
            return 0

        print("[log] Unknown sub-command. Run 'aura log --help'.")
        return 1

    @staticmethod
    def _tail(syslog: Syslog, args) -> int:
        lines_count = getattr(args, "lines", 25)
        entries = syslog.tail(lines_count)
        if not entries:
            print("  (no log entries)")
        else:
            for entry in entries:
                print(f"  {entry}")
        return 0

    @staticmethod
    def _search(syslog: Syslog, args) -> int:
        pattern = getattr(args, "pattern", "")
        if not pattern:
            print("[log] Search pattern required.")
            return 1
        results = syslog.search(pattern)
        if not results:
            print(f"  No log entries matching '{pattern}'.")
        else:
            for entry in results:
                print(f"  {entry}")
        return 0
