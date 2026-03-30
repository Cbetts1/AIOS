"""
Interactive Shell Module — REPL for AURA OS.

Provides a fully interactive terminal with:
  - Command history (persisted to disk)
  - Tab completion for AURA commands
  - Inline AI assist (prefix a query with ``?`` or ``ai:``)
  - Pass-through to the host shell for non-AURA commands
  - Job control basics (``bg``, ``jobs``, ``exit``)
"""

from __future__ import annotations

import os
import sys
import readline
import shlex
import subprocess
from pathlib import Path
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from core.engine import CommandEngine


# ──────────────────────────────────────────────────────────────────────────────
# Tab completer
# ──────────────────────────────────────────────────────────────────────────────

class _AuraCompleter:
    """readline tab-completer for AURA commands."""

    def __init__(self, commands: list[str]):
        self.commands = sorted(commands)
        self._matches: list[str] = []

    def complete(self, text: str, state: int):
        if state == 0:
            if text:
                self._matches = [c for c in self.commands if c.startswith(text)]
            else:
                self._matches = self.commands[:]
        return self._matches[state] if state < len(self._matches) else None


# ──────────────────────────────────────────────────────────────────────────────
# Shell module
# ──────────────────────────────────────────────────────────────────────────────

class ShellModule:
    """
    Interactive AURA OS shell.

    Wraps the CommandEngine in a readline-based REPL with history,
    tab completion, and inline AI assistance.
    """

    HISTORY_FILE = ".aura_history"
    BANNER = (
        "\n"
        "  ╔══════════════════════════════════════════════════╗\n"
        "  ║        AURA OS — Interactive Shell               ║\n"
        "  ║  Type 'help' for commands, '?' for AI assist     ║\n"
        "  ║  Use 'exit' or Ctrl-D to quit                    ║\n"
        "  ╚══════════════════════════════════════════════════╝\n"
    )

    def __init__(self, env_map: dict, adapter):
        self.env = env_map
        self.adapter = adapter
        self._engine: Optional[CommandEngine] = None
        self._ai = None
        self._process_mod = None
        self._history_path = Path(
            env_map.get("storage_root", Path.home() / ".aura")
        ) / self.HISTORY_FILE

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def start(self):
        """Enter the interactive REPL."""
        self._lazy_init()
        self._setup_readline()
        print(self.BANNER)

        while True:
            try:
                line = input("aura> ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\n[aura] Goodbye.")
                break

            if not line:
                continue

            # Builtin shell commands
            if line in ("exit", "quit", "logout"):
                print("[aura] Goodbye.")
                break

            if line == "clear":
                os.system("cls" if os.name == "nt" else "clear")
                continue

            if line == "jobs":
                self._ensure_process_mod()
                self._process_mod.jobs()
                continue

            # AI assist: lines starting with ? or ai:
            if line.startswith("?") or line.lower().startswith("ai:"):
                query = line.lstrip("?").strip()
                if line.lower().startswith("ai:"):
                    query = line[3:].strip()
                self._ai_query(query)
                continue

            # Host shell pass-through: lines starting with !
            if line.startswith("!"):
                self._host_shell(line[1:].strip())
                continue

            # AURA command dispatch
            try:
                tokens = shlex.split(line)
            except ValueError:
                tokens = line.split()

            if tokens:
                self._engine.run(tokens)

        self._save_history()

    # ------------------------------------------------------------------ #
    # Lazy initialization
    # ------------------------------------------------------------------ #

    def _lazy_init(self):
        if self._engine is None:
            from core.engine import CommandEngine
            self._engine = CommandEngine()

    def _ensure_process_mod(self):
        if self._process_mod is None:
            from modules.process import ProcessModule
            self._process_mod = ProcessModule(self.env, self.adapter)

    # ------------------------------------------------------------------ #
    # AI assist
    # ------------------------------------------------------------------ #

    def _ai_query(self, prompt: str):
        if not prompt:
            print("  [AI] Ask me anything! Example: ? how do I install git")
            return
        try:
            from modules.ai import AIModule
            if self._ai is None:
                self._ai = AIModule(self.env, self.adapter)
            response = self._ai.query(prompt)
            print(f"\n  AI > {response}\n")
        except Exception as e:
            print(f"  [AI] Error: {e}")

    # ------------------------------------------------------------------ #
    # Host shell pass-through
    # ------------------------------------------------------------------ #

    def _host_shell(self, cmd: str):
        """Execute a raw command on the host shell."""
        if not cmd:
            print("  Usage: !<command>  (e.g., !ls -la)")
            return
        try:
            tokens = shlex.split(cmd)
            subprocess.run(tokens)
        except ValueError:
            # shlex.split failed (e.g. unmatched quotes) — fall back safely
            print(f"  [shell] Could not parse command: {cmd}")
        except Exception as e:
            print(f"  [shell] Error: {e}")

    # ------------------------------------------------------------------ #
    # Readline / history
    # ------------------------------------------------------------------ #

    def _setup_readline(self):
        # Load history
        try:
            if self._history_path.exists():
                readline.read_history_file(str(self._history_path))
        except Exception:
            pass

        readline.set_history_length(2000)

        # Tab completion
        cmds = []
        if self._engine:
            cmds = list(self._engine.registry.names())
        # Add shell builtins
        cmds.extend(["exit", "quit", "clear", "jobs", "help"])
        completer = _AuraCompleter(cmds)
        readline.set_completer(completer.complete)
        readline.parse_and_bind("tab: complete")

    def _save_history(self):
        try:
            self._history_path.parent.mkdir(parents=True, exist_ok=True)
            readline.write_history_file(str(self._history_path))
        except Exception:
            pass
