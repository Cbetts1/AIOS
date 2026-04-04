"""Local AI model detection and management for AURA OS.

Enhancements vs original:
- Detects Ollama HTTP API in addition to CLI binaries
- Reports model metadata (size, format, modified date) from Ollama API
- Supports ``pull_model`` to download models via Ollama HTTP API
- Returns richer runtime info dicts
"""

import json
import os
import shutil
import urllib.error
import urllib.request
from typing import Dict, List, Optional

_DEFAULT_OLLAMA_URL = "http://localhost:11434"


class ModelManager:
    """Detects available AI runtimes and local model files.

    Searches for runtimes in order: ollama HTTP API → ollama CLI →
    llama-cli (llama.cpp) → ctransformers (Python).
    Model files (``*.gguf``, ``*.bin``) are discovered in ``~/.aura/models/``.
    """

    MODEL_EXTENSIONS = (".gguf", ".bin")
    RUNTIME_BINARIES = {
        "ollama": "ollama",
        "llama.cpp": "llama-cli",
    }

    def __init__(self, models_dir: str = None, ollama_url: str = None):
        if models_dir is None:
            aura_home = os.environ.get("AURA_HOME", os.path.expanduser("~/.aura"))
            models_dir = os.path.join(aura_home, "models")
        self._models_dir = models_dir
        self._ollama_url = (
            ollama_url
            or os.environ.get("OLLAMA_URL", _DEFAULT_OLLAMA_URL)
        ).rstrip("/")
        os.makedirs(self._models_dir, exist_ok=True)

    # ------------------------------------------------------------------
    # Runtime detection
    # ------------------------------------------------------------------

    def detect_runtimes(self) -> Dict[str, Optional[str]]:
        """Return a dict mapping runtime name → path/status string (or None)."""
        found: Dict[str, Optional[str]] = {}

        # Ollama: check HTTP API first, then fall back to binary presence
        ollama_http = self._ollama_http_available()
        if ollama_http:
            found["ollama"] = f"http:{self._ollama_url}"
        else:
            found["ollama"] = shutil.which(self.RUNTIME_BINARIES["ollama"])

        # llama.cpp
        found["llama.cpp"] = shutil.which(self.RUNTIME_BINARIES["llama.cpp"])

        # ctransformers (Python package, no binary)
        try:
            import ctransformers  # type: ignore  # noqa: F401
            found["ctransformers"] = "python-package"
        except ImportError:
            found["ctransformers"] = None

        return found

    def get_active_runtime(self) -> Optional[str]:
        """Return the name of the first available runtime, or None."""
        runtimes = self.detect_runtimes()
        for name in ("ollama", "llama.cpp", "ctransformers"):
            if runtimes.get(name):
                return name
        return None

    def _ollama_http_available(self) -> bool:
        """Return True if the Ollama HTTP API responds."""
        try:
            req = urllib.request.urlopen(
                f"{self._ollama_url}/api/tags", timeout=3
            )
            req.close()
            return True
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Model listing (with metadata from Ollama HTTP when available)
    # ------------------------------------------------------------------

    def list_models(self) -> List[str]:
        """Return a list of model file paths found in the models directory."""
        models = []
        try:
            for fname in os.listdir(self._models_dir):
                if any(fname.endswith(ext) for ext in self.MODEL_EXTENSIONS):
                    models.append(os.path.join(self._models_dir, fname))
        except OSError:
            pass
        return sorted(models)

    def list_ollama_models(self) -> List[Dict]:
        """Return metadata dicts for models available in a running Ollama instance.

        Each dict contains: name, size, format, modified_at.
        Returns an empty list if Ollama is not reachable.
        """
        try:
            with urllib.request.urlopen(
                f"{self._ollama_url}/api/tags", timeout=5
            ) as resp:
                data = json.loads(resp.read().decode())
                result = []
                for m in data.get("models", []):
                    result.append({
                        "name": m.get("name", ""),
                        "size": m.get("size", 0),
                        "format": m.get("details", {}).get("format", ""),
                        "modified_at": m.get("modified_at", ""),
                    })
                return result
        except Exception:
            return []

    def pull_model(self, model_name: str) -> Dict:
        """Download *model_name* via the Ollama HTTP API.

        Returns ``{"ok": True}`` on success, ``{"ok": False, "error": ...}``
        on failure.  Requires Ollama to be running.
        """
        if not self._ollama_http_available():
            return {"ok": False, "error": "Ollama HTTP API is not available."}

        payload = json.dumps({"name": model_name, "stream": False}).encode()
        try:
            req = urllib.request.Request(
                f"{self._ollama_url}/api/pull",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=600) as resp:
                body = json.loads(resp.read().decode())
                if body.get("status") == "success" or "error" not in body:
                    return {"ok": True, "model": model_name}
                return {"ok": False, "error": body.get("error", "Unknown error")}
        except urllib.error.URLError as exc:
            return {"ok": False, "error": str(exc)}

    # ------------------------------------------------------------------
    # Model file validation
    # ------------------------------------------------------------------

    def load_model(self, model_path: str) -> Optional[str]:
        """Return *model_path* if the file exists, otherwise None.

        Actual model loading is delegated to the inference engine; this
        method simply validates that the path is accessible.
        """
        if os.path.isfile(model_path):
            return model_path
        candidate = os.path.join(self._models_dir, model_path)
        if os.path.isfile(candidate):
            return candidate
        return None
