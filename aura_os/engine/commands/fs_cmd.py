"""``aura fs`` command handler — file system operations."""

import os
import shutil
from pathlib import Path


class FsCommand:
    """File-system operations: ls, cat, find, mkdir, rm, edit.

    Operates on the real host filesystem (not the VFS sandbox) so that
    ``aura fs ls /tmp`` works as the user would expect.
    """

    def execute(self, args, eal) -> int:
        sub = getattr(args, "fs_command", None)

        if sub == "ls":
            return self._ls(getattr(args, "path", "."))

        if sub == "cat":
            return self._cat(args.file)

        if sub == "find":
            root = getattr(args, "root", ".")
            pattern = getattr(args, "pattern", "")
            return self._find(root, pattern)

        if sub == "mkdir":
            return self._mkdir(args.path)

        if sub == "rm":
            return self._rm(args.path)

        if sub == "edit":
            return self._edit(args.file)

        print("[fs] Unknown sub-command. Run 'aura fs --help'.")
        return 1

    # ------------------------------------------------------------------
    # Sub-commands
    # ------------------------------------------------------------------

    @staticmethod
    def _ls(path: str) -> int:
        p = Path(path).expanduser().resolve()
        if not p.exists():
            print(f"[fs] Path not found: {path}")
            return 1

        try:
            entries = sorted(p.iterdir(), key=lambda e: (not e.is_dir(), e.name.lower()))
        except PermissionError:
            print(f"[fs] Permission denied: {path}")
            return 1

        print(f"\n  {p}")
        print("  " + "─" * 40)
        for entry in entries:
            tag = "[D]" if entry.is_dir() else "   "
            suffix = "/" if entry.is_dir() else ""
            print(f"  {tag}  {entry.name}{suffix}")
        print()
        return 0

    @staticmethod
    def _cat(path: str) -> int:
        p = Path(path).expanduser().resolve()
        if not p.exists():
            print(f"[fs] File not found: {path}")
            return 1
        if p.is_dir():
            print(f"[fs] '{path}' is a directory. Use 'aura fs ls {path}'.")
            return 1
        try:
            print(p.read_text(encoding="utf-8"))
        except PermissionError:
            print(f"[fs] Permission denied: {path}")
            return 1
        return 0

    @staticmethod
    def _find(root: str, pattern: str) -> int:
        root_p = Path(root).expanduser().resolve()
        if not root_p.exists():
            print(f"[fs] Path not found: {root}")
            return 1

        pattern_lower = pattern.lower()
        matches = [
            fp for fp in root_p.rglob("*")
            if fp.is_file() and (not pattern_lower or pattern_lower in fp.name.lower())
        ]

        if not matches:
            print(f"[fs] No files matching '{pattern}' under {root}")
            return 0

        print(f"\n  Found {len(matches)} file(s):")
        for m in sorted(matches):
            print(f"    {m}")
        print()
        return 0

    @staticmethod
    def _mkdir(path: str) -> int:
        p = Path(path).expanduser().resolve()
        p.mkdir(parents=True, exist_ok=True)
        print(f"[fs] Created: {p}")
        return 0

    @staticmethod
    def _rm(path: str) -> int:
        p = Path(path).expanduser().resolve()
        if not p.exists():
            print(f"[fs] Not found: {path}")
            return 1

        if p.is_dir():
            shutil.rmtree(p)
        else:
            p.unlink()
        print(f"[fs] Deleted: {p}")
        return 0

    @staticmethod
    def _edit(path: str) -> int:
        p = Path(path).expanduser().resolve()
        if not p.exists():
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("")

        editor = os.environ.get("EDITOR")
        if editor and shutil.which(editor):
            os.execvp(editor, [editor, str(p)])
            return 0

        for editor_name in ("nano", "micro", "vim", "vi"):
            if shutil.which(editor_name):
                os.system(f"{editor_name} {p}")
                return 0

        print(f"[fs] No text editor found. File path: {p}")
        print("     Set the EDITOR environment variable to override.")
        return 1
