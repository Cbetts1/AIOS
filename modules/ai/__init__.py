"""
AI Module — Offline-First Assistant
Tries to use a local GGUF model via llama-cpp-python if available,
otherwise falls back to a deterministic rule-based assistant.
"""

import re
import json
import time
from pathlib import Path


class AIModule:
    """
    Offline AI assistant.

    Priority order:
      1. llama-cpp-python with a GGUF model found in ~/.aura/models/
      2. Rule-based response engine (always available)
    """

    MODEL_DIR_NAMES = ["models", "ai/models"]

    def __init__(self, env_map: dict, adapter):
        self.env = env_map
        self.adapter = adapter
        self._llm = None
        self._backend = "rule-based"
        self._model_path = self._find_model()
        if self._model_path:
            self._try_load_llm()

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def query(self, prompt: str) -> str:
        """Process *prompt* and return a response string."""
        if self._llm is not None:
            return self._llm_query(prompt)
        return self._rule_query(prompt)

    def backend(self) -> str:
        return self._backend

    def model_path(self):
        return self._model_path

    # ------------------------------------------------------------------ #
    # Model discovery & loading
    # ------------------------------------------------------------------ #

    def _find_model(self):
        """Search for a .gguf model file in known locations."""
        storage_root = Path(self.env.get("storage_root", Path.home() / ".aura"))
        search_dirs = [
            storage_root / "models",
            Path.home() / ".aura" / "models",
            Path("/usr/local/share/aura/models"),
        ]
        for d in search_dirs:
            if d.is_dir():
                for f in sorted(d.glob("*.gguf")):
                    return f
        return None

    def _try_load_llm(self):
        """Attempt to load the GGUF model with llama-cpp-python."""
        try:
            from llama_cpp import Llama
            self._llm = Llama(
                model_path=str(self._model_path),
                n_ctx=2048,
                n_threads=2,
                verbose=False,
            )
            self._backend = "llama-cpp"
        except ImportError:
            pass  # llama-cpp-python not installed — use fallback
        except Exception:
            pass  # model load failed — use fallback

    # ------------------------------------------------------------------ #
    # LLM inference
    # ------------------------------------------------------------------ #

    def _llm_query(self, prompt: str) -> str:
        try:
            out = self._llm(
                f"<|user|>\n{prompt}\n<|assistant|>\n",
                max_tokens=512,
                stop=["<|user|>", "</s>"],
            )
            return out["choices"][0]["text"].strip()
        except Exception as e:
            return f"[AI] LLM error: {e}"

    # ------------------------------------------------------------------ #
    # Rule-based fallback engine
    # ------------------------------------------------------------------ #

    _RULES = [
        # Code generation
        (r"\b(write|create|generate)\b.*\b(code|function|script|class)\b",
         "Here is a Python function template:\n\ndef my_function(args):\n    # TODO: implement\n    pass\n\nEdit it using: aura fs edit <filename>"),

        # File help
        (r"\b(how|where)\b.*(file|directory|folder|path)\b",
         "Use 'aura fs ls [path]' to list files, 'aura fs cat <file>' to view, 'aura fs edit <file>' to edit."),

        # Run help
        (r"\b(run|execute|launch)\b.*(script|program|file)\b",
         "Use 'aura run <file>' to run a script. Supported types: .py, .sh, .js"),

        # Git/repo
        (r"\b(git|repo|repository|commit|branch)\b",
         "Repo commands:\n  aura repo create <name>\n  aura repo list\n  aura repo status [path]"),

        # Package management
        (r"\b(install|package|pkg|apt|brew|pip|npm|remove|uninstall)\b",
         "Package commands:\n  aura pkg install <name>  — install a package\n  aura pkg remove <name>   — remove a package\n  aura pkg search <query>  — search the catalog\n  aura pkg catalog         — browse all packages\n  aura pkg list            — list installed packages\n  aura pkg info <name>     — package details"),

        # Process management
        (r"\b(process|pid|kill|terminate|running|top|htop|ps)\b",
         "Process commands:\n  aura ps            — list running processes\n  aura top           — top resource consumers\n  aura kill <pid>    — terminate a process\n  aura jobs          — list AURA background jobs"),

        # Shell
        (r"\b(shell|terminal|interactive|repl|prompt)\b",
         "Start the interactive shell with: aura shell\nFeatures: tab-completion, command history, AI assist (type ?), host shell pass-through (type !)"),

        # System info
        (r"\b(system|os|platform|info|hardware)\b",
         "Use 'aura sys info' for system details, 'aura sys caps' for capability flags, 'aura env' for full environment JSON."),

        # Help
        (r"\b(help|commands|usage)\b",
         "Run 'aura help' to see all available commands, or 'aura shell' for the interactive terminal."),

        # Automation
        (r"\b(automat|task|workflow|schedule|cron)\b",
         "Automation commands:\n  aura auto list\n  aura auto run <task>\n  aura auto create <name>"),

        # Greeting
        (r"^(hi|hello|hey|yo)\b",
         "Hello! I'm AURA's AI assistant. I'm integrated throughout the OS — ask me anything!\nTry: aura shell (interactive mode), aura pkg search <tool>, aura ps"),
    ]

    def _rule_query(self, prompt: str) -> str:
        p = prompt.lower()
        for pattern, response in self._RULES:
            if re.search(pattern, p):
                return response
        return (
            "I couldn't find a specific answer for that.\n"
            "Try 'aura help' for available commands, or describe your task differently.\n"
            f"(Backend: {self._backend} — no local model loaded)"
        )
