"""Virtual filesystem abstraction for AURA OS.

Enhancements vs original:
- **Binary read/write**: ``read_bytes`` / ``write_bytes`` methods
- **Recursive listing**: ``ls`` now accepts a ``recursive`` flag
- **Atomic writes**: text and binary writes use a temp-file-then-rename
  pattern to prevent partial writes
- **Copy / move**: ``copy`` and ``move`` helpers
- **Search**: ``find`` by name glob pattern
- **Disk usage**: ``du`` returns total byte count for a subtree
"""

import fnmatch
import os
import stat
import tempfile
from typing import Dict, List


class VirtualFS:
    """A sandboxed filesystem view rooted at *base_dir*.

    All paths provided by callers are treated as relative to *base_dir*.
    Absolute paths supplied by the caller have their leading ``/`` stripped
    before resolution.  The resolved real path is checked against *base_dir*
    to prevent path-traversal escapes (``../../`` etc.).

    Default base directory: ``~/.aura/data/``
    """

    def __init__(self, base_dir: str = None):
        if base_dir is None:
            aura_home = os.environ.get("AURA_HOME", os.path.expanduser("~/.aura"))
            base_dir = os.path.join(aura_home, "data")
        self._base = os.path.realpath(os.path.abspath(base_dir))
        os.makedirs(self._base, exist_ok=True)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _safe_path(self, path: str) -> str:
        """Resolve *path* relative to base_dir and verify it does not escape.

        Raises :class:`PermissionError` if the resolved path is outside the
        sandbox.  Absolute paths that do not start with base_dir are always
        rejected.
        """
        if os.path.isabs(path):
            # Absolute paths must be inside the sandbox
            candidate = os.path.realpath(path)
        else:
            candidate = os.path.realpath(os.path.join(self._base, path))

        if not candidate.startswith(self._base + os.sep) and candidate != self._base:
            raise PermissionError(
                f"Path '{path}' resolves outside the VFS sandbox ({self._base})."
            )
        # Additional check using commonpath for robustness
        try:
            common = os.path.commonpath([self._base, candidate])
        except ValueError:
            common = ""
        if common != self._base:
            raise PermissionError(
                f"Path '{path}' resolves outside the VFS sandbox ({self._base})."
            )
        return candidate

    # ------------------------------------------------------------------
    # Public API — existence / metadata
    # ------------------------------------------------------------------

    def exists(self, path: str) -> bool:
        """Return True if *path* exists inside the sandbox."""
        try:
            return os.path.exists(self._safe_path(path))
        except PermissionError:
            return False

    def stat(self, path: str) -> Dict:
        """Return a dict with basic stat information for *path*."""
        full = self._safe_path(path)
        st = os.stat(full)
        return {
            "path": path,
            "size": st.st_size,
            "is_dir": stat.S_ISDIR(st.st_mode),
            "is_file": stat.S_ISREG(st.st_mode),
            "mtime": st.st_mtime,
        }

    # ------------------------------------------------------------------
    # Public API — read
    # ------------------------------------------------------------------

    def read(self, path: str) -> str:
        """Read and return text content of *path* (UTF-8)."""
        full = self._safe_path(path)
        with open(full, "r", encoding="utf-8") as fh:
            return fh.read()

    def read_bytes(self, path: str) -> bytes:
        """Read and return raw binary content of *path*."""
        full = self._safe_path(path)
        with open(full, "rb") as fh:
            return fh.read()

    # ------------------------------------------------------------------
    # Public API — write (atomic)
    # ------------------------------------------------------------------

    def write(self, path: str, content: str):
        """Atomically write text *content* to *path* (UTF-8).

        Parent directories are created as needed.
        Uses a temporary file + ``os.replace`` for crash-safety.
        """
        full = self._safe_path(path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        dir_path = os.path.dirname(full)
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", dir=dir_path, delete=False, suffix=".tmp"
        ) as tmp:
            tmp.write(content)
            tmp_path = tmp.name
        os.replace(tmp_path, full)

    def write_bytes(self, path: str, content: bytes):
        """Atomically write binary *content* to *path*.

        Parent directories are created as needed.
        """
        full = self._safe_path(path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        dir_path = os.path.dirname(full)
        with tempfile.NamedTemporaryFile(
            "wb", dir=dir_path, delete=False, suffix=".tmp"
        ) as tmp:
            tmp.write(content)
            tmp_path = tmp.name
        os.replace(tmp_path, full)

    def append(self, path: str, content: str):
        """Append text *content* to *path*, creating the file if needed."""
        full = self._safe_path(path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "a", encoding="utf-8") as fh:
            fh.write(content)

    # ------------------------------------------------------------------
    # Public API — delete / copy / move
    # ------------------------------------------------------------------

    def delete(self, path: str):
        """Delete the file at *path*."""
        full = self._safe_path(path)
        os.remove(full)

    def delete_tree(self, path: str):
        """Recursively delete *path* and all its contents."""
        import shutil
        full = self._safe_path(path)
        shutil.rmtree(full)

    def copy(self, src: str, dst: str):
        """Copy file *src* to *dst* within the sandbox."""
        import shutil
        full_src = self._safe_path(src)
        full_dst = self._safe_path(dst)
        os.makedirs(os.path.dirname(full_dst), exist_ok=True)
        shutil.copy2(full_src, full_dst)

    def move(self, src: str, dst: str):
        """Move (rename) *src* to *dst* within the sandbox."""
        import shutil
        full_src = self._safe_path(src)
        full_dst = self._safe_path(dst)
        os.makedirs(os.path.dirname(full_dst), exist_ok=True)
        shutil.move(full_src, full_dst)

    # ------------------------------------------------------------------
    # Public API — directory operations
    # ------------------------------------------------------------------

    def ls(self, path: str = "", recursive: bool = False) -> List[str]:
        """List entries in directory *path* (default: root of sandbox).

        Args:
            path: Relative path inside the sandbox.
            recursive: If True, return all files in the subtree as
                       sandbox-relative paths.
        """
        full = self._safe_path(path) if path else self._base
        if not os.path.isdir(full):
            raise NotADirectoryError(f"'{path}' is not a directory.")
        if not recursive:
            return sorted(os.listdir(full))
        # Recursive walk — return paths relative to base
        result = []
        for root, dirs, files in os.walk(full):
            dirs.sort()
            for fname in sorted(files):
                abs_path = os.path.join(root, fname)
                rel = os.path.relpath(abs_path, self._base)
                result.append(rel)
        return result

    def mkdir(self, path: str):
        """Create directory *path* (and parents) inside the sandbox."""
        full = self._safe_path(path)
        os.makedirs(full, exist_ok=True)

    # ------------------------------------------------------------------
    # Public API — search
    # ------------------------------------------------------------------

    def find(self, pattern: str, path: str = "") -> List[str]:
        """Find files matching *pattern* (glob-style) within *path*.

        Returns sandbox-relative paths.  Example::

            vfs.find("*.json")        # all JSON files
            vfs.find("*.log", "logs") # JSON files under logs/
        """
        base = self._safe_path(path) if path else self._base
        if not os.path.isdir(base):
            return []
        results = []
        for root, _dirs, files in os.walk(base):
            for fname in files:
                if fnmatch.fnmatch(fname, pattern):
                    abs_path = os.path.join(root, fname)
                    rel = os.path.relpath(abs_path, self._base)
                    results.append(rel)
        return sorted(results)

    # ------------------------------------------------------------------
    # Public API — disk usage
    # ------------------------------------------------------------------

    def du(self, path: str = "") -> int:
        """Return total byte size of all files under *path* (recursive).

        Returns 0 for an empty or non-existent directory.
        """
        full = self._safe_path(path) if path else self._base
        if not os.path.exists(full):
            return 0
        if os.path.isfile(full):
            return os.path.getsize(full)
        total = 0
        for root, _dirs, files in os.walk(full):
            for fname in files:
                try:
                    total += os.path.getsize(os.path.join(root, fname))
                except OSError:
                    pass
        return total

    @property
    def base_dir(self) -> str:
        """Absolute path of the sandbox root directory."""
        return self._base

