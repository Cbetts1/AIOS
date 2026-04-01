"""Cross-platform clipboard management for AURA OS.

Works on Linux (xclip/xsel/wl-copy), macOS (pbcopy/pbpaste),
Android/Termux (termux-clipboard-*), and falls back to an
in-memory buffer when no native tool is available.
"""

import os
import shutil
import subprocess
import threading
from typing import Dict, List, Optional


class ClipboardManager:
    """Portable clipboard with history tracking.

    Detects the host platform's clipboard tool and delegates to it.
    Keeps a configurable-length history in memory.
    """

    def __init__(self, max_history: int = 50):
        self._lock = threading.Lock()
        self._history: List[str] = []
        self._max_history = max_history
        self._buffer: str = ""  # in-memory fallback
        self._backend = self._detect_backend()

    # ------------------------------------------------------------------
    # Backend detection
    # ------------------------------------------------------------------

    @staticmethod
    def _detect_backend() -> str:
        """Return the name of the clipboard backend to use."""
        # macOS
        if shutil.which("pbcopy"):
            return "pbcopy"
        # Termux / Android
        if shutil.which("termux-clipboard-set"):
            return "termux"
        # Wayland
        if shutil.which("wl-copy") and os.environ.get("WAYLAND_DISPLAY"):
            return "wayland"
        # X11
        if shutil.which("xclip"):
            return "xclip"
        if shutil.which("xsel"):
            return "xsel"
        return "memory"

    # ------------------------------------------------------------------
    # Copy / paste
    # ------------------------------------------------------------------

    def copy(self, text: str) -> Dict:
        """Copy *text* to the clipboard.  Returns status dict."""
        with self._lock:
            self._history.append(text)
            if len(self._history) > self._max_history:
                self._history = self._history[-self._max_history:]
        try:
            self._write(text)
            return {"ok": True, "backend": self._backend, "length": len(text)}
        except Exception as exc:
            return {"ok": False, "backend": self._backend,
                    "error": str(exc)}

    def paste(self) -> Dict:
        """Read current clipboard contents.  Returns status dict."""
        try:
            text = self._read()
            return {"ok": True, "text": text, "backend": self._backend}
        except Exception as exc:
            return {"ok": False, "text": "", "backend": self._backend,
                    "error": str(exc)}

    # ------------------------------------------------------------------
    # History
    # ------------------------------------------------------------------

    def history(self, limit: int = 10) -> List[str]:
        """Return the most recent clipboard entries."""
        with self._lock:
            return list(self._history[-limit:])

    def clear_history(self):
        """Clear clipboard history."""
        with self._lock:
            self._history.clear()

    # ------------------------------------------------------------------
    # Internal platform adapters
    # ------------------------------------------------------------------

    def _write(self, text: str):
        """Write *text* to the system clipboard."""
        if self._backend == "pbcopy":
            subprocess.run(["pbcopy"], input=text.encode(),
                           check=True, capture_output=True)
        elif self._backend == "termux":
            subprocess.run(["termux-clipboard-set"], input=text.encode(),
                           check=True, capture_output=True)
        elif self._backend == "wayland":
            subprocess.run(["wl-copy"], input=text.encode(),
                           check=True, capture_output=True)
        elif self._backend == "xclip":
            subprocess.run(["xclip", "-selection", "clipboard"],
                           input=text.encode(), check=True,
                           capture_output=True)
        elif self._backend == "xsel":
            subprocess.run(["xsel", "--clipboard", "--input"],
                           input=text.encode(), check=True,
                           capture_output=True)
        else:
            self._buffer = text

    def _read(self) -> str:
        """Read from the system clipboard."""
        if self._backend == "pbcopy":
            r = subprocess.run(["pbpaste"], capture_output=True, check=True)
            return r.stdout.decode("utf-8", errors="replace")
        elif self._backend == "termux":
            r = subprocess.run(["termux-clipboard-get"],
                               capture_output=True, check=True)
            return r.stdout.decode("utf-8", errors="replace")
        elif self._backend == "wayland":
            r = subprocess.run(["wl-paste"], capture_output=True, check=True)
            return r.stdout.decode("utf-8", errors="replace")
        elif self._backend == "xclip":
            r = subprocess.run(["xclip", "-selection", "clipboard", "-o"],
                               capture_output=True, check=True)
            return r.stdout.decode("utf-8", errors="replace")
        elif self._backend == "xsel":
            r = subprocess.run(["xsel", "--clipboard", "--output"],
                               capture_output=True, check=True)
            return r.stdout.decode("utf-8", errors="replace")
        else:
            return self._buffer

    def info(self) -> Dict:
        """Return information about the clipboard backend."""
        return {
            "backend": self._backend,
            "history_size": len(self._history),
            "max_history": self._max_history,
        }
