"""``aura pkg`` command handler."""

from aura_os.pkg.manager import PackageManager
from aura_os.pkg.registry import LocalRegistry
from aura_os.shell.colors import bold, cyan, dim, green, red, yellow


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
                print(f"  {yellow('[pkg]')} No packages installed.")
            else:
                print(f"  {bold('NAME'):<34} {bold('VERSION'):<22} {bold('DESCRIPTION')}")
                print(f"  {dim('─' * 64)}")
                for pkg in packages:
                    name = pkg.get("name", "?")
                    ver = pkg.get("version", "?")
                    desc = pkg.get("description", "")
                    print(f"  {cyan(name):<34} {green(ver):<22} {desc}")
            return 0

        if sub == "search":
            results = manager.search(args.query)
            if not results:
                print(f"  {yellow('[pkg]')} No packages found matching '{args.query}'.")
            else:
                print(f"  {bold('NAME'):<34} {bold('VERSION'):<22} {bold('DESCRIPTION')}")
                print(f"  {dim('─' * 64)}")
                for pkg in results:
                    name = pkg.get("name", "?")
                    ver = pkg.get("version", "?")
                    desc = pkg.get("description", "")
                    print(f"  {cyan(name):<34} {green(ver):<22} {desc}")
            return 0

        if sub == "info":
            pkg = registry.get_package(args.name)
            if pkg is None:
                print(f"  {red('[pkg]')} Package '{args.name}' not found in registry.")
                return 1
            for key, value in pkg.items():
                print(f"  {bold(key):<26}: {value}")
            return 0

        print(f"  {red('[pkg]')} Unknown sub-command '{sub}'. Run 'aura pkg --help'.")
        return 1
