"""Real interactive shell (REPL) for AURA OS.

AuraShell provides a real command-line interface backed by the host OS.
Commands are executed through the host's process manager — no simulation.

Features:
- Execute any real system command
- Built-in AURA commands via the engine router (``aura <subcommand>``)
- 30+ shell built-ins: ls, cat, head, tail, mkdir, rm, touch, cp, mv, wc,
  grep, which, whoami, id, hostname, date, uname, uptime, ifconfig, ping,
  cd, pwd, echo, env, export, set, unset, alias, unalias, history, clear
- Command chaining: ;, &&, ||
- Shell variable assignment and expansion (VAR=value / $VAR / ${VAR})
- Glob expansion (*, ?, [...])
- Command history (via readline when available)
- Pipe (|) and output redirection (> / >>) support
- Script file execution
- Background jobs (& suffix)
"""

from __future__ import annotations

import glob as _glob_mod
import os
import re
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
        router: CommandRouter for ``aura <subcommand>`` dispatch.
        parser: argparse ArgumentParser (required alongside *router*).
        prompt: Prompt string (default ``aura> ``).
        home: AURA_HOME path (defaults to ``~/.aura``).
    """

    def __init__(self, eal=None, router=None, parser=None,
                 prompt: str = "aura> ", home: Optional[str] = None):
        self._eal = eal
        self._router = router
        self._parser = parser
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

        # Command chaining: ;  &&  ||
        # Must be checked before pipe/redirect so chained commands can use them.
        if re.search(r"(&&|\|\||;)", line):
            self._run_chain(line)
            return

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

    def _run_chain(self, line: str) -> None:
        """Execute commands separated by ``;``, ``&&``, or ``||``."""
        # Split preserving the operators
        tokens = re.split(r"(&&|\|\||;)", line)
        tokens = [t.strip() for t in tokens]
        pending_op = ";"  # first segment always runs
        for token in tokens:
            if token in ("&&", "||", ";"):
                pending_op = token
                continue
            if not token:
                continue
            if pending_op == "&&" and self._last_exit_code != 0:
                continue
            if pending_op == "||" and self._last_exit_code == 0:
                continue
            self._execute_line(token)  # recurse — handles all built-ins properly

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

        # Glob expansion on arguments (not the command name)
        if len(tokens) > 1:
            tokens = [tokens[0]] + self._expand_globs(tokens[1:])
        else:
            tokens = self._expand_globs(tokens)

        # Resolve alias
        if tokens[0] in self._aliases:
            alias_line = self._aliases[tokens[0]] + " " + " ".join(tokens[1:])
            self._execute_line(alias_line.strip())
            return

        cmd = tokens[0]

        # When a redirect is specified, open the target file so that all
        # built-in print() output lands in it instead of the terminal.
        import contextlib
        if redir_path and not background:
            redir_fh = self._open_redir(redir_path, redir_append)
        else:
            redir_fh = None
        stdout_ctx = (contextlib.redirect_stdout(redir_fh)
                      if redir_fh else contextlib.nullcontext())

        # ── Built-in + subprocess dispatch ─────────────────────────────
        # stdout_ctx redirects print() calls to the redirect file when
        # the user writes  cmd > file  or  cmd >> file.

        _handled = True  # will be set False if no built-in matches

        with stdout_ctx:
            if cmd in ("exit", "quit"):
                code = int(tokens[1]) if len(tokens) > 1 else 0
                self._last_exit_code = code
                self._exit_flag = True
            elif cmd == "cd":
                self._builtin_cd(tokens[1:])
            elif cmd == "export":
                self._builtin_export(tokens[1:])
            elif cmd == "alias":
                self._builtin_alias(tokens[1:])
            elif cmd == "unalias":
                if len(tokens) > 1:
                    self._aliases.pop(tokens[1], None)
            elif cmd == "set":
                self._builtin_set(tokens[1:])
            elif cmd == "unset":
                for name in tokens[1:]:
                    self._env.pop(name, None)
                    os.environ.pop(name, None)
            elif cmd == "history":
                for i, h in enumerate(self._history[-50:], 1):
                    print(f"  {i:4}  {h}")
            elif cmd in ("clear", "cls"):
                print("\033[2J\033[H", end="")
            elif cmd == "pwd":
                print(self._cwd)
            elif cmd == "echo":
                print(self._expand_vars(" ".join(tokens[1:])))
            elif cmd == "env":
                for k, v in sorted(self._env.items()):
                    print(f"{k}={v}")
            elif cmd == "help":
                self._print_help()
            # ── File system built-ins ─────────────────────────────────
            elif cmd == "ls":
                self._builtin_ls(tokens[1:])
            elif cmd == "cat":
                self._builtin_cat(tokens[1:])
            elif cmd == "head":
                self._builtin_head(tokens[1:])
            elif cmd == "tail":
                self._builtin_tail(tokens[1:])
            elif cmd == "mkdir":
                if len(tokens) < 2:
                    print("Usage: mkdir <dir>")
                else:
                    target = self._abspath(tokens[1])
                    try:
                        os.makedirs(target, exist_ok=True)
                        self._last_exit_code = 0
                    except OSError as exc:
                        print(f"mkdir: {exc}")
                        self._last_exit_code = 1
            elif cmd == "rm":
                self._builtin_rm(tokens[1:])
            elif cmd == "touch":
                if len(tokens) < 2:
                    print("Usage: touch <file>")
                else:
                    target = self._abspath(tokens[1])
                    try:
                        Path(target).touch()
                        self._last_exit_code = 0
                    except OSError as exc:
                        print(f"touch: {exc}")
                        self._last_exit_code = 1
            elif cmd == "cp":
                self._builtin_cp(tokens[1:])
            elif cmd == "mv":
                self._builtin_mv(tokens[1:])
            elif cmd == "wc":
                self._builtin_wc(tokens[1:])
            elif cmd == "grep":
                self._builtin_grep(tokens[1:])
            elif cmd == "which":
                if len(tokens) < 2:
                    print("Usage: which <binary>")
                else:
                    import shutil as _shutil
                    found = _shutil.which(tokens[1])
                    if found:
                        print(found)
                        self._last_exit_code = 0
                    else:
                        print(f"which: {tokens[1]}: not found")
                        self._last_exit_code = 1
            # ── System info built-ins ─────────────────────────────────
            elif cmd == "whoami":
                import getpass
                print(getpass.getuser())
                self._last_exit_code = 0
            elif cmd == "id":
                import getpass
                user = getpass.getuser()
                uid = os.getuid() if hasattr(os, "getuid") else 0
                gid = os.getgid() if hasattr(os, "getgid") else 0
                print(f"uid={uid}({user}) gid={gid}")
                self._last_exit_code = 0
            elif cmd == "hostname":
                import platform as _plat
                print(_plat.node())
                self._last_exit_code = 0
            elif cmd == "date":
                import datetime
                print(datetime.datetime.now().strftime("%a %b %d %H:%M:%S %Z %Y"))
                self._last_exit_code = 0
            elif cmd == "uname":
                import platform as _plat
                flag = tokens[1] if len(tokens) > 1 else "-s"
                u = _plat.uname()
                if flag == "-a":
                    print(f"{u.system} {u.node} {u.release} {u.version} {u.machine}")
                elif flag == "-r":
                    print(u.release)
                elif flag == "-m":
                    print(u.machine)
                elif flag == "-n":
                    print(u.node)
                else:
                    print(u.system)
                self._last_exit_code = 0
            elif cmd == "uptime":
                self._builtin_uptime()
            elif cmd == "ifconfig":
                self._builtin_ifconfig()
            elif cmd == "ping":
                self._builtin_ping(tokens[1:])
            # ── AURA router commands ───────────────────────────────────
            elif self._router and cmd == "aura" and len(tokens) > 1:
                self._run_aura_command(tokens[1:])
            else:
                _handled = False   # fall through to subprocess

        if redir_fh:
            redir_fh.close()

        if _handled:
            return

        # ── Real OS execution (no built-in matched) ───────────────────

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
        """Dispatch an ``aura <subcommand>`` call via the CLI router."""
        if not self._router or not self._parser:
            print("[shell] aura router not available in this shell session")
            self._last_exit_code = 1
            return
        try:
            parsed = self._parser.parse_args(args)
            rc = self._router.dispatch(parsed, self._eal)
            self._last_exit_code = rc if isinstance(rc, int) else 0
        except SystemExit:
            self._last_exit_code = 0
        except Exception as exc:
            print(f"[shell] aura: {exc}")
            self._last_exit_code = 1

    # ------------------------------------------------------------------
    # Built-in implementations
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
            print(f"cd: no such directory: {target}")
            self._last_exit_code = 1
        except NotADirectoryError:
            print(f"cd: not a directory: {target}")
            self._last_exit_code = 1
        except PermissionError:
            print(f"cd: permission denied: {target}")
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
        elif len(args) >= 2 and args[0].isidentifier():
            val = " ".join(args[1:])
            self._env[args[0]] = val
            os.environ[args[0]] = val
        else:
            print("Usage: set <name> <value>")

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
                    print(f"alias: {token}: not found")

    def _builtin_ls(self, args: List[str]) -> None:
        target_dir = args[0] if args else self._cwd
        target_dir = self._abspath(target_dir)
        try:
            entries = sorted(os.listdir(target_dir))
            for entry in entries:
                full = os.path.join(target_dir, entry)
                suffix = "/" if os.path.isdir(full) else ""
                print(f"  {entry}{suffix}")
            self._last_exit_code = 0
        except OSError as exc:
            print(f"ls: {exc}")
            self._last_exit_code = 1

    def _builtin_cat(self, args: List[str]) -> None:
        if not args:
            print("Usage: cat <file> [...]")
            return
        rc = 0
        for fname in args:
            path = self._abspath(fname)
            try:
                with open(path, "r", encoding="utf-8", errors="replace") as fh:
                    print(fh.read(), end="")
            except OSError as exc:
                print(f"cat: {exc}")
                rc = 1
        self._last_exit_code = rc

    def _builtin_head(self, args: List[str]) -> None:
        n = 10
        files = []
        i = 0
        while i < len(args):
            if args[i] == "-n" and i + 1 < len(args):
                try:
                    n = int(args[i + 1])
                except ValueError:
                    pass
                i += 2
            else:
                files.append(args[i])
                i += 1
        if not files:
            print("Usage: head [-n N] <file>")
            return
        for fname in files:
            path = self._abspath(fname)
            try:
                with open(path, "r", encoding="utf-8", errors="replace") as fh:
                    for idx, text_line in enumerate(fh):
                        if idx >= n:
                            break
                        print(text_line, end="")
                self._last_exit_code = 0
            except OSError as exc:
                print(f"head: {exc}")
                self._last_exit_code = 1

    def _builtin_tail(self, args: List[str]) -> None:
        n = 10
        files = []
        i = 0
        while i < len(args):
            if args[i] == "-n" and i + 1 < len(args):
                try:
                    n = int(args[i + 1])
                except ValueError:
                    pass
                i += 2
            else:
                files.append(args[i])
                i += 1
        if not files:
            print("Usage: tail [-n N] <file>")
            return
        for fname in files:
            path = self._abspath(fname)
            try:
                with open(path, "r", encoding="utf-8", errors="replace") as fh:
                    lines = fh.readlines()
                for text_line in lines[-n:]:
                    print(text_line, end="")
                self._last_exit_code = 0
            except OSError as exc:
                print(f"tail: {exc}")
                self._last_exit_code = 1

    def _builtin_rm(self, args: List[str]) -> None:
        if not args:
            print("Usage: rm <path> [...]")
            return
        import shutil as _shutil
        for fname in args:
            if fname in ("-r", "-rf", "-f"):
                continue
            path = self._abspath(fname)
            try:
                if os.path.isdir(path):
                    _shutil.rmtree(path)
                else:
                    os.remove(path)
                self._last_exit_code = 0
            except OSError as exc:
                print(f"rm: {exc}")
                self._last_exit_code = 1

    def _builtin_cp(self, args: List[str]) -> None:
        if len(args) < 2:
            print("Usage: cp <src> <dst>")
            return
        import shutil as _shutil
        src, dst = self._abspath(args[-2]), self._abspath(args[-1])
        try:
            if os.path.isdir(src):
                _shutil.copytree(src, dst)
            else:
                _shutil.copy2(src, dst)
            self._last_exit_code = 0
        except OSError as exc:
            print(f"cp: {exc}")
            self._last_exit_code = 1

    def _builtin_mv(self, args: List[str]) -> None:
        if len(args) < 2:
            print("Usage: mv <src> <dst>")
            return
        import shutil as _shutil
        src, dst = self._abspath(args[-2]), self._abspath(args[-1])
        try:
            _shutil.move(src, dst)
            self._last_exit_code = 0
        except OSError as exc:
            print(f"mv: {exc}")
            self._last_exit_code = 1

    def _builtin_wc(self, args: List[str]) -> None:
        if not args:
            print("Usage: wc <file>")
            return
        for fname in args:
            path = self._abspath(fname)
            try:
                with open(path, "r", encoding="utf-8", errors="replace") as fh:
                    content = fh.read()
                line_ct = content.count("\n")
                word_ct = len(content.split())
                char_ct = len(content)
                print(f"  {line_ct} {word_ct} {char_ct} {fname}")
                self._last_exit_code = 0
            except OSError as exc:
                print(f"wc: {exc}")
                self._last_exit_code = 1

    def _builtin_grep(self, args: List[str]) -> None:
        if len(args) < 2:
            print("Usage: grep <pattern> <file> [...]")
            return
        pattern = args[0]
        files = args[1:]
        rc = 1  # no match
        for fname in files:
            path = self._abspath(fname)
            try:
                with open(path, "r", encoding="utf-8", errors="replace") as fh:
                    for i, text_line in enumerate(fh, 1):
                        if pattern in text_line:
                            prefix = f"{fname}:" if len(files) > 1 else ""
                            print(f"  {prefix}{i}: {text_line}", end="")
                            rc = 0
            except OSError as exc:
                print(f"grep: {exc}")
                rc = 2
        self._last_exit_code = rc

    def _builtin_uptime(self) -> None:
        try:
            import psutil
            import time as _time
            uptime_s = _time.time() - psutil.boot_time()
        except (ImportError, Exception):
            try:
                with open("/proc/uptime", "r") as fh:
                    uptime_s = float(fh.read().split()[0])
            except OSError:
                print("uptime: unavailable")
                self._last_exit_code = 1
                return
        days = int(uptime_s // 86400)
        hours = int((uptime_s % 86400) // 3600)
        mins = int((uptime_s % 3600) // 60)
        parts = []
        if days:
            parts.append(f"{days} day(s)")
        if hours:
            parts.append(f"{hours}h")
        parts.append(f"{mins}m")
        print(f"  up {', '.join(parts)}")
        self._last_exit_code = 0

    def _builtin_ifconfig(self) -> None:
        try:
            from aura_os.net import NetworkManager
            nm = NetworkManager()
            for iface in nm.list_interfaces():
                status = "UP" if iface.get("is_up") else "DOWN"
                addrs = ", ".join(iface.get("addresses", [])) or "no address"
                print(f"  {iface['name']:<15} {status:<6}  {addrs}")
            self._last_exit_code = 0
        except Exception as exc:
            print(f"ifconfig: {exc}")
            self._last_exit_code = 1

    def _builtin_ping(self, args: List[str]) -> None:
        if not args:
            print("Usage: ping <host> [-c count]")
            self._last_exit_code = 1
            return
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
                print(f"  PING {host}: {result['packets_received']}/{result['packets_sent']}"
                      f" received, avg {result.get('avg_ms', 0):.1f} ms")
                self._last_exit_code = 0
            else:
                print(f"  PING {host}: failed — host unreachable or ping not available")
                self._last_exit_code = 1
        except Exception as exc:
            print(f"ping: {exc}")
            self._last_exit_code = 1

    def _print_help(self) -> None:
        print("""
  AURA OS Shell — Built-in Commands
  ──────────────────────────────────────────────────
  Navigation & Files:
    cd [dir]          Change directory
    pwd               Print working directory
    ls [dir]          List directory contents
    cat <file>        Print file contents
    head [-n N] <f>   Print first N lines (default 10)
    tail [-n N] <f>   Print last N lines (default 10)
    mkdir <dir>       Create directory
    rm <path>         Remove file or directory
    touch <file>      Create or update file
    cp <src> <dst>    Copy file or directory
    mv <src> <dst>    Move/rename file or directory
    wc <file>         Count lines, words, chars
    grep <pat> <file> Search for pattern in file
    which <binary>    Locate a binary in PATH

  Environment & Variables:
    export [VAR=val]  Set/show environment variables
    set <name> <val>  Set a shell variable
    unset <name>      Remove a variable
    alias [name=cmd]  Set/show command aliases
    unalias <name>    Remove an alias
    echo <text>       Print text (supports $VAR expansion)
    env               Show all environment variables

  System:
    whoami            Print current user
    id                Print uid/gid
    hostname          Print hostname
    date              Print current date/time
    uname [-a|-r|-m]  Print system information
    uptime            Show system uptime
    ifconfig          List network interfaces
    ping <host>       Ping a host
    clear             Clear the terminal

  Shell Control:
    history           Show command history
    help              Show this help
    exit [code]       Exit the shell
    quit              Exit the shell

  Shell Features:
    cmd1 | cmd2       Pipe output between commands
    cmd > file        Redirect output to file
    cmd >> file       Append output to file
    cmd1 && cmd2      Run cmd2 only if cmd1 succeeds
    cmd1 || cmd2      Run cmd2 only if cmd1 fails
    cmd1 ; cmd2       Run commands sequentially
    cmd &             Run command in background
    $VAR / ${VAR}     Variable expansion
    VAR=value         Shell variable assignment
    *  ?  [...]       Glob expansion in arguments

  AURA Commands (requires 'aura' prefix):
    aura ps           List tracked processes
    aura sys          Show system status
    aura service ...  Manage services
    aura pkg ...      Package management
    aura ai <prompt>  Query AI assistant
    (and all other 'aura' sub-commands)
