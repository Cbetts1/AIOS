"""Real interactive shell (REPL) for AURA OS.

AuraShell provides a real command-line interface backed by the host OS.
Commands are executed through the host's process manager — no simulation.

Features:
- Execute any real system command
- Built-in AURA commands via the engine router
- Shell variable assignment and expansion (VAR=value)
- Command history (via readline when available)
- Pipe (|) and output redirection (> / >>) support
- Background jobs (& suffix)
- Command chaining (;, &&, ||)
- Glob expansion (* ? [...])
- cd, export, alias, unalias, history, exit built-ins
- File-operation built-ins: ls, cat, head, tail, mkdir, rm, touch, cp, mv
- Search built-ins: grep, wc, which
- System built-ins: date, uname, hostname, uptime, whoami, id, ifconfig, ping
- Script file execution
- Tab completion for file paths (when readline is available)
"""

from __future__ import annotations

import datetime
import getpass
import glob as _glob
import os
import platform
import re
import shlex
import shutil
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


# ---------------------------------------------------------------------------
# AuraShell
# ---------------------------------------------------------------------------

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
        # Strip inline comments (space + # outside quotes — simple heuristic)
        if " #" in line:
            line = line[:line.index(" #")].rstrip()

        # Command chaining: ; && ||
        if any(op in line for op in ("&&", "||", ";")):
            self._run_chain(line)
            return

        # Background execution
        background = False
        if line.rstrip().endswith("&"):
            background = True
            line = line.rstrip()[:-1].rstrip()

        # Output redirect: command >> file  or  command > file
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
        stripped = line.strip()
        if stripped and not stripped[0].isspace():
            tokens_check = stripped.split(None, 1)
            if tokens_check and "=" in tokens_check[0] and tokens_check[0][0].isalpha():
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
    # Command chaining (;, &&, ||)
    # ------------------------------------------------------------------

    def _run_chain(self, line: str) -> None:
        """Handle command chains split by ;, &&, ||."""
        tokens = re.split(r"(&&|\|\||;)", line)
        tokens = [t.strip() for t in tokens]
        pending_op = ";"
        last_rc = 0
        for token in tokens:
            if token in ("&&", "||", ";"):
                pending_op = token
                continue
            if not token:
                continue
            if pending_op == "&&" and last_rc != 0:
                continue
            if pending_op == "||" and last_rc == 0:
                continue
            self._execute_line(token)
            last_rc = self._last_exit_code
        self._last_exit_code = last_rc

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
            tokens = self._expand_globs(tokens)
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

        tokens = self._expand_globs(tokens)

        # Resolve alias
        if tokens[0] in self._aliases:
            alias_line = self._aliases[tokens[0]] + " " + " ".join(tokens[1:])
            self._execute_line(alias_line.strip())
            return

        cmd = tokens[0]

        # ---- Shell built-ins ----
        rc = self._try_builtin(cmd, tokens, redir_path, redir_append)
        if rc is not None:
            self._last_exit_code = rc
            return

        # AURA router commands (e.g. "aura ps")
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
            from aura_os.engine.cli import build_parser
            parser = build_parser()
            parsed = parser.parse_args(args)
            rc = self._router.dispatch(parsed, self._eal)
            self._last_exit_code = rc if isinstance(rc, int) else 0
        except SystemExit:
            self._last_exit_code = 0
        except Exception as exc:
            print(f"[shell] aura: {exc}")
            self._last_exit_code = 1

    # ------------------------------------------------------------------
    # Built-in dispatcher
    # ------------------------------------------------------------------

    def _try_builtin(self, cmd: str, tokens: List[str],
                     redir_path: Optional[str], redir_append: bool) -> Optional[int]:
        """Attempt to handle *cmd* as a built-in.

        Returns the exit code if handled, or ``None`` if it should be passed
        to the host OS.
        """
        # ---- Shell control ----
        if cmd in ("exit", "quit"):
            code = int(tokens[1]) if len(tokens) > 1 else 0
            self._last_exit_code = code
            self._exit_flag = True
            return code
        if cmd == "cd":
            self._builtin_cd(tokens[1:])
            return self._last_exit_code
        if cmd == "export":
            self._builtin_export(tokens[1:])
            return 0
        if cmd == "set":
            self._builtin_set(tokens[1:])
            return 0
        if cmd == "unset":
            for name in tokens[1:]:
                self._env.pop(name, None)
                os.environ.pop(name, None)
            return 0
        if cmd == "alias":
            self._builtin_alias(tokens[1:])
            return 0
        if cmd == "unalias":
            for name in tokens[1:]:
                self._aliases.pop(name, None)
            return 0
        if cmd == "history":
            for i, h in enumerate(self._history[-50:], 1):
                print(f"  {i:4}  {h}")
            return 0
        if cmd in ("clear", "cls"):
            print("\033[2J\033[H", end="", flush=True)
            return 0
        if cmd == "pwd":
            print(self._cwd)
            return 0
        if cmd == "echo":
            print(" ".join(tokens[1:]))
            return 0
        if cmd == "env":
            for k, v in sorted(self._env.items()):
                print(f"{k}={v}")
            return 0
        if cmd in ("source", "."):
            script = tokens[1] if len(tokens) > 1 else None
            if not script:
                print("[shell] Usage: source <file>")
                return 1
            return self.run_script(script)
        if cmd == "help":
            self._print_help()
            return 0

        # ---- Navigation / files ----
        if cmd == "ls":
            return self._builtin_ls(tokens[1:])
        if cmd == "cat":
            return self._builtin_cat(tokens[1:], redir_path, redir_append)
        if cmd == "head":
            return self._builtin_head(tokens[1:])
        if cmd == "tail":
            return self._builtin_tail(tokens[1:])
        if cmd == "mkdir":
            return self._builtin_mkdir(tokens[1:])
        if cmd == "rm":
            return self._builtin_rm(tokens[1:])
        if cmd == "touch":
            return self._builtin_touch(tokens[1:])
        if cmd == "cp":
            return self._builtin_cp(tokens[1:])
        if cmd == "mv":
            return self._builtin_mv(tokens[1:])
        if cmd == "wc":
            return self._builtin_wc(tokens[1:])
        if cmd == "grep":
            return self._builtin_grep(tokens[1:])
        if cmd == "which":
            return self._builtin_which(tokens[1:])

        # ---- System info ----
        if cmd == "date":
            print(datetime.datetime.now().strftime("%a %b %d %H:%M:%S %Z %Y"))
            return 0
        if cmd == "uname":
            return self._builtin_uname(tokens[1:])
        if cmd == "hostname":
            print(platform.node())
            return 0
        if cmd == "uptime":
            return self._builtin_uptime()
        if cmd == "whoami":
            print(getpass.getuser())
            return 0
        if cmd == "id":
            user = getpass.getuser()
            uid = os.getuid() if hasattr(os, "getuid") else 0
            gid = os.getgid() if hasattr(os, "getgid") else 0
            print(f"uid={uid}({user}) gid={gid}")
            return 0
        if cmd == "ifconfig":
            return self._builtin_ifconfig()
        if cmd == "ping":
            return self._builtin_ping(tokens[1:])

        return None  # not a built-in

    # ------------------------------------------------------------------
    # Built-in implementations — shell control
    # ------------------------------------------------------------------

    def _builtin_cd(self, args: List[str]) -> None:
        target = args[0] if args else os.path.expanduser("~")
        target = self._expand_vars(target)
        target = os.path.expanduser(target)
        if not os.path.isabs(target):
            target = os.path.join(self._cwd, target)
        target = os.path.realpath(target)
        try:
            os.chdir(target)
            self._cwd = os.getcwd()
            self._env["PWD"] = self._cwd
            self._last_exit_code = 0
        except FileNotFoundError:
            print(f"[shell] cd: no such directory: {target}")
            self._last_exit_code = 1
        except NotADirectoryError:
            print(f"[shell] cd: not a directory: {target}")
            self._last_exit_code = 1
        except PermissionError:
            print(f"[shell] cd: permission denied: {target}")
            self._last_exit_code = 1

    def _builtin_export(self, args: List[str]) -> None:
        if not args:
            for k, v in sorted(self._env.items()):
                print(f"  {k}={v}")
            return
        for token in args:
            if "=" in token:
                k, _, v = token.partition("=")
                self._env[k] = v
                os.environ[k] = v
            elif token in self._env:
                os.environ[token] = self._env[token]

    def _builtin_set(self, args: List[str]) -> None:
        if not args:
            for k, v in sorted(self._env.items()):
                print(f"  {k}={v}")
            return
        for token in args:
            if "=" in token:
                k, _, v = token.partition("=")
                self._env[k] = v
                os.environ[k] = v

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
                else:
                    print(f"[shell] alias: {token}: not found")

    # ------------------------------------------------------------------
    # Built-in implementations — file operations
    # ------------------------------------------------------------------

    def _resolve(self, path: str) -> str:
        """Resolve *path* relative to the current working directory."""
        if os.path.isabs(path):
            return path
        return os.path.join(self._cwd, path)

    def _builtin_ls(self, args: List[str]) -> int:
        # Parse -a / -l flags
        show_hidden = "-a" in args
        long_fmt = "-l" in args
        paths = [a for a in args if not a.startswith("-")] or [self._cwd]
        rc = 0
        for p in paths:
            target = self._resolve(p)
            try:
                if os.path.isdir(target):
                    entries = sorted(os.listdir(target))
                    if not show_hidden:
                        entries = [e for e in entries if not e.startswith(".")]
                    if long_fmt:
                        for entry in entries:
                            full = os.path.join(target, entry)
                            stat = os.stat(full)
                            size = stat.st_size
                            is_dir = os.path.isdir(full)
                            suffix = "/" if is_dir else ""
                            print(f"  {'d' if is_dir else '-'}  {size:>10}  {entry}{suffix}")
                    else:
                        for entry in entries:
                            full = os.path.join(target, entry)
                            suffix = "/" if os.path.isdir(full) else ""
                            print(f"  {entry}{suffix}")
                else:
                    print(f"  {os.path.basename(target)}")
            except OSError as exc:
                print(f"ls: {exc}")
                rc = 1
        return rc

    def _builtin_cat(self, args: List[str],
                     redir_path: Optional[str], redir_append: bool) -> int:
        if not args:
            print("Usage: cat <file> [...]")
            return 1
        rc = 0
        out = self._open_redir(redir_path, redir_append) if redir_path else None
        try:
            for p in args:
                path = self._resolve(p)
                try:
                    with open(path, "r", encoding="utf-8", errors="replace") as fh:
                        content = fh.read()
                    if out:
                        out.write(content)
                    else:
                        print(content, end="")
                except OSError as exc:
                    print(f"cat: {exc}")
                    rc = 1
        finally:
            if out:
                out.close()
        return rc

    def _builtin_head(self, args: List[str]) -> int:
        n = 10
        paths = []
        i = 0
        while i < len(args):
            if args[i] in ("-n", "--lines") and i + 1 < len(args):
                try:
                    n = int(args[i + 1])
                except ValueError:
                    pass
                i += 2
            elif args[i].startswith("-") and args[i][1:].isdigit():
                n = int(args[i][1:])
                i += 1
            else:
                paths.append(args[i])
                i += 1
        if not paths:
            print("Usage: head [-n N] <file> [...]")
            return 1
        rc = 0
        for p in paths:
            path = self._resolve(p)
            try:
                with open(path, "r", encoding="utf-8", errors="replace") as fh:
                    for j, line in enumerate(fh):
                        if j >= n:
                            break
                        print(line, end="")
            except OSError as exc:
                print(f"head: {exc}")
                rc = 1
        return rc

    def _builtin_tail(self, args: List[str]) -> int:
        n = 10
        paths = []
        i = 0
        while i < len(args):
            if args[i] in ("-n", "--lines") and i + 1 < len(args):
                try:
                    n = int(args[i + 1])
                except ValueError:
                    pass
                i += 2
            elif args[i].startswith("-") and args[i][1:].isdigit():
                n = int(args[i][1:])
                i += 1
            else:
                paths.append(args[i])
                i += 1
        if not paths:
            print("Usage: tail [-n N] <file> [...]")
            return 1
        rc = 0
        for p in paths:
            path = self._resolve(p)
            try:
                with open(path, "r", encoding="utf-8", errors="replace") as fh:
                    lines = fh.readlines()
                for line in lines[-n:]:
                    print(line, end="")
            except OSError as exc:
                print(f"tail: {exc}")
                rc = 1
        return rc

    def _builtin_mkdir(self, args: List[str]) -> int:
        if not args:
            print("Usage: mkdir <dir> [...]")
            return 1
        rc = 0
        for p in args:
            if p.startswith("-"):
                continue  # ignore -p etc.; we always use makedirs
            path = self._resolve(p)
            try:
                os.makedirs(path, exist_ok=True)
            except OSError as exc:
                print(f"mkdir: {exc}")
                rc = 1
        return rc

    def _builtin_rm(self, args: List[str]) -> int:
        recursive = "-r" in args or "-rf" in args or "-fr" in args
        paths = [a for a in args if not a.startswith("-")]
        if not paths:
            print("Usage: rm [-r] <path> [...]")
            return 1
        rc = 0
        for p in paths:
            path = self._resolve(p)
            try:
                if os.path.isdir(path):
                    if recursive:
                        shutil.rmtree(path)
                    else:
                        print(f"rm: {path}: is a directory (use -r)")
                        rc = 1
                else:
                    os.remove(path)
            except OSError as exc:
                print(f"rm: {exc}")
                rc = 1
        return rc

    def _builtin_touch(self, args: List[str]) -> int:
        if not args:
            print("Usage: touch <file> [...]")
            return 1
        rc = 0
        for p in args:
            path = self._resolve(p)
            try:
                Path(path).touch()
            except OSError as exc:
                print(f"touch: {exc}")
                rc = 1
        return rc

    def _builtin_cp(self, args: List[str]) -> int:
        recursive = "-r" in args or "-R" in args
        paths = [a for a in args if not a.startswith("-")]
        if len(paths) < 2:
            print("Usage: cp [-r] <src> <dst>")
            return 1
        src = self._resolve(paths[0])
        dst = self._resolve(paths[1])
        try:
            if os.path.isdir(src):
                if recursive:
                    shutil.copytree(src, dst)
                else:
                    print(f"cp: {src}: is a directory (use -r)")
                    return 1
            else:
                shutil.copy2(src, dst)
        except OSError as exc:
            print(f"cp: {exc}")
            return 1
        return 0

    def _builtin_mv(self, args: List[str]) -> int:
        paths = [a for a in args if not a.startswith("-")]
        if len(paths) < 2:
            print("Usage: mv <src> <dst>")
            return 1
        src = self._resolve(paths[0])
        dst = self._resolve(paths[1])
        try:
            shutil.move(src, dst)
        except OSError as exc:
            print(f"mv: {exc}")
            return 1
        return 0

    def _builtin_wc(self, args: List[str]) -> int:
        if not args:
            print("Usage: wc <file> [...]")
            return 1
        rc = 0
        for p in args:
            path = self._resolve(p)
            try:
                with open(path, "r", encoding="utf-8", errors="replace") as fh:
                    content = fh.read()
                lc = content.count("\n")
                wc = len(content.split())
                cc = len(content)
                print(f"  {lc:6} {wc:6} {cc:6}  {p}")
            except OSError as exc:
                print(f"wc: {exc}")
                rc = 1
        return rc

    def _builtin_grep(self, args: List[str]) -> int:
        case_insensitive = "-i" in args
        show_line_nums = "-n" in args
        args_clean = [a for a in args if not a.startswith("-")]
        if len(args_clean) < 2:
            print("Usage: grep [-i] [-n] <pattern> <file> [...]")
            return 1
        pattern = args_clean[0]
        files = args_clean[1:]
        rc = 1  # 1 = no matches (grep convention)
        flags = re.IGNORECASE if case_insensitive else 0
        try:
            compiled = re.compile(pattern, flags)
        except re.error as exc:
            print(f"grep: invalid pattern: {exc}")
            return 2
        for p in files:
            path = self._resolve(p)
            try:
                with open(path, "r", encoding="utf-8", errors="replace") as fh:
                    for lineno, line in enumerate(fh, 1):
                        if compiled.search(line):
                            prefix = f"{lineno}:" if show_line_nums else ""
                            print(f"  {prefix}{line}", end="")
                            rc = 0
            except OSError as exc:
                print(f"grep: {exc}")
                rc = 2
        return rc

    def _builtin_which(self, args: List[str]) -> int:
        if not args:
            print("Usage: which <binary> [...]")
            return 1
        rc = 0
        for name in args:
            result = shutil.which(name)
            if result:
                print(result)
            else:
                print(f"[shell] which: {name}: not found")
                rc = 1
        return rc

    # ------------------------------------------------------------------
    # Built-in implementations — system info
    # ------------------------------------------------------------------

    def _builtin_uname(self, args: List[str]) -> int:
        u = platform.uname()
        flag = args[0] if args else "-s"
        if flag == "-a":
            print(f"{u.system} {u.node} {u.release} {u.version} {u.machine}")
        elif flag == "-r":
            print(u.release)
        elif flag == "-m":
            print(u.machine)
        elif flag == "-n":
            print(u.node)
        elif flag == "-s":
            print(u.system)
        else:
            print(u.system)
        return 0

    def _builtin_uptime(self) -> int:
        try:
            import psutil
            import time
            secs = time.time() - psutil.boot_time()
            days = int(secs // 86400)
            hours = int((secs % 86400) // 3600)
            mins = int((secs % 3600) // 60)
            parts = []
            if days:
                parts.append(f"{days}d")
            parts.append(f"{hours}h {mins}m")
            print(f"  up {', '.join(parts)}")
            return 0
        except ImportError:
            pass
        # Fallback: read /proc/uptime on Linux
        try:
            with open("/proc/uptime", "r") as fh:
                secs = float(fh.read().split()[0])
            days = int(secs // 86400)
            hours = int((secs % 86400) // 3600)
            mins = int((secs % 3600) // 60)
            parts = []
            if days:
                parts.append(f"{days}d")
            parts.append(f"{hours}h {mins}m")
            print(f"  up {', '.join(parts)}")
            return 0
        except OSError:
            pass
        print("  uptime: unavailable")
        return 0

    def _builtin_ifconfig(self) -> int:
        try:
            from aura_os.net import NetworkManager
            nm = NetworkManager()
            for iface in nm.list_interfaces():
                status = "UP" if iface.get("is_up") else "DOWN"
                addrs = ", ".join(iface.get("addresses", [])) or "no address"
                print(f"  {iface['name']:<15} {status:<6}  {addrs}")
            return 0
        except Exception:
            pass
        # Fallback: run system ifconfig / ip
        for cmd in (["ip", "addr"], ["ifconfig"]):
            try:
                result = subprocess.run(cmd, capture_output=True, text=True)
                if result.returncode == 0:
                    print(result.stdout)
                    return 0
            except FileNotFoundError:
                continue
        print("ifconfig: unavailable")
        return 1

    def _builtin_ping(self, args: List[str]) -> int:
        if not args:
            print("Usage: ping <host> [-c count]")
            return 1
        host = args[0]
        count = 4
        if "-c" in args:
            idx = args.index("-c")
            if idx + 1 < len(args):
                try:
                    count = int(args[idx + 1])
                except ValueError:
                    pass
        try:
            from aura_os.net import NetworkManager
            nm = NetworkManager()
            result = nm.ping(host, count=count)
            if result.get("success"):
                print(f"  PING {host}: {result['packets_received']}/{result['packets_sent']} "
                      f"received, avg {result.get('avg_ms', 0):.1f} ms")
            else:
                print(f"  PING {host}: failed — host unreachable or ping not available")
            return 0 if result.get("success") else 1
        except Exception:
            pass
        # Fallback to system ping
        try:
            flag = "-c" if sys.platform != "win32" else "-n"
            result = subprocess.run(
                ["ping", flag, str(count), host],
                stdout=None, stderr=None,
            )
            return result.returncode
        except FileNotFoundError:
            print(f"ping: command not found")
            return 127

    # ------------------------------------------------------------------
    # Help
    # ------------------------------------------------------------------

    def _print_help(self) -> None:
        print("""
  AURA OS Shell — Built-in Commands
  ──────────────────────────────────────────────────────
  Navigation & Files:
    cd [dir]              Change directory
    pwd                   Print working directory
    ls [-a] [-l] [dir]    List directory contents
    cat <file> [...]      Print file contents
    head [-n N] <file>    Print first N lines (default 10)
    tail [-n N] <file>    Print last N lines (default 10)
    mkdir <dir> [...]     Create directory (with parents)
    rm [-r] <path> [...]  Remove file or directory
    touch <file> [...]    Create empty file
    cp [-r] <src> <dst>   Copy file or directory
    mv <src> <dst>        Move / rename file or directory
    wc <file> [...]       Count lines, words, chars
    grep [-i] [-n] <pat> <file>  Search for pattern in file

  Environment & Variables:
    export [VAR=val]      Set / list environment variables
    set [VAR=val]         Set shell variable
    unset <name>          Remove shell variable
    alias [name=cmd]      Set / list command aliases
    unalias <name>        Remove an alias
    echo [text]           Print text (supports $VAR expansion)
    env                   Show all environment variables

  System:
    whoami                Print current user
    id                    Print user id and group
    hostname              Print hostname
    date                  Print current date and time
    uname [-a|-r|-m|-n]   Print system information
    uptime                Show system uptime
    ifconfig              Show network interfaces
    ping <host> [-c N]    Ping a host
    which <binary>        Locate a binary in PATH
    clear                 Clear the terminal

  Shell Features:
    cmd1 | cmd2           Pipe output between commands
    cmd > file            Redirect output to file (overwrite)
    cmd >> file           Append output to file
    cmd &                 Run command in background
    cmd1 && cmd2          Run cmd2 only if cmd1 succeeds
    cmd1 || cmd2          Run cmd2 only if cmd1 fails
    cmd1 ; cmd2           Run both commands
    $VAR / ${VAR}         Environment variable expansion
    VAR=value             Assign shell variable
    source <file>         Execute commands from file

  AURA Commands (prefix with 'aura'):
    aura ps               List tracked processes
    aura sys              System status
    aura health           Health dashboard
    aura service list     List services
    aura net status       Network status
    aura log tail         View system log
    aura ai "<prompt>"    Query AI assistant
    (run 'aura --help' for the full command list)

    exit [code]           Exit the shell
    Ctrl-D                Exit the shell
    Ctrl-C                Cancel current input
""")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _build_prompt(self) -> str:
        cwd_display = self._cwd.replace(os.path.expanduser("~"), "~")
        code_indicator = "" if self._last_exit_code == 0 else f"[{self._last_exit_code}] "
        return f"{code_indicator}{cwd_display} {self._prompt}"

    def _expand_vars(self, text: str) -> str:
        """Expand $VAR and ${VAR} references."""
        def _replacer(match):
            var = match.group(1) or match.group(2)
            return self._env.get(var, os.environ.get(var, ""))
        return re.sub(r"\$\{(\w+)\}|\$(\w+)", _replacer, text)

    def _expand_globs(self, tokens: List[str]) -> List[str]:
        """Expand glob patterns in *tokens* relative to the current directory."""
        result = []
        for token in tokens:
            if any(c in token for c in ("*", "?", "[")):
                pattern = token if os.path.isabs(token) else os.path.join(self._cwd, token)
                matches = sorted(_glob.glob(pattern))
                if matches:
                    result.extend(matches)
                else:
                    result.append(token)
            else:
                result.append(token)
        return result

    def _open_redir(self, path: Optional[str], append: bool):
        if not path:
            return None
        full = path if os.path.isabs(path) else os.path.join(self._cwd, path)
        try:
            return open(full, "a" if append else "w", encoding="utf-8")
        except OSError as exc:
            print(f"[shell] Cannot open '{full}': {exc}")
            return None

    # ------------------------------------------------------------------
    # Readline setup (tab completion + history)
    # ------------------------------------------------------------------

    def _setup_readline(self) -> None:
        import atexit

        readline.set_completer_delims(" \t\n;|&>")
        readline.set_completer(self._completer)
        readline.parse_and_bind("tab: complete")

        history_file = os.path.join(self._home, "shell_history")
        try:
            Path(self._home).mkdir(parents=True, exist_ok=True)
            readline.read_history_file(history_file)
        except (FileNotFoundError, OSError):
            pass
        atexit.register(self._save_history, history_file)

    def _completer(self, text: str, state: int) -> Optional[str]:
        """Tab-completion: complete paths and built-in/AURA command names."""
        if state == 0:
            self._completion_matches = self._compute_completions(text)
        try:
            return self._completion_matches[state]
        except IndexError:
            return None

    def _compute_completions(self, text: str) -> List[str]:
        # If text contains a path separator, complete file paths
        if "/" in text or text.startswith("~") or text.startswith("."):
            return self._complete_path(text)

        # Get the full line to decide context
        try:
            line_buf = readline.get_line_buffer()
        except Exception:
            line_buf = text

        stripped = line_buf.lstrip()
        # First word: complete commands + built-ins
        if not stripped or stripped == text:
            return self._complete_command(text)

        # Subsequent words: complete file paths
        return self._complete_path(text)

    def _complete_path(self, text: str) -> List[str]:
        """Return file/directory completions for *text*."""
        expanded = os.path.expanduser(text)
        if not os.path.isabs(expanded):
            expanded = os.path.join(self._cwd, expanded)

        if os.path.isdir(expanded) and not text.endswith("/"):
            # Complete the directory itself
            return [text + "/"]

        parent = os.path.dirname(expanded)
        prefix = os.path.basename(expanded)
        try:
            entries = os.listdir(parent or self._cwd)
        except OSError:
            return []

        matches = []
        for entry in sorted(entries):
            if entry.startswith(prefix):
                full = os.path.join(parent, entry)
                suffix = "/" if os.path.isdir(full) else ""
                # Reconstruct with original prefix (preserve relative path)
                orig_dir = os.path.dirname(text)
                candidate = (os.path.join(orig_dir, entry) if orig_dir else entry) + suffix
                matches.append(candidate)
        return matches

    def _complete_command(self, text: str) -> List[str]:
        """Return command-name completions for *text*."""
        builtins = [
            "cd", "pwd", "ls", "cat", "head", "tail", "mkdir", "rm", "touch",
            "cp", "mv", "wc", "grep", "which", "echo", "env", "export", "set",
            "unset", "alias", "unalias", "history", "clear", "date", "uname",
            "hostname", "uptime", "whoami", "id", "ifconfig", "ping",
            "source", "exit", "quit", "help", "aura",
        ]
        path_cmds = []
        for directory in os.environ.get("PATH", "").split(os.pathsep):
            try:
                for entry in os.listdir(directory):
                    if entry.startswith(text):
                        path_cmds.append(entry)
            except OSError:
                continue

        all_cmds = sorted(set(
            [b for b in builtins if b.startswith(text)] + path_cmds
        ))
        return all_cmds

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
        from aura_os.main import _build_router
        script = getattr(args, "script", None)
        try:
            router = _build_router()
        except Exception:
            router = None
        shell = AuraShell(eal=eal, router=router)
        if script:
            return shell.run_script(script)
        return shell.run()
