"""Local AI model detection and management for AURA OS."""

import os
import shutil
from typing import Dict, List, Optional


class ModelManager:
    """Detects available AI runtimes and local model files.

    Searches for runtimes in order: ollama → llama-cli (llama.cpp) →
    ctransformers (Python).  Model files (``*.gguf``, ``*.bin``) are
    discovered in ``~/.aura/models/``.
    """

    MODEL_EXTENSIONS = (".gguf", ".bin")
    RUNTIME_BINARIES = {
        "ollama": "ollama",
        "llama.cpp": "llama-cli",
    }

    def __init__(self, models_dir: str = None):
        if models_dir is None:
            aura_home = os.environ.get("AURA_HOME", os.path.expanduser("~/.aura"))
            models_dir = os.path.join(aura_home, "models")
        self._models_dir = models_dir
        os.makedirs(self._models_dir, exist_ok=True)

    # ------------------------------------------------------------------
    # Runtime detection
    # ------------------------------------------------------------------

    def detect_runtimes(self) -> Dict[str, Optional[str]]:
        """Return a dict mapping runtime name → binary path (or None)."""
        found: Dict[str, Optional[str]] = {}
        for name, binary in self.RUNTIME_BINARIES.items():
            found[name] = shutil.which(binary)

        # Check for ctransformers (Python package, no binary)
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

    # ------------------------------------------------------------------
    # Model file discovery
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

    def load_model(self, model_path: str) -> Optional[str]:
        """Return *model_path* if the file exists, otherwise None.

        Actual model loading is delegated to the inference engine; this method
        simply validates that the path is accessible.
        """
        if os.path.isfile(model_path):
            return model_path
        # Try relative to models_dir
        candidate = os.path.join(self._models_dir, model_path)
        if os.path.isfile(candidate):
            return candidate
        return None
