"""Init system command handler for AURA OS."""


class InitCommand:
    """Handles the ``init`` sub-command."""

    def execute(self, args, eal) -> int:
        from aura_os.init import InitManager

        im = InitManager()
        sub = args.init_command

        if sub == "status":
            return self._status(im)
        if sub == "boot":
            return self._boot(im)
        if sub == "shutdown":
            return self._shutdown(im)
        print(f"init: unknown sub-command '{sub}'")
        return 1

    # ------------------------------------------------------------------

    def _status(self, im) -> int:
        units = im.status()
        if not units:
            print("  (no units registered)")
            return 0
        fmt = "  {:<20} {:<10} {}"
        print(fmt.format("UNIT", "STATE", "DESCRIPTION"))
        print("  " + "-" * 55)
        for u in units:
            print(fmt.format(u["name"], u["state"], u.get("description", "")))
        return 0

    def _boot(self, im) -> int:
        results = im.boot()
        ok = results.get("ok", [])
        failed = results.get("failed", [])
        skipped = results.get("skipped", [])
        print(f"  Boot complete — ok: {len(ok)}, failed: {len(failed)}, skipped: {len(skipped)}")
        if failed:
            print(f"  Failed units: {', '.join(failed)}")
        if skipped:
            print(f"  Skipped units: {', '.join(skipped)}")
        return 0 if not failed else 1

    def _shutdown(self, im) -> int:
        im.shutdown()
        print("  Shutdown complete.")
        return 0
