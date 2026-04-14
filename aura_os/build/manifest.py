"""System manifest builder and differ for AURA OS.

``ManifestBuilder`` generates a point-in-time JSON snapshot of the running
AURA OS installation:

- Version info
- Installed packages (from PackageManager)
- Kernel module status
- Filesystem snapshot (VFS)
- Registered services

``BuildCommand`` exposes these utilities as:

- ``aura build manifest [--output FILE]``
- ``aura build diff OLD NEW``
- ``aura build validate``
"""

from __future__ import annotations

import json
import os
import sys
import time
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# ManifestBuilder
# ---------------------------------------------------------------------------

class ManifestBuilder:
    """Generates a JSON system manifest for AURA OS.

    Args:
        aura_home: Path to AURA_HOME.  Defaults to ``~/.aura``.
    """

    def __init__(self, aura_home: str = None):
        self._home = aura_home or os.environ.get(
            "AURA_HOME", os.path.expanduser("~/.aura")
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def build(self) -> Dict[str, Any]:
        """Build and return the manifest as a dict."""
        return {
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "aura_version": self._aura_version(),
            "python_version": sys.version.split()[0],
            "platform": sys.platform,
            "aura_home": self._home,
            "packages": self._collect_packages(),
            "kernel_modules": self._collect_kernel_modules(),
            "services": self._collect_services(),
            "filesystem": self._collect_filesystem(),
        }

    def build_json(self, indent: int = 2) -> str:
        """Return the manifest serialised as a JSON string."""
        return json.dumps(self.build(), indent=indent)

    def save(self, path: str) -> None:
        """Save the manifest to *path* as JSON."""
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(self.build_json())

    def print_summary(self, manifest: Dict[str, Any] = None) -> None:
        """Print a human-readable summary of the manifest to stdout."""
        if manifest is None:
            manifest = self.build()

        print("=" * 60)
        print("  AURA OS — System Manifest")
        print(f"  Generated: {manifest.get('generated_at', '?')}")
        print("=" * 60)
        print(f"  AURA version  : {manifest.get('aura_version', '?')}")
        print(f"  Python        : {manifest.get('python_version', '?')}")
        print(f"  Platform      : {manifest.get('platform', '?')}")
        print(f"  AURA_HOME     : {manifest.get('aura_home', '?')}")

        pkgs = manifest.get("packages", [])
        print(f"\n  Packages ({len(pkgs)}):")
        for pkg in pkgs[:10]:
            print(f"    {pkg.get('name', '?'):<20} {pkg.get('version', '')}")
        if len(pkgs) > 10:
            print(f"    … {len(pkgs) - 10} more")

        mods = manifest.get("kernel_modules", {})
        ok_count = sum(1 for v in mods.values() if v == "ok")
        print(f"\n  Kernel modules: {ok_count}/{len(mods)} loaded")
        for name, status in mods.items():
            sym = "✓" if status == "ok" else "✗"
            print(f"    {sym}  {name}")

        svcs = manifest.get("services", [])
        print(f"\n  Services ({len(svcs)}):")
        for svc in svcs[:8]:
            print(f"    {svc.get('name', '?'):<20} {svc.get('status', '?')}")

        print()

    # ------------------------------------------------------------------
    # Diff support
    # ------------------------------------------------------------------

    @staticmethod
    def diff(old: Dict[str, Any], new: Dict[str, Any]) -> Dict[str, Any]:
        """Return a diff dict describing changes between two manifests.

        Keys in the result:
        - ``added_packages``   — packages in *new* but not *old*
        - ``removed_packages`` — packages in *old* but not *new*
        - ``changed_packages`` — packages whose version changed
        - ``kernel_changes``   — modules whose status changed
        - ``service_changes``  — services whose status changed
        """
        def _pkg_map(manifest: Dict[str, Any]) -> Dict[str, str]:
            return {p["name"]: p.get("version", "") for p in manifest.get("packages", [])}

        old_pkgs = _pkg_map(old)
        new_pkgs = _pkg_map(new)

        added = [{"name": k, "version": new_pkgs[k]}
                 for k in new_pkgs if k not in old_pkgs]
        removed = [{"name": k, "version": old_pkgs[k]}
                   for k in old_pkgs if k not in new_pkgs]
        changed = [{"name": k, "old": old_pkgs[k], "new": new_pkgs[k]}
                   for k in old_pkgs if k in new_pkgs and old_pkgs[k] != new_pkgs[k]]

        old_mods = old.get("kernel_modules", {})
        new_mods = new.get("kernel_modules", {})
        kernel_changes = {k: {"old": old_mods.get(k), "new": new_mods.get(k)}
                          for k in set(old_mods) | set(new_mods)
                          if old_mods.get(k) != new_mods.get(k)}

        def _svc_map(manifest: Dict[str, Any]) -> Dict[str, str]:
            return {s["name"]: s.get("status", "") for s in manifest.get("services", [])}

        old_svcs = _svc_map(old)
        new_svcs = _svc_map(new)
        svc_changes = {k: {"old": old_svcs.get(k), "new": new_svcs.get(k)}
                       for k in set(old_svcs) | set(new_svcs)
                       if old_svcs.get(k) != new_svcs.get(k)}

        return {
            "from": old.get("generated_at"),
            "to": new.get("generated_at"),
            "added_packages": added,
            "removed_packages": removed,
            "changed_packages": changed,
            "kernel_changes": kernel_changes,
            "service_changes": svc_changes,
        }

    @staticmethod
    def print_diff(diff_result: Dict[str, Any]) -> None:
        """Print a human-readable diff to stdout."""
        print("=" * 60)
        print("  AURA OS — Manifest Diff")
        print(f"  From : {diff_result.get('from', '?')}")
        print(f"  To   : {diff_result.get('to', '?')}")
        print("=" * 60)

        for pkg in diff_result.get("added_packages", []):
            print(f"  + {pkg['name']} {pkg.get('version', '')}")
        for pkg in diff_result.get("removed_packages", []):
            print(f"  - {pkg['name']} {pkg.get('version', '')}")
        for pkg in diff_result.get("changed_packages", []):
            print(f"  ~ {pkg['name']}  {pkg['old']} → {pkg['new']}")

        for name, chg in diff_result.get("kernel_changes", {}).items():
            print(f"  K {name}: {chg['old']} → {chg['new']}")
        for name, chg in diff_result.get("service_changes", {}).items():
            print(f"  S {name}: {chg['old']} → {chg['new']}")

        total = (len(diff_result.get("added_packages", [])) +
                 len(diff_result.get("removed_packages", [])) +
                 len(diff_result.get("changed_packages", [])) +
                 len(diff_result.get("kernel_changes", {})) +
                 len(diff_result.get("service_changes", {})))
        if total == 0:
            print("  (no changes detected)")
        print()

    # ------------------------------------------------------------------
    # Data collectors
    # ------------------------------------------------------------------

    def _aura_version(self) -> str:
        try:
            from aura_os import __version__
            return __version__
        except Exception:
            return "unknown"

    def _collect_packages(self) -> List[Dict[str, Any]]:
        try:
            from aura_os.pkg.manager import PackageManager
            pm = PackageManager()
            return pm.list_packages()
        except Exception:
            return []

    def _collect_kernel_modules(self) -> Dict[str, str]:
        import importlib
        modules = [
            "aura_os.kernel.process", "aura_os.kernel.service",
            "aura_os.kernel.syslog", "aura_os.kernel.scheduler",
            "aura_os.kernel.memory", "aura_os.kernel.network",
            "aura_os.kernel.events", "aura_os.kernel.cron",
            "aura_os.kernel.clipboard", "aura_os.kernel.plugins",
            "aura_os.kernel.secrets", "aura_os.kernel.ipc",
        ]
        result = {}
        for mod in modules:
            name = mod.split(".")[-1]
            try:
                importlib.import_module(mod)
                result[name] = "ok"
            except ImportError as exc:
                result[name] = f"error: {exc}"
        return result

    def _collect_services(self) -> List[Dict[str, Any]]:
        try:
            from aura_os.kernel.service import ServiceManager
            sm = ServiceManager()
            return sm.list_services()
        except Exception:
            return []

    def _collect_filesystem(self) -> Dict[str, Any]:
        try:
            import shutil
            total, used, free = shutil.disk_usage(
                self._home if os.path.exists(self._home) else os.path.expanduser("~")
            )
            return {
                "aura_home": self._home,
                "aura_home_exists": os.path.isdir(self._home),
                "disk_total_mb": round(total / (1 << 20)),
                "disk_free_mb": round(free / (1 << 20)),
            }
        except Exception:
            return {"aura_home": self._home}


# ---------------------------------------------------------------------------
# CLI command wrapper
# ---------------------------------------------------------------------------

class BuildCommand:
    """``aura build`` — build and manifest utilities."""

    def execute(self, args, eal) -> int:
        build_cmd = getattr(args, "build_cmd", None)
        home = os.environ.get("AURA_HOME", os.path.expanduser("~/.aura"))

        if build_cmd == "manifest":
            return self._do_manifest(args, home)
        if build_cmd == "diff":
            return self._do_diff(args)
        if build_cmd == "validate":
            from aura_os.build.validator import Validator
            v = Validator(home)
            results = v.run_all()
            v.print_report(results)
            return 0 if v.all_passed(results) else 1

        # Default: print summary
        builder = ManifestBuilder(home)
        builder.print_summary()
        return 0

    # ------------------------------------------------------------------

    def _do_manifest(self, args, home: str) -> int:
        builder = ManifestBuilder(home)
        output = getattr(args, "output", None)
        if output:
            builder.save(output)
            print(f"[build] Manifest saved to {output}")
        else:
            builder.print_summary()
        return 0

    def _do_diff(self, args) -> int:
        old_path = getattr(args, "old", None)
        new_path = getattr(args, "new", None)
        if not old_path or not new_path:
            print("[build] Usage: aura build diff <old.json> <new.json>")
            return 1
        try:
            with open(old_path, encoding="utf-8") as fh:
                old = json.load(fh)
            with open(new_path, encoding="utf-8") as fh:
                new = json.load(fh)
        except (OSError, json.JSONDecodeError) as exc:
            print(f"[build] Cannot load manifest: {exc}")
            return 1
        diff = ManifestBuilder.diff(old, new)
        ManifestBuilder.print_diff(diff)
        return 0
