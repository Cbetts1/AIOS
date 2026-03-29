"""Virtual filesystem abstraction for AURA OS."""

import os
import stat
from typing import Dict, List, Optional


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
    # Public API
    # ------------------------------------------------------------------

    def exists(self, path: str) -> bool:
        """Return True if *path* exists inside the sandbox."""
        try:
            return os.path.exists(self._safe_path(path))
        except PermissionError:
            return False

    def read(self, path: str) -> str:
        """Read and return text content of *path*."""
        full = self._safe_path(path)
        with open(full, "r", encoding="utf-8") as fh:
            return fh.read()

    def write(self, path: str, content: str):
        """Write *content* to *path*, creating parent directories if needed."""
        full = self._safe_path(path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8") as fh:
            fh.write(content)

    def delete(self, path: str):
        """Delete the file at *path*."""
        full = self._safe_path(path)
        os.remove(full)

    def ls(self, path: str = "") -> List[str]:
        """List entries in directory *path* (default: root of sandbox)."""
        full = self._safe_path(path) if path else self._base
        if not os.path.isdir(full):
            raise NotADirectoryError(f"'{path}' is not a directory.")
        return sorted(os.listdir(full))

    def mkdir(self, path: str):
        """Create directory *path* (and parents) inside the sandbox."""
        full = self._safe_path(path)
        os.makedirs(full, exist_ok=True)

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

    @property
    def base_dir(self) -> str:
        """Absolute path of the sandbox root directory."""
        return self._base
