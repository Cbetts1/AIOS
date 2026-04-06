"""``aura plugin`` command handler — plugin management."""


class PluginCommand:
    """Plugin management: scan, load, unload, list, create."""

    def execute(self, args, eal) -> int:
        from aura_os.kernel.plugins import PluginManager

        pm = PluginManager()
        sub = getattr(args, "plugin_command", None)

        if sub == "scan":
            plugins = pm.scan()
            if not plugins:
                print("  No plugins found")
                return 0
            for p in plugins:
                status = "enabled" if p.enabled else "disabled"
                print(f"  {p.name:<20} v{p.version:<8} [{status}]")
                if p.description:
                    print(f"    {p.description}")
            return 0

        if sub == "load":
            name = getattr(args, "name", "")
            pm.scan()
            if pm.load(name):
                print(f"  ✓ Plugin '{name}' loaded")
            else:
                print(f"  ✗ Failed to load plugin '{name}'")
            return 0

        if sub == "unload":
            name = getattr(args, "name", "")
            if pm.unload(name):
                print(f"  ✓ Plugin '{name}' unloaded")
            else:
                print(f"  ✗ Plugin '{name}' not loaded")
            return 0

        if sub == "reload":
            name = getattr(args, "name", "")
            pm.scan()
            if pm.reload(name):
                print(f"  ✓ Plugin '{name}' reloaded")
            else:
                print(f"  ✗ Failed to reload plugin '{name}'")
            return 0

        if sub == "create":
            name = getattr(args, "name", "")
            desc = getattr(args, "description", "")
            path = pm.create_plugin(name, description=desc)
            print(f"  ✓ Plugin scaffolded at: {path}")
            return 0

        if sub == "list" or sub is None:
            pm.scan()
            plugins = pm.list_plugins()
            if not plugins:
                print("  No plugins installed")
                return 0
            for p in plugins:
                loaded = "✓ loaded" if p["loaded"] else "○ not loaded"
                enabled = "enabled" if p["enabled"] else "disabled"
                print(f"  {p['name']:<20} v{p['version']:<8} "
                      f"[{enabled}] {loaded}")
            return 0

        return 0
