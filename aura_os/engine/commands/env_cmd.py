"""``aura env`` command handler."""

import json

from aura_os.shell.colors import bold, cyan, dim, green, header, red, yellow


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
        """Render *info* as a human-readable, colored table."""
        sep = dim("─" * 50)
        print(sep)
        print(f"  {header('⬡ AURA OS')} — {bold('Environment Info')}")
        print(sep)

        print(f"\n  {bold('Platform')}   : {cyan(info.get('platform', 'unknown'))}")
        pkg_mgr = info.get('pkg_manager') or 'none detected'
        print(f"  {bold('Pkg manager')}: {pkg_mgr}")

        # Paths
        paths = info.get("paths", {})
        if paths:
            print(f"\n  {bold('Paths:')}")
            for k, v in paths.items():
                print(f"    {dim(k + ':'):<28} {v}")

        # System
        system = info.get("system", {})
        if system:
            print(f"\n  {bold('System:')}")
            for k, v in system.items():
                if k == "memory" and isinstance(v, dict):
                    mem = v
                    total_mb = mem.get("total_kb", mem.get("total", 0) // 1024) // 1024
                    used_mb = mem.get("used_kb", mem.get("used", 0) // 1024) // 1024
                    pct = mem.get("percent", 0)
                    color = green if pct < 50 else (yellow if pct < 80 else red)
                    print(f"    {dim('memory:'):<28} "
                          f"{color(f'{used_mb} MB / {total_mb} MB  ({pct}%)')}")
                else:
                    print(f"    {dim(k + ':'):<28} {v}")

        # Binaries
        binaries = info.get("binaries", {})
        if binaries:
            print(f"\n  {bold('Available binaries:')}")
            for name, path in sorted(binaries.items()):
                if path:
                    print(f"    {cyan(name):<24} {dim(str(path))}")
                else:
                    print(f"    {dim(name):<24} {red('not found')}")

        print()
