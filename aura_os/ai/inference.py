"""Local AI inference engine for AURA OS."""

import subprocess
import shutil
from typing import Optional

from .model_manager import ModelManager
from .knowledge import build_system_prompt, lookup as knowledge_lookup


_INSTALL_HINT = (
    "\n[aura ai] No local AI runtime detected.\n"
    "\nTo enable AI features, install one of the following:\n"
    "  • Ollama  : https://ollama.com  (recommended)\n"
    "      Install: curl -fsSL https://ollama.com/install.sh | sh\n"
    "      Then run: ollama pull mistral\n"
    "  • llama.cpp: https://github.com/ggerganov/llama.cpp\n"
    "      Build llama-cli and place it in your PATH.\n"
    "\nAfter installation, run: aura ai \"<your prompt>\"\n"
)


class LocalInference:
    """Runs prompts through a locally available AI runtime.

    Tries runtimes in order: ollama → llama-cli → fallback message.
    """

    def __init__(self, model_manager: ModelManager = None):
        self._mm = model_manager or ModelManager()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def query(self, prompt: str, model: Optional[str] = None, max_tokens: int = 512) -> str:
        """Run *prompt* through the best available local runtime.

        First checks the built-in knowledge base for a direct answer.
        If a local AI runtime is available, the prompt is enriched with
        AURA system context so the model can give informed answers.
        Falls back to an instructional message when no runtime exists.
        """
        # Try built-in knowledge base first for fast, offline answers
        kb_answer = knowledge_lookup(prompt)

        runtime = self._mm.get_active_runtime()

        if runtime == "ollama":
            enriched = self._enrich_prompt(prompt)
            return self._query_ollama(enriched, model, max_tokens)
        if runtime == "llama.cpp":
            enriched = self._enrich_prompt(prompt)
            return self._query_llama_cpp(enriched, model, max_tokens)

        # No LLM available — return knowledge-base answer or install hint
        if kb_answer:
            return kb_answer

        return _INSTALL_HINT

    @staticmethod
    def _enrich_prompt(user_prompt: str) -> str:
        """Prepend system context to *user_prompt* for richer LLM answers."""
        system = build_system_prompt()
        return (
            f"[SYSTEM]\n{system}\n\n"
            f"[USER]\n{user_prompt}"
        )

    # ------------------------------------------------------------------
    # Runtime-specific backends
    # ------------------------------------------------------------------

    def _query_ollama(self, prompt: str, model: Optional[str], max_tokens: int) -> str:
        """Query ollama via its CLI."""
        ollama_bin = shutil.which("ollama")
        if not ollama_bin:
            return _INSTALL_HINT

        target_model = model or self._default_ollama_model()
        if not target_model:
            return (
                "[aura ai] Ollama is installed but no models are available.\n"
                "Run: ollama pull mistral"
            )

        cmd = [ollama_bin, "run", target_model, prompt]
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120,
            )
            if result.returncode == 0:
                return result.stdout.strip()
            return f"[aura ai] Ollama error: {result.stderr.strip()}"
        except subprocess.TimeoutExpired:
            return "[aura ai] Ollama timed out."
        except OSError as exc:
            return f"[aura ai] Failed to run ollama: {exc}"

    def _default_ollama_model(self) -> Optional[str]:
        """Return the first model listed by ``ollama list``, or None."""
        ollama_bin = shutil.which("ollama")
        if not ollama_bin:
            return None
        try:
            result = subprocess.run(
                [ollama_bin, "list"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            lines = result.stdout.strip().splitlines()
            # Skip header line; first field of each row is the model name
            for line in lines[1:]:
                parts = line.split()
                if parts:
                    return parts[0]
        except (subprocess.SubprocessError, OSError, IndexError):
            pass
        return None

    def _query_llama_cpp(self, prompt: str, model: Optional[str], max_tokens: int) -> str:
        """Query llama.cpp via its llama-cli binary."""
        llama_bin = shutil.which("llama-cli")
        if not llama_bin:
            return _INSTALL_HINT

        model_path = model or self._first_local_model()
        if not model_path:
            return (
                "[aura ai] llama-cli is installed but no model files found in ~/.aura/models/.\n"
                "Place a .gguf model file there and try again."
            )

        cmd = [
            llama_bin,
            "-m", model_path,
            "-n", str(max_tokens),
            "-p", prompt,
            "--no-display-prompt",
        ]
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=180,
            )
            if result.returncode == 0:
                return result.stdout.strip()
            return f"[aura ai] llama-cli error: {result.stderr.strip()}"
        except subprocess.TimeoutExpired:
            return "[aura ai] llama-cli timed out."
        except OSError as exc:
            return f"[aura ai] Failed to run llama-cli: {exc}"

    def _first_local_model(self) -> Optional[str]:
        """Return the path to the first discovered local model file."""
        models = self._mm.list_models()
        return models[0] if models else None
