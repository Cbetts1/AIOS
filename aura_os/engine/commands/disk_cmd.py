"""Disk usage / analysis command for AURA OS.

Provides ``aura disk`` with subcommands:
  df          — filesystem mount-point usage (like ``df -h``)
  du <path>   — directory / subtree usage
  top         — top-N largest directories under a given root
  vfs         — disk usage of the AURA VFS data sandbox
"""

from __future__ import annotations

import os
import shutil
from typing import List


def _fmt_bytes(n: int) -> str:
    """Return a human-readable byte count string (KiB/MiB/GiB)."""
    for unit, threshold in (("GiB", 1 << 30), ("MiB", 1 << 20), ("KiB", 1 << 10)):
        if n >= threshold:
            return f"{n / threshold:.1f} {unit}"
    return f"{n} B"


class DiskCommand:
    """Disk usage and filesystem analysis."""

    def execute(self, args, eal) -> int:
        sub = getattr(args, "disk_command", None)
        if sub == "df" or sub is None:
            return self._cmd_df()
        if sub == "du":
            return self._cmd_du(args.path, args.depth)
        if sub == "top":
            return self._cmd_top(args.path, args.limit)
        if sub == "vfs":
            return self._cmd_vfs()
        print(f"Unknown disk subcommand: {sub}")
        return 1

    # ------------------------------------------------------------------

    def _cmd_df(self) -> int:
        """Show disk usage for all mounted filesystems."""
        try:
            import psutil
            parts = psutil.disk_partitions(all=False)
            print(f"{'Filesystem':<30} {'Total':>10} {'Used':>10} {'Free':>10} {'Use%':>6}  Mount")
            print("-" * 75)
            for p in parts:
                try:
                    usage = psutil.disk_usage(p.mountpoint)
                    pct = f"{usage.percent:.1f}%"
                    print(
                        f"{p.device:<30} {_fmt_bytes(usage.total):>10} "
                        f"{_fmt_bytes(usage.used):>10} {_fmt_bytes(usage.free):>10} "
                        f"{pct:>6}  {p.mountpoint}"
                    )
                except PermissionError:
                    pass
        except ImportError:
            # Fallback: call system df
            import subprocess
            result = subprocess.run(["df", "-h"], capture_output=True, text=True)
            print(result.stdout)
            if result.returncode != 0:
                print(result.stderr)
                return 1
        return 0

    def _cmd_du(self, path: str, depth: int) -> int:
        """Show disk usage for a directory tree."""
        root = os.path.realpath(os.path.abspath(path or "."))
        if not os.path.exists(root):
            print(f"du: no such path: {root}")
            return 1

        if os.path.isfile(root):
            size = os.path.getsize(root)
            print(f"{_fmt_bytes(size):>10}  {root}")
            return 0

        entries: List[tuple] = []
        for name in sorted(os.listdir(root)):
            full = os.path.join(root, name)
            total = _du_path(full)
            entries.append((total, full))

        entries.sort(key=lambda x: x[0], reverse=True)
        for size, p in entries:
            print(f"{_fmt_bytes(size):>10}  {p}")

        total_root = _du_path(root)
        print(f"\n{'Total':>10}  {_fmt_bytes(total_root)}")
        return 0

    def _cmd_top(self, path: str, limit: int) -> int:
        """List the top-N largest items under *path*."""
        root = os.path.realpath(os.path.abspath(path or "."))
        if not os.path.isdir(root):
            print(f"top: not a directory: {root}")
            return 1

        items: List[tuple] = []
        for dirpath, dirs, files in os.walk(root):
            for fname in files:
                fp = os.path.join(dirpath, fname)
                try:
                    items.append((os.path.getsize(fp), fp))
                except OSError:
                    pass

        items.sort(key=lambda x: x[0], reverse=True)
        print(f"Top {limit} largest files under {root}:\n")
        for size, fp in items[:limit]:
            print(f"  {_fmt_bytes(size):>10}  {fp}")
        return 0

    def _cmd_vfs(self) -> int:
        """Show AURA VFS sandbox disk usage."""
        from aura_os.fs.vfs import VirtualFS
        vfs = VirtualFS()
        total = vfs.du()
        entries = []
        try:
            for name in sorted(os.listdir(vfs.base_dir)):
                full = os.path.join(vfs.base_dir, name)
                entries.append((_du_path(full), name))
        except OSError:
            pass

        print(f"AURA VFS sandbox: {vfs.base_dir}\n")
        entries.sort(key=lambda x: x[0], reverse=True)
        for size, name in entries:
            print(f"  {_fmt_bytes(size):>10}  {name}")
        print(f"\n{'Total':>12}  {_fmt_bytes(total)}")
        return 0


def _du_path(path: str) -> int:
    """Return total byte size of *path* (file or directory)."""
    if os.path.isfile(path):
        try:
            return os.path.getsize(path)
        except OSError:
            return 0
    total = 0
    for root, _dirs, files in os.walk(path):
        for fname in files:
            try:
                total += os.path.getsize(os.path.join(root, fname))
            except OSError:
                pass
    return total