""")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _abspath(self, path: str) -> str:
        """Resolve *path* relative to the shell's current directory."""
        path = self._expand_vars(os.path.expanduser(path))
        if not os.path.isabs(path):
            path = os.path.join(self._cwd, path)
        return os.path.normpath(path)

    def _expand_globs(self, tokens: List[str]) -> List[str]:
        """Expand glob patterns in *tokens*.  Unmatched patterns pass through."""
        result: List[str] = []
        for part in tokens:
            if any(c in part for c in ("*", "?", "[")):
                pattern = part if os.path.isabs(part) else os.path.join(self._cwd, part)
                matches = sorted(_glob_mod.glob(pattern))
                result.extend(matches if matches else [part])
            else:
                result.append(part)
        return result

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
            return Path(path).open("a" if append else "w", encoding="utf-8")
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
        # Lazy import avoids circular dependency (main → shell → main).
        from aura_os.main import _build_router  # type: ignore[attr-defined]
        from aura_os.engine.cli import build_parser

        try:
            router = _build_router()
            parser = build_parser()
        except Exception:  # noqa: BLE001
            router = None
            parser = None

        script = getattr(args, "script", None)
        shell = AuraShell(eal=eal, router=router, parser=parser)
        if script:
            return shell.run_script(script)
        return shell.run()
