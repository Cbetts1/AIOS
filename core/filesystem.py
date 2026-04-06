"""
Core File System Manager
Provides search, navigation, and editing operations via the EAL adapter.

.. deprecated::
    This legacy ``core/`` package is superseded by ``aura_os/fs/``.
    New code should import from ``aura_os.fs`` instead.
"""

import os
from pathlib import Path


class FileSystemManager:
    """
    High-level file system operations that work through the EAL adapter.
    """

    def __init__(self, adapter):
        self.adapter = adapter

    def ls(self, path="."):
        """List contents of *path*."""
        p = Path(path).expanduser().resolve()
        if not p.exists():
            print(f"[fs] Path not found: {path}")
            return

        try:
            entries = self.adapter.list_dir(p)
        except PermissionError:
            print(f"[fs] Permission denied: {path}")
            return

        print(f"\n  {p}")
        print("  " + "─" * 40)
        for name, is_dir in entries:
            tag = "/" if is_dir else ""
            print(f"  {'[D]' if is_dir else '   '}  {name}{tag}")
        print()

    def cat(self, path):
        """Print contents of *path*."""
        p = Path(path).expanduser().resolve()
        if not p.exists():
            print(f"[fs] File not found: {path}")
            return
        if p.is_dir():
            print(f"[fs] '{path}' is a directory. Use 'aura fs ls {path}'")
            return

        try:
            content = self.adapter.read_file(p)
            print(content)
        except PermissionError:
            print(f"[fs] Permission denied: {path}")

    def find(self, root=".", pattern=""):
        """Recursively search for files matching *pattern* under *root*."""
        root_p = Path(root).expanduser().resolve()
        if not root_p.exists():
            print(f"[fs] Path not found: {root}")
            return

        pattern = pattern.lower()
        matches = []
        for fp in root_p.rglob("*"):
            if fp.is_file():
                if not pattern or pattern in fp.name.lower():
                    matches.append(fp)

        if not matches:
            print(f"[fs] No files found matching '{pattern}' under {root}")
            return

        print(f"\n  Found {len(matches)} file(s):")
        for m in sorted(matches):
            print(f"    {m}")
        print()

    def mkdir(self, path):
        """Create directory *path*."""
        p = Path(path).expanduser().resolve()
        p.mkdir(parents=True, exist_ok=True)
        print(f"[fs] Created: {p}")

    def rm(self, path):
        """Delete file or directory at *path*."""
        p = Path(path).expanduser().resolve()
        if not p.exists():
            print(f"[fs] Not found: {path}")
            return
        self.adapter.delete(p)
        print(f"[fs] Deleted: {p}")

    def edit(self, path):
        """Open *path* in the best available text editor."""
        p = Path(path).expanduser().resolve()
        if not p.exists():
            # Create empty file
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("")

        # Try editors in order of preference
        for editor in ("nano", "micro", "vim", "vi", "notepad"):
            if self.adapter.which(editor):
                self.adapter.run([editor, str(p)], capture=False)
                return

        print(f"[fs] No text editor found. File path: {p}")
        print("     Set the EDITOR environment variable to override.")
