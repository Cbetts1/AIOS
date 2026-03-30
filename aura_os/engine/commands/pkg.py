"""``aura pkg`` command handler."""

from aura_os.pkg.manager import PackageManager
from aura_os.pkg.registry import LocalRegistry


class PkgCommand:
    """Package management interface.

    Delegates to :class:`~aura_os.pkg.manager.PackageManager` for all
    operations.  Supports sub-commands: install, remove, list, search, info.
    """

    def execute(self, args, eal) -> int:
        """Dispatch to the appropriate pkg sub-command.

        Returns 0 on success, 1 on failure.
        """
        registry = LocalRegistry()
        manager = PackageManager(registry=registry)

        sub = getattr(args, "pkg_command", None)

        if sub == "install":
            return 0 if manager.install(args.name_or_path) else 1

        if sub == "remove":
            return 0 if manager.remove(args.name) else 1

        if sub == "list":
            packages = manager.list_installed()
            if not packages:
                print("[pkg] No packages installed.")
            else:
                print(f"{'NAME':<24} {'VERSION':<12} DESCRIPTION")
                print("─" * 64)
                for pkg in packages:
                    name = pkg.get("name", "?")
                    ver = pkg.get("version", "?")
                    desc = pkg.get("description", "")
                    print(f"{name:<24} {ver:<12} {desc}")
            return 0

        if sub == "search":
            results = manager.search(args.query)
            if not results:
                print(f"[pkg] No packages found matching '{args.query}'.")
            else:
                print(f"{'NAME':<24} {'VERSION':<12} DESCRIPTION")
                print("─" * 64)
                for pkg in results:
                    name = pkg.get("name", "?")
                    ver = pkg.get("version", "?")
                    desc = pkg.get("description", "")
                    print(f"{name:<24} {ver:<12} {desc}")
            return 0

        if sub == "info":
            pkg = registry.get_package(args.name)
            if pkg is None:
                print(f"[pkg] Package '{args.name}' not found in registry.")
                return 1
            for key, value in pkg.items():
                print(f"  {key:<16}: {value}")
            return 0

        print(f"[pkg] Unknown sub-command '{sub}'. Run 'aura pkg --help'.")
        return 1
