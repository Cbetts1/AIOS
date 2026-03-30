"""``aura service`` command handler — manage background services."""

from aura_os.kernel.service import ServiceManager


class ServiceCommand:
    """Manage AURA OS background services.

    Sub-commands: list, start, stop, restart, status, enable, disable, create.
    """

    def execute(self, args, eal) -> int:
        """Dispatch to the appropriate service sub-command.

        Returns 0 on success, 1 on failure.
        """
        mgr = ServiceManager()
        sub = getattr(args, "svc_command", None)

        if sub == "list":
            return self._list(mgr)
        if sub == "start":
            return self._start(mgr, args.name)
        if sub == "stop":
            return self._stop(mgr, args.name)
        if sub == "restart":
            return self._restart(mgr, args.name)
        if sub == "status":
            return self._status(mgr, args.name)
        if sub == "enable":
            return self._enable(mgr, args.name)
        if sub == "disable":
            return self._disable(mgr, args.name)
        if sub == "create":
            return self._create(mgr, args)

        print("[service] Unknown sub-command. Run 'aura service --help'.")
        return 1

    # ------------------------------------------------------------------
    # Sub-command implementations
    # ------------------------------------------------------------------

    @staticmethod
    def _list(mgr: ServiceManager) -> int:
        services = mgr.list_services()
        if not services:
            print("  No services configured.")
            return 0

        print(f"  {'NAME':<20} {'STATUS':<10} {'ENABLED':<9} {'PID':<8} {'DESCRIPTION'}")
        print("  " + "─" * 70)
        for svc in services:
            enabled_str = "yes" if svc["enabled"] else "no"
            pid_str = str(svc["pid"]) if svc["pid"] else "-"
            print(
                f"  {svc['name']:<20} {svc['status']:<10} {enabled_str:<9} "
                f"{pid_str:<8} {svc['description']}"
            )
        return 0

    @staticmethod
    def _start(mgr: ServiceManager, name: str) -> int:
        if mgr.start(name):
            info = mgr.status(name)
            pid = info["pid"] if info else "?"
            print(f"  Service '{name}' started (PID {pid}).")
            return 0
        print(f"  Failed to start service '{name}'. Does it exist?")
        return 1

    @staticmethod
    def _stop(mgr: ServiceManager, name: str) -> int:
        if mgr.stop(name):
            print(f"  Service '{name}' stopped.")
            return 0
        print(f"  Service '{name}' is not running or does not exist.")
        return 1

    @staticmethod
    def _restart(mgr: ServiceManager, name: str) -> int:
        if mgr.restart(name):
            print(f"  Service '{name}' restarted.")
            return 0
        print(f"  Failed to restart service '{name}'.")
        return 1

    @staticmethod
    def _status(mgr: ServiceManager, name: str) -> int:
        info = mgr.status(name)
        if info is None:
            print(f"  Service '{name}' not found.")
            return 1
        print(f"  Service: {info['name']}")
        print(f"  Status:  {info['status']}")
        print(f"  Enabled: {'yes' if info['enabled'] else 'no'}")
        print(f"  PID:     {info['pid'] or '-'}")
        print(f"  Uptime:  {info['elapsed']}s")
        print(f"  Restarts:{info['restarts']}")
        print(f"  Command: {info['command']}")
        print(f"  Desc:    {info['description']}")
        return 0

    @staticmethod
    def _enable(mgr: ServiceManager, name: str) -> int:
        if mgr.enable(name):
            print(f"  Service '{name}' enabled (auto-start on boot).")
            return 0
        print(f"  Service '{name}' not found.")
        return 1

    @staticmethod
    def _disable(mgr: ServiceManager, name: str) -> int:
        if mgr.disable(name):
            print(f"  Service '{name}' disabled.")
            return 0
        print(f"  Service '{name}' not found.")
        return 1

    @staticmethod
    def _create(mgr: ServiceManager, args) -> int:
        name = args.name
        command = getattr(args, "cmd", "")
        description = getattr(args, "description", "")
        if not command:
            print("[service] --cmd is required when creating a service.")
            return 1
        mgr.create(name, command, description=description)
        print(f"  Service '{name}' created.")
        return 0
