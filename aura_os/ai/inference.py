"""Local AI inference engine for AURA OS.

Supported runtimes (tried in order):
1. **ollama HTTP API** — fastest, zero-copy streaming, full parameter control
2. **ollama CLI** — fallback when HTTP API is unreachable
3. **llama.cpp** (llama-cli binary)
4. Helpful install instructions if nothing is available

New capabilities vs the original:
- ``temperature``, ``top_p``, ``top_k`` parameter forwarding
- Configurable ``system`` prompt for personas / context injection
- Automatic retry with exponential back-off (3 attempts by default)
- Streaming output support via :meth:`stream`
- Timeout is per-attempt; total wall-time = timeout × retries
"""

import json
import os
import subprocess
import shutil
import time
import urllib.error
import urllib.request
from typing import Iterator, Optional

from .model_manager import ModelManager


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

_DEFAULT_OLLAMA_URL = "http://localhost:11434"


class LocalInference:
    """Runs prompts through a locally available AI runtime.

    Tries runtimes in order:
    ollama HTTP API → ollama CLI → llama-cli → fallback message.
    """

    def __init__(
        self,
        model_manager: ModelManager = None,
        ollama_url: str = None,
        retries: int = 3,
        retry_delay: float = 1.0,
    ):
        self._mm = model_manager or ModelManager()
        self._ollama_url = (
            ollama_url
            or os.environ.get("OLLAMA_URL", _DEFAULT_OLLAMA_URL)
        ).rstrip("/")
        self._retries = max(1, retries)
        self._retry_delay = retry_delay

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def query(
        self,
        prompt: str,
        model: Optional[str] = None,
        max_tokens: int = 512,
        temperature: float = 0.7,
        top_p: float = 0.9,
        top_k: int = 40,
        system: Optional[str] = None,
    ) -> str:
        """Run *prompt* through the best available local runtime.

        Args:
            prompt: User prompt text.
            model: Model name or file path override.
            max_tokens: Maximum number of tokens to generate.
            temperature: Sampling temperature (0.0–2.0).
            top_p: Nucleus-sampling probability threshold.
            top_k: Top-K candidates per token step.
            system: Optional system/instruction prompt prepended to context.

        Returns:
            The model response as a string, or an instructional message
            if no runtime is available.
        """
        last_error = _INSTALL_HINT
        for attempt in range(self._retries):
            try:
                result = self._query_once(
                    prompt, model, max_tokens, temperature, top_p, top_k, system
                )
                return result
            except _RetryableError as exc:
                last_error = str(exc)
                if attempt < self._retries - 1:
                    time.sleep(self._retry_delay * (2 ** attempt))
        return last_error

    def stream(
        self,
        prompt: str,
        model: Optional[str] = None,
        max_tokens: int = 512,
        temperature: float = 0.7,
        top_p: float = 0.9,
        top_k: int = 40,
        system: Optional[str] = None,
    ) -> Iterator[str]:
        """Yield response tokens/chunks as they arrive from the model.

        Falls back to yielding the full :meth:`query` result in one chunk
        when the runtime does not support streaming (llama.cpp CLI).

        Usage::

            for chunk in engine.stream("Explain quantum computing"):
                print(chunk, end="", flush=True)
        """
        runtime = self._mm.get_active_runtime()
        if runtime == "ollama" and self._is_ollama_http_available():
            yield from self._stream_ollama_http(
                prompt, model, max_tokens, temperature, top_p, top_k, system
            )
        else:
            yield self.query(
                prompt, model, max_tokens, temperature, top_p, top_k, system
            )

    # ------------------------------------------------------------------
    # Internal dispatch
    # ------------------------------------------------------------------

    def _query_once(
        self,
        prompt: str,
        model: Optional[str],
        max_tokens: int,
        temperature: float,
        top_p: float,
        top_k: int,
        system: Optional[str],
    ) -> str:
        runtime = self._mm.get_active_runtime()

        if runtime == "ollama":
            if self._is_ollama_http_available():
                return self._query_ollama_http(
                    prompt, model, max_tokens, temperature, top_p, top_k, system
                )
            return self._query_ollama_cli(prompt, model, max_tokens)

        if runtime == "llama.cpp":
            return self._query_llama_cpp(prompt, model, max_tokens)

        return _INSTALL_HINT

    # ------------------------------------------------------------------
    # Ollama HTTP backend (preferred)
    # ------------------------------------------------------------------

    def _is_ollama_http_available(self) -> bool:
        """Return True if the Ollama HTTP API is reachable."""
        try:
            req = urllib.request.urlopen(
                f"{self._ollama_url}/api/tags", timeout=3
            )
            req.close()
            return True
        except Exception:
            return False

    def _query_ollama_http(
        self,
        prompt: str,
        model: Optional[str],
        max_tokens: int,
        temperature: float,
        top_p: float,
        top_k: int,
        system: Optional[str],
    ) -> str:
        """Query the Ollama HTTP API (non-streaming)."""
        target_model = model or self._default_ollama_model_http()
        if not target_model:
            return (
                "[aura ai] Ollama is running but no models are available.\n"
                "Run: ollama pull mistral"
            )

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload = json.dumps({
            "model": target_model,
            "messages": messages,
            "stream": False,
            "options": {
                "num_predict": max_tokens,
                "temperature": temperature,
                "top_p": top_p,
                "top_k": top_k,
            },
        }).encode()

        try:
            req = urllib.request.Request(
                f"{self._ollama_url}/api/chat",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=120) as resp:
                body = json.loads(resp.read().decode())
                return body.get("message", {}).get("content", "").strip()
        except urllib.error.URLError as exc:
            raise _RetryableError(f"[aura ai] Ollama HTTP error: {exc}") from exc
        except (KeyError, json.JSONDecodeError) as exc:
            return f"[aura ai] Unexpected Ollama response: {exc}"

    def _stream_ollama_http(
        self,
        prompt: str,
        model: Optional[str],
        max_tokens: int,
        temperature: float,
        top_p: float,
        top_k: int,
        system: Optional[str],
    ) -> Iterator[str]:
        """Stream tokens from the Ollama HTTP API."""
        target_model = model or self._default_ollama_model_http()
        if not target_model:
            yield "[aura ai] No ollama model available. Run: ollama pull mistral"
            return

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload = json.dumps({
            "model": target_model,
            "messages": messages,
            "stream": True,
            "options": {
                "num_predict": max_tokens,
                "temperature": temperature,
                "top_p": top_p,
                "top_k": top_k,
            },
        }).encode()

        try:
            req = urllib.request.Request(
                f"{self._ollama_url}/api/chat",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=180) as resp:
                for raw_line in resp:
                    line = raw_line.decode().strip()
                    if not line:
                        continue
                    try:
                        chunk = json.loads(line)
                        token = chunk.get("message", {}).get("content", "")
                        if token:
                            yield token
                        if chunk.get("done"):
                            break
                    except json.JSONDecodeError:
                        continue
        except Exception as exc:
            yield f"\n[aura ai] Stream error: {exc}"

    def _default_ollama_model_http(self) -> Optional[str]:
        """Return the first model name from the Ollama HTTP /api/tags."""
        try:
            with urllib.request.urlopen(
                f"{self._ollama_url}/api/tags", timeout=5
            ) as resp:
                data = json.loads(resp.read().decode())
                models = data.get("models", [])
                if models:
                    return models[0].get("name")
        except Exception:
            pass
        return None

    # ------------------------------------------------------------------
    # Ollama CLI backend (fallback)
    # ------------------------------------------------------------------

    def _query_ollama_cli(
        self, prompt: str, model: Optional[str], max_tokens: int
    ) -> str:
        """Query ollama via its CLI (fallback when HTTP API is unavailable)."""
        ollama_bin = shutil.which("ollama")
        if not ollama_bin:
            return _INSTALL_HINT

        target_model = model or self._default_ollama_model_cli()
        if not target_model:
            return (
                "[aura ai] Ollama is installed but no models are available.\n"
                "Run: ollama pull mistral"
            )

        cmd = [ollama_bin, "run", target_model, prompt]
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=120,
            )
            if result.returncode == 0:
                return result.stdout.strip()
            raise _RetryableError(
                f"[aura ai] Ollama CLI error: {result.stderr.strip()}"
            )
        except subprocess.TimeoutExpired as exc:
            raise _RetryableError("[aura ai] Ollama timed out.") from exc
        except OSError:
            return "[aura ai] Failed to run ollama: binary not accessible"

    def _default_ollama_model_cli(self) -> Optional[str]:
        """Return the first model listed by ``ollama list``."""
        ollama_bin = shutil.which("ollama")
        if not ollama_bin:
            return None
        try:
            result = subprocess.run(
                [ollama_bin, "list"],
                capture_output=True, text=True, timeout=10,
            )
            for line in result.stdout.strip().splitlines()[1:]:
                parts = line.split()
                if parts:
                    return parts[0]
        except (subprocess.SubprocessError, OSError):
            pass
        return None

    # ------------------------------------------------------------------
    # llama.cpp backend
    # ------------------------------------------------------------------

    def _query_llama_cpp(
        self, prompt: str, model: Optional[str], max_tokens: int
    ) -> str:
        """Query llama.cpp via its llama-cli binary."""
        llama_bin = shutil.which("llama-cli")
        if not llama_bin:
            return _INSTALL_HINT

        model_path = model or self._first_local_model()
        if not model_path:
            return (
                "[aura ai] llama-cli is installed but no model files found "
                "in ~/.aura/models/.\nPlace a .gguf model file there and try again."
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
                cmd, capture_output=True, text=True, timeout=180,
            )
            if result.returncode == 0:
                return result.stdout.strip()
            raise _RetryableError(
                f"[aura ai] llama-cli error: {result.stderr.strip()}"
            )
        except subprocess.TimeoutExpired as exc:
            raise _RetryableError("[aura ai] llama-cli timed out.") from exc
        except OSError:
            return "[aura ai] Failed to run llama-cli: binary not accessible"

    def _first_local_model(self) -> Optional[str]:
        """Return the path to the first discovered local model file."""
        models = self._mm.list_models()
        return models[0] if models else None


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


class _RetryableError(Exception):
    """Raised by backends to signal a transient failure worth retrying."""
