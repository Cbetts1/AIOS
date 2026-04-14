"""Real interactive shell (REPL) for AURA OS.

AuraShell provides a real command-line interface backed by the host OS.
Commands are executed through the host's process manager — no simulation.

Features:
- Execute any real system command
- Built-in AURA commands via the engine router
- Shell variable assignment and expansion (VAR=value)
- Command history (via readline when available)
- Pipe (|) and output redirection (> / >>) support
- cd, export, alias, unalias, history, exit built-ins
- Script file execution
- Background jobs (& suffix)
"""

from __future__ import annotations

import os
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional


_READLINE_AVAILABLE = False
try:
    import readline  # noqa: F401
    _READLINE_AVAILABLE = True
except ImportError:
    pass


BANNER = """\
╔══════════════════════════════════════╗
║      AURA OS  —  Interactive Shell   ║
║  Type 'help' for built-in commands   ║
║  Type 'exit' or Ctrl-D to quit       ║
╚══════════════════════════════════════╝"""


class AuraShell:
    """Real interactive REPL shell for AURA OS.

    Args:
        eal: EAL instance for AURA built-in commands.
        router: CommandRouter for AURA sub-commands.
        prompt: Prompt string (default ``aura> ``).
        home: AURA_HOME path (defaults to ``~/.aura``).
    """

    def __init__(self, eal=None, router=None, prompt: str = "aura> ",
                 home: Optional[str] = None):
        self._eal = eal
        self._router = router
        self._prompt = prompt
        self._home = home or os.environ.get("AURA_HOME", os.path.expanduser("~/.aura"))

        self._cwd: str = os.getcwd()
        self._env: Dict[str, str] = dict(os.environ)
        self._aliases: Dict[str, str] = {}
        self._history: List[str] = []
        self._exit_flag = False
        self._last_exit_code: int = 0

        if _READLINE_AVAILABLE:
            self._setup_readline()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self) -> int:
        """Start the interactive REPL loop.  Returns exit code."""
        print(BANNER)
        print()
        while not self._exit_flag:
            try:
                line = input(self._build_prompt())
            except EOFError:
                print()
                break
            except KeyboardInterrupt:
                print("^C")
                continue
            line = line.strip()
            if not line:
                continue
            self._history.append(line)
            if _READLINE_AVAILABLE:
                readline.add_history(line)
            self._execute_line(line)
        return self._last_exit_code

    def run_script(self, path: str) -> int:
        """Execute a shell script file non-interactively."""
        try:
            with open(path, "r", encoding="utf-8") as fh:
                lines = fh.readlines()
        except OSError as exc:
            print(f"[shell] Cannot read script '{path}': {exc}", file=sys.stderr)
            return 1
        for raw in lines:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            self._execute_line(line)
            if self._exit_flag:
                break
        return self._last_exit_code

    def execute(self, line: str) -> int:
        """Execute a single command line and return exit code."""
        self._execute_line(line.strip())
        return self._last_exit_code

    # ------------------------------------------------------------------
    # Line execution
    # ------------------------------------------------------------------

    def _execute_line(self, line: str) -> None:
        # Strip inline comments
        if " #" in line:
            line = line[:line.index(" #")].rstrip()

        # Background execution
        background = False
        if line.endswith("&"):
            background = True
            line = line[:-1].rstrip()

        # Output redirect: command > file  or  command >> file
        redir_append = False
        redir_path: Optional[str] = None
        if ">>" in line:
            parts = line.split(">>", 1)
            line, redir_path = parts[0].rstrip(), parts[1].strip()
            redir_append = True
        elif ">" in line:
            parts = line.split(">", 1)
            line, redir_path = parts[0].rstrip(), parts[1].strip()

        # Pipe chain
        if "|" in line:
            self._run_pipe(line, redir_path, redir_append)
            return

        # Variable assignment: VAR=value
        if "=" in line and not line.startswith("("):
            stripped = line.strip()
            if stripped and not stripped[0].isspace():
                tokens = stripped.split(None, 1)
                if tokens and "=" in tokens[0] and tokens[0][0].isalpha():
                    self._handle_assignment(stripped)
                    return

        # Execute the single command
        self._run_command(line, redir_path, redir_append, background)

    def _handle_assignment(self, expr: str) -> None:
        key, _, val = expr.partition("=")
        key = key.strip()
        val = self._expand_vars(val.strip())
        self._env[key] = val
        os.environ[key] = val

    # ------------------------------------------------------------------
    # Pipe execution
    # ------------------------------------------------------------------

    def _run_pipe(self, line: str, redir_path: Optional[str], redir_append: bool) -> None:
        segments = [s.strip() for s in line.split("|")]
        procs = []
        prev_stdout = None
        for i, seg in enumerate(segments):
            is_last = i == len(segments) - 1
            try:
                tokens = shlex.split(self._expand_vars(seg))
            except ValueError as exc:
                print(f"[shell] Parse error: {exc}")
                return
            if not tokens:
                continue
            stdout = subprocess.PIPE if not is_last else (
                self._open_redir(redir_path, redir_append) if redir_path else None
            )
            try:
                proc = subprocess.Popen(
                    tokens,
                    stdin=prev_stdout,
                    stdout=stdout,
                    cwd=self._cwd,
                    env=self._env,
                )
                if prev_stdout:
                    prev_stdout.close()
                prev_stdout = proc.stdout
                procs.append(proc)
            except (OSError, FileNotFoundError) as exc:
                print(f"[shell] {exc}")
                return
        for proc in procs:
            proc.wait()
        if procs:
            self._last_exit_code = procs[-1].returncode

    # ------------------------------------------------------------------
    # Single command execution
    # ------------------------------------------------------------------

    def _run_command(self, line: str, redir_path: Optional[str],
                     redir_append: bool, background: bool) -> None:
        line = self._expand_vars(line)
        try:
            tokens = shlex.split(line)
        except ValueError as exc:
            print(f"[shell] Parse error: {exc}")
            return
        if not tokens:
            return

        # Resolve alias
        if tokens[0] in self._aliases:
            alias_line = self._aliases[tokens[0]] + " " + " ".join(tokens[1:])
            self._execute_line(alias_line.strip())
            return

        cmd = tokens[0]

        # Built-in commands
        if cmd == "exit":
            code = int(tokens[1]) if len(tokens) > 1 else 0
            self._last_exit_code = code
            self._exit_flag = True
            return
        if cmd == "cd":
            self._builtin_cd(tokens[1:])
            return
        if cmd == "export":
            self._builtin_export(tokens[1:])
            return
        if cmd == "alias":
            self._builtin_alias(tokens[1:])
            return
        if cmd == "unalias":
            if len(tokens) > 1:
                self._aliases.pop(tokens[1], None)
            return
        if cmd == "history":
            for i, h in enumerate(self._history[-50:], 1):
                print(f"  {i:4}  {h}")
            return
        if cmd in ("clear", "cls"):
            os.system("clear" if os.name != "nt" else "cls")
            return
        if cmd == "pwd":
            print(self._cwd)
            return
        if cmd == "echo":
            print(" ".join(tokens[1:]))
            return
        if cmd == "env":
            for k, v in sorted(self._env.items()):
                print(f"{k}={v}")
            return
        if cmd == "help":
            self._print_help()
            return

        # AURA router commands
        if self._router and cmd == "aura" and len(tokens) > 1:
            self._run_aura_command(tokens[1:])
            return

        # Real OS execution
        stdout_fh = self._open_redir(redir_path, redir_append) if redir_path else None
        try:
            if background:
                subprocess.Popen(
                    tokens, cwd=self._cwd, env=self._env,
                    stdout=stdout_fh or subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                print(f"[{os.getpid()}] {cmd}")
                self._last_exit_code = 0
            else:
                proc = subprocess.run(
                    tokens, cwd=self._cwd, env=self._env,
                    stdout=stdout_fh,
                )
                self._last_exit_code = proc.returncode
        except FileNotFoundError:
            print(f"[shell] command not found: {cmd}")
            self._last_exit_code = 127
        except PermissionError:
            print(f"[shell] Permission denied: {cmd}")
            self._last_exit_code = 126
        except OSError as exc:
            print(f"[shell] {exc}")
            self._last_exit_code = 1
        finally:
            if stdout_fh:
                stdout_fh.close()

    def _run_aura_command(self, args: List[str]) -> None:
        try:
            ns = self._router.dispatch(args, self._eal)
            self._last_exit_code = ns if isinstance(ns, int) else 0
        except Exception as exc:
            print(f"[shell] aura: {exc}")
            self._last_exit_code = 1

    # ------------------------------------------------------------------
    # Built-ins
    # ------------------------------------------------------------------

    def _builtin_cd(self, args: List[str]) -> None:
        target = args[0] if args else os.path.expanduser("~")
        target = self._expand_vars(target)
        try:
            os.chdir(target)
            self._cwd = os.getcwd()
            self._env["PWD"] = self._cwd
        except FileNotFoundError:
            print(f"[shell] cd: no such directory: {target}")
        except NotADirectoryError:
            print(f"[shell] cd: not a directory: {target}")
        except PermissionError:
            print(f"[shell] cd: permission denied: {target}")

    def _builtin_export(self, args: List[str]) -> None:
        for token in args:
            if "=" in token:
                k, _, v = token.partition("=")
                self._env[k] = v
                os.environ[k] = v
            elif token in self._env:
                os.environ[token] = self._env[token]

    def _builtin_alias(self, args: List[str]) -> None:
        if not args:
            for k, v in sorted(self._aliases.items()):
                print(f"alias {k}='{v}'")
            return
        for token in args:
            if "=" in token:
                k, _, v = token.partition("=")
                self._aliases[k] = v.strip("'\"")
            else:
                if token in self._aliases:
                    print(f"alias {token}='{self._aliases[token]}'")

    def _print_help(self) -> None:
        print("""
  AURA OS Shell — Built-in Commands
  ─────────────────────────────────
  cd [dir]            Change directory
  pwd                 Print working directory
  echo [text]         Print text
  env                 Show environment variables
  export VAR=value    Set environment variable
  alias [k=v]         Create or list command aliases
  unalias name        Remove an alias
  history             Show command history
  clear               Clear the screen
  help                Show this help
  exit [code]         Exit the shell

  Pipe syntax    : cmd1 | cmd2
  Redirect       : cmd > file   (overwrite)
                   cmd >> file  (append)
  Background     : cmd &
  Variable expand: $VAR or ${VAR}
  Assignment     : VAR=value
""")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _build_prompt(self) -> str:
        cwd_display = self._cwd.replace(os.path.expanduser("~"), "~")
        code_indicator = "" if self._last_exit_code == 0 else f"[{self._last_exit_code}] "
        return f"{code_indicator}{cwd_display} {self._prompt}"

    def _expand_vars(self, text: str) -> str:
        return os.path.expandvars(text)

    def _open_redir(self, path: Optional[str], append: bool):
        if not path:
            return None
        try:
            return open(path, "a" if append else "w", encoding="utf-8")  # noqa: SIM115
        except OSError as exc:
            print(f"[shell] Cannot open '{path}': {exc}")
            return None

    def _setup_readline(self) -> None:
        readline.set_completer_delims(" \t\n")
        readline.parse_and_bind("tab: complete")
        history_file = os.path.join(self._home, "shell_history")
        try:
            Path(self._home).mkdir(parents=True, exist_ok=True)
            readline.read_history_file(history_file)
        except (FileNotFoundError, OSError):
            pass
        import atexit
        atexit.register(self._save_history, history_file)

    def _save_history(self, path: str) -> None:
        try:
            readline.write_history_file(path)
        except OSError:
            pass


# ---------------------------------------------------------------------------
# CLI command wrapper
# ---------------------------------------------------------------------------

class ShellCommand:
    """``aura shell`` — start an interactive AURA shell."""

    def execute(self, args, eal) -> int:
        script = getattr(args, "script", None)
        shell = AuraShell(eal=eal)
        if script:
            return shell.run_script(script)
        return shell.run()
