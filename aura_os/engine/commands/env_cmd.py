"""``aura env`` command handler."""

import json


class EnvCommand:
    """Display environment information gathered from the EAL.

    Supports plain text (default) and ``--json`` output modes.
    """

    def execute(self, args, eal) -> int:
        """Print environment info, optionally as JSON.

        Returns 0.
        """
        info = eal.get_env_info()

        if getattr(args, "as_json", False):
            print(json.dumps(info, indent=2))
            return 0

        self._print_human(info)
        return 0

    @staticmethod
    def _print_human(info: dict):
        """Render *info* as a human-readable table."""
        print("─" * 50)
        print("  AURA OS — Environment Info")
        print("─" * 50)

        print(f"\n  Platform   : {info.get('platform', 'unknown')}")
        print(f"  Pkg manager: {info.get('pkg_manager') or 'none detected'}")

        # Paths
        paths = info.get("paths", {})
        if paths:
            print("\n  Paths:")
            for k, v in paths.items():
                print(f"    {k:<18}: {v}")

        # System
        system = info.get("system", {})
        if system:
            print("\n  System:")
            for k, v in system.items():
                if k == "memory" and isinstance(v, dict):
                    mem = v
                    total_mb = mem.get("total_kb", mem.get("total", 0) // 1024) // 1024
                    used_mb = mem.get("used_kb", mem.get("used", 0) // 1024) // 1024
                    pct = mem.get("percent", 0)
                    print(f"    {'memory':<18}: {used_mb} MB / {total_mb} MB  ({pct}%)")
                else:
                    print(f"    {k:<18}: {v}")

        # Binaries
        binaries = info.get("binaries", {})
        if binaries:
            print("\n  Available binaries:")
            for name, path in sorted(binaries.items()):
                status = path if path else "not found"
                print(f"    {name:<14}: {status}")

        print()
