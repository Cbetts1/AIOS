#!/usr/bin/env python3
"""AURA OS — main entry point."""

import os
import sys


def _bootstrap():
    """Ensure AURA_HOME is set before importing other modules."""
    if "AURA_HOME" not in os.environ:
        os.environ["AURA_HOME"] = os.path.expanduser("~/.aura")


def _build_router():
    """Create a CommandRouter and register all command handlers."""
    from aura_os.engine.router import CommandRouter
    from aura_os.engine.commands.run import RunCommand
    from aura_os.engine.commands.ai import AiCommand
    from aura_os.engine.commands.env_cmd import EnvCommand
    from aura_os.engine.commands.pkg import PkgCommand
    from aura_os.engine.commands.sys_cmd import SysCommand
    from aura_os.engine.commands.ps_cmd import PsCommand
    from aura_os.engine.commands.kill_cmd import KillCommand
    from aura_os.engine.commands.service_cmd import ServiceCommand
    from aura_os.engine.commands.log_cmd import LogCommand
    from aura_os.engine.commands.user_cmd import UserCommand
    from aura_os.engine.commands.net_cmd import NetCommand
    from aura_os.engine.commands.init_cmd import InitCommand
    from aura_os.engine.commands.notify_cmd import NotifyCommand
    from aura_os.engine.commands.cron_cmd import CronCommand
    from aura_os.engine.commands.clip_cmd import ClipCommand
    from aura_os.engine.commands.plugin_cmd import PluginCommand
    from aura_os.engine.commands.secret_cmd import SecretCommand
    from aura_os.engine.commands.disk_cmd import DiskCommand
    from aura_os.engine.commands.health_cmd import HealthCommand
    from aura_os.engine.commands.monitor_cmd import MonitorCommand
    from aura_os.engine.commands.web_cmd import WebCommand

    router = CommandRouter()
    router.register("run", RunCommand)
    router.register("ai", AiCommand)
    router.register("env", EnvCommand)
    router.register("pkg", PkgCommand)
    router.register("sys", SysCommand)
    router.register("ps", PsCommand)
    router.register("kill", KillCommand)
    router.register("service", ServiceCommand)
    router.register("log", LogCommand)
    router.register("user", UserCommand)
    router.register("net", NetCommand)
    router.register("init", InitCommand)
    router.register("notify", NotifyCommand)
    router.register("cron", CronCommand)
    router.register("clip", ClipCommand)
    router.register("plugin", PluginCommand)
    router.register("secret", SecretCommand)
    router.register("disk", DiskCommand)
    router.register("health", HealthCommand)
    router.register("monitor", MonitorCommand)
    router.register("web", WebCommand)
    return router


# ------------------------------------------------------------------
# Enhanced interactive shell
# ------------------------------------------------------------------

def _run_shell(eal, script_file=None):
    """Launch an enhanced REPL with built-in shell commands.

    If *script_file* is provided, commands are read from that file
    non-interactively instead of prompting for input.
    """
    from aura_os.engine.cli import build_parser
    from aura_os.kernel.syslog import Syslog
    from aura_os.fs.procfs import ProcFS

    router = _build_router()
    parser = build_parser()
    syslog = Syslog()
    procfs = ProcFS()

    # Shell state
    env_vars = dict(os.environ)
    aliases = {}
    cwd = os.getcwd()

    # Determine input source: script file or stdin REPL
    if script_file is not None:
        try:
            with open(script_file, "r", encoding="utf-8") as fh:
                script_lines = fh.readlines()
        except OSError as exc:
            print(f"[aura shell] Cannot read script '{script_file}': {exc}",
                  file=sys.stderr)
            return 1
        syslog.info("shell", f"Running script: {script_file}")
        input_iter = iter(line.rstrip("\n") for line in script_lines)
        interactive = False
    else:
        input_iter = None
        interactive = True

    if interactive:
        # Try to enable readline history
        try:
            import readline
            import atexit
            history_path = os.path.expanduser(
                os.environ.get("AURA_HOME", "~/.aura") + "/data/.history"
            )
            os.makedirs(os.path.dirname(history_path), exist_ok=True)
            try:
                readline.read_history_file(history_path)
            except OSError:
                pass
            atexit.register(readline.write_history_file, history_path)
        except ImportError:
            pass
        syslog.info("shell", "Interactive shell started")
        print("AURA OS shell — type 'help' for commands, 'exit' to quit.")

    prompt = "aura> "
    while True:
        try:
            if interactive:
                # Update prompt with cwd
                short_cwd = cwd.replace(os.path.expanduser("~"), "~")
                prompt = f"aura:{short_cwd}> "
                line = input(prompt).strip()
            else:
                line = next(input_iter).strip()  # type: ignore[union-attr]
        except StopIteration:
            # Script finished
            break
        except EOFError:
            print()
            break
        except KeyboardInterrupt:
            print()
            continue

        if not line:
            continue

        # Expand aliases
        parts = line.split()
        if parts[0] in aliases:
            line = aliases[parts[0]] + " " + " ".join(parts[1:])
            parts = line.split()

        # Expand environment variables ($VAR and ${VAR})
        line = _expand_env_vars(line, env_vars)

        # ------------------------------------------------------------------
        # Command chaining: split on ; && ||  (outside quotes)
        # ------------------------------------------------------------------
        if any(op in line for op in ("&&", "||", ";")):
            _handle_chain(line, cwd, env_vars, aliases, router, parser, eal, syslog, procfs)
            continue

        # Handle background execution (&)
        background = False
        if line.rstrip().endswith("&"):
            background = True
            line = line.rstrip()[:-1].rstrip()

        # Handle pipes
        if "|" in line:
            _handle_pipe(line, cwd, env_vars)
            continue

        # Handle output redirection
        if ">>" in line or ">" in line:
            _handle_redirect(line, cwd, env_vars)
            continue

        # Glob expansion in arguments
        parts = _expand_globs(line.split(), cwd)

        # Built-in commands
        cmd = parts[0].lower() if parts else ""

        if cmd in ("exit", "quit"):
            syslog.info("shell", "Shell exiting")
            break

        if cmd == "cd":
            target = parts[1] if len(parts) > 1 else os.path.expanduser("~")
            target = _expand_env_vars(target, env_vars)
            target = os.path.expanduser(target)
            if not os.path.isabs(target):
                target = os.path.join(cwd, target)
            target = os.path.realpath(target)
            if os.path.isdir(target):
                cwd = target
                os.chdir(cwd)
                env_vars["PWD"] = cwd
            else:
                print(f"cd: no such directory: {target}")
            continue

        if cmd == "pwd":
            print(cwd)
            continue

        if cmd == "echo":
            print(" ".join(parts[1:]))
            continue

        if cmd == "export":
            if len(parts) < 2:
                for k, v in sorted(env_vars.items()):
                    print(f"  {k}={v}")
            else:
                for arg in parts[1:]:
                    if "=" in arg:
                        key, _, val = arg.partition("=")
                        env_vars[key] = val
                        os.environ[key] = val
                    else:
                        val = env_vars.get(arg, "")
                        print(f"  {arg}={val}")
            continue

        if cmd == "set":
            if len(parts) < 2:
                for k, v in sorted(env_vars.items()):
                    print(f"  {k}={v}")
            elif len(parts) >= 3 and parts[1].isidentifier():
                env_vars[parts[1]] = " ".join(parts[2:])
            else:
                print("Usage: set <name> <value>")
            continue

        if cmd == "unset":
            if len(parts) < 2:
                print("Usage: unset <name>")
            else:
                env_vars.pop(parts[1], None)
                os.environ.pop(parts[1], None)
            continue

        if cmd == "alias":
            if len(parts) < 2:
                for k, v in sorted(aliases.items()):
                    print(f"  alias {k}='{v}'")
            else:
                for arg in parts[1:]:
                    if "=" in arg:
                        key, _, val = arg.partition("=")
                        aliases[key] = val.strip("'\"")
                    else:
                        a = aliases.get(arg)
                        if a:
                            print(f"  alias {arg}='{a}'")
                        else:
                            print(f"  alias: {arg}: not found")
            continue

        if cmd == "unalias":
            if len(parts) < 2:
                print("Usage: unalias <name>")
            else:
                aliases.pop(parts[1], None)
            continue

        if cmd == "history":
            try:
                import readline
                length = readline.get_current_history_length()
                start = max(1, length - 25)
                for i in range(start, length + 1):
                    item = readline.get_history_item(i)
                    if item:
                        print(f"  {i:>5}  {item}")
            except ImportError:
                print("  (readline not available)")
            continue

        if cmd == "clear":
            print("\033[2J\033[H", end="")
            continue

        if cmd == "whoami":
            import getpass
            print(getpass.getuser())
            continue

        if cmd == "id":
            import getpass
            user = getpass.getuser()
            uid = os.getuid() if hasattr(os, "getuid") else 0
            gid = os.getgid() if hasattr(os, "getgid") else 0
            print(f"uid={uid}({user}) gid={gid}")
            continue

        if cmd == "hostname":
            import platform as plat
            print(plat.node())
            continue

        if cmd == "ifconfig":
            from aura_os.net import NetworkManager
            nm = NetworkManager()
            for iface in nm.list_interfaces():
                status = "UP" if iface.get("is_up") else "DOWN"
                addrs = ", ".join(iface.get("addresses", [])) or "no address"
                print(f"  {iface['name']:<15} {status:<6}  {addrs}")
            continue

        if cmd == "ping":
            if len(parts) < 2:
                print("Usage: ping <host> [-c count]")
            else:
                from aura_os.net import NetworkManager
                host = parts[1]
                count = 4
                if "-c" in parts:
                    idx = parts.index("-c")
                    if idx + 1 < len(parts):
                        try:
                            count = int(parts[idx + 1])
                        except ValueError:
                            pass
                nm = NetworkManager()
                result = nm.ping(host, count=count)
                if result.get("success"):
                    print(f"  PING {host}: {result['packets_received']}/{result['packets_sent']} received, avg {result.get('avg_ms', 0):.1f} ms")
                else:
                    print(f"  PING {host}: failed — host unreachable or ping not available")
            continue

        if cmd == "date":
            import datetime
            print(datetime.datetime.now().strftime("%a %b %d %H:%M:%S %Z %Y"))
            continue

        if cmd == "uname":
            import platform as plat
            flag = parts[1] if len(parts) > 1 else "-s"
            u = plat.uname()
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
            continue

        if cmd == "uptime":
            content = procfs.read("uptime")
            if content:
                secs = float(content.split()[0])
                days = int(secs // 86400)
                hours = int((secs % 86400) // 3600)
                mins = int((secs % 3600) // 60)
                uptime_parts = []
                if days:
                    uptime_parts.append(f"{days} day(s)")
                if hours:
                    uptime_parts.append(f"{hours}h")
                uptime_parts.append(f"{mins}m")
                print(f"  up {', '.join(uptime_parts)}")
            continue

        if cmd == "cat":
            if len(parts) < 2:
                print("Usage: cat <file>")
            else:
                path = os.path.join(cwd, parts[1]) if not os.path.isabs(parts[1]) else parts[1]
                try:
                    with open(path, "r", encoding="utf-8") as fh:
                        print(fh.read(), end="")
                except OSError as exc:
                    print(f"cat: {exc}")
            continue

        if cmd == "ls":
            target_dir = parts[1] if len(parts) > 1 else cwd
            if not os.path.isabs(target_dir):
                target_dir = os.path.join(cwd, target_dir)
            try:
                entries = sorted(os.listdir(target_dir))
                for entry in entries:
                    full = os.path.join(target_dir, entry)
                    if os.path.isdir(full):
                        print(f"  {entry}/")
                    else:
                        print(f"  {entry}")
            except OSError as exc:
                print(f"ls: {exc}")
            continue

        if cmd == "mkdir":
            if len(parts) < 2:
                print("Usage: mkdir <dir>")
            else:
                target = os.path.join(cwd, parts[1]) if not os.path.isabs(parts[1]) else parts[1]
                try:
                    os.makedirs(target, exist_ok=True)
                except OSError as exc:
                    print(f"mkdir: {exc}")
            continue

        if cmd == "rm":
            if len(parts) < 2:
                print("Usage: rm <path>")
            else:
                import shutil
                target = os.path.join(cwd, parts[1]) if not os.path.isabs(parts[1]) else parts[1]
                try:
                    if os.path.isdir(target):
                        shutil.rmtree(target)
                    else:
                        os.remove(target)
                except OSError as exc:
                    print(f"rm: {exc}")
            continue

        if cmd == "touch":
            if len(parts) < 2:
                print("Usage: touch <file>")
            else:
                target = os.path.join(cwd, parts[1]) if not os.path.isabs(parts[1]) else parts[1]
                try:
                    from pathlib import Path as P
                    P(target).touch()
                except OSError as exc:
                    print(f"touch: {exc}")
            continue

        if cmd == "cp":
            if len(parts) < 3:
                print("Usage: cp <src> <dst>")
            else:
                import shutil
                src = os.path.join(cwd, parts[1]) if not os.path.isabs(parts[1]) else parts[1]
                dst = os.path.join(cwd, parts[2]) if not os.path.isabs(parts[2]) else parts[2]
                try:
                    if os.path.isdir(src):
                        shutil.copytree(src, dst)
                    else:
                        shutil.copy2(src, dst)
                except OSError as exc:
                    print(f"cp: {exc}")
            continue

        if cmd == "mv":
            if len(parts) < 3:
                print("Usage: mv <src> <dst>")
            else:
                import shutil
                src = os.path.join(cwd, parts[1]) if not os.path.isabs(parts[1]) else parts[1]
                dst = os.path.join(cwd, parts[2]) if not os.path.isabs(parts[2]) else parts[2]
                try:
                    shutil.move(src, dst)
                except OSError as exc:
                    print(f"mv: {exc}")
            continue

        if cmd == "head":
            if len(parts) < 2:
                print("Usage: head <file> [n]")
            else:
                path = os.path.join(cwd, parts[1]) if not os.path.isabs(parts[1]) else parts[1]
                try:
                    n = int(parts[2]) if len(parts) > 2 else 10
                except ValueError:
                    print(f"head: invalid count: {parts[2]}")
                    continue
                try:
                    with open(path, "r", encoding="utf-8") as fh:
                        for i, line_text in enumerate(fh):
                            if i >= n:
                                break
                            print(line_text, end="")
                except OSError as exc:
                    print(f"head: {exc}")
            continue

        if cmd == "tail":
            if len(parts) < 2:
                print("Usage: tail <file> [n]")
            else:
                path = os.path.join(cwd, parts[1]) if not os.path.isabs(parts[1]) else parts[1]
                try:
                    n = int(parts[2]) if len(parts) > 2 else 10
                except ValueError:
                    print(f"tail: invalid count: {parts[2]}")
                    continue
                try:
                    with open(path, "r", encoding="utf-8") as fh:
                        all_lines = fh.readlines()
                    for text_line in all_lines[-n:]:
                        print(text_line, end="")
                except OSError as exc:
                    print(f"tail: {exc}")
            continue

        if cmd == "wc":
            if len(parts) < 2:
                print("Usage: wc <file>")
            else:
                path = os.path.join(cwd, parts[1]) if not os.path.isabs(parts[1]) else parts[1]
                try:
                    with open(path, "r", encoding="utf-8") as fh:
                        content = fh.read()
                    line_ct = content.count("\n")
                    word_ct = len(content.split())
                    char_ct = len(content)
                    print(f"  {line_ct} {word_ct} {char_ct} {parts[1]}")
                except OSError as exc:
                    print(f"wc: {exc}")
            continue

        if cmd == "grep":
            if len(parts) < 3:
                print("Usage: grep <pattern> <file>")
            else:
                pattern = parts[1]
                path = os.path.join(cwd, parts[2]) if not os.path.isabs(parts[2]) else parts[2]
                try:
                    with open(path, "r", encoding="utf-8") as fh:
                        for i, text_line in enumerate(fh, 1):
                            if pattern in text_line:
                                print(f"  {i}: {text_line}", end="")
                except OSError as exc:
                    print(f"grep: {exc}")
            continue

        if cmd == "which":
            if len(parts) < 2:
                print("Usage: which <binary>")
            else:
                import shutil
                result = shutil.which(parts[1])
                if result:
                    print(result)
                else:
                    print(f"  {parts[1]} not found")
            continue

        if cmd == "proc":
            if len(parts) < 2:
                entries = procfs.ls()
                for e in entries:
                    print(f"  {e}")
            else:
                proc_path = "/".join(parts[1:])
                content = procfs.read(proc_path)
                if content is not None:
                    print(content, end="")
                else:
                    print(f"  /proc/{proc_path}: not found")
            continue

        if cmd == "help":
            _print_shell_help()
            continue

        # Fall through to aura CLI commands
        try:
            parsed = parser.parse_args(line.split())
            router.dispatch(parsed, eal)
        except SystemExit:
            pass
        except Exception as exc:  # noqa: BLE001
            print(f"[shell] Error: {exc}")


def _expand_globs(parts: list, cwd: str) -> list:
    """Expand glob patterns (*, ?, [...]) in *parts* relative to *cwd*.

    Returns the expanded argument list.  Patterns that match nothing are
    kept as-is (POSIX-style no-match passthrough).
    """
    import glob as _glob
    result = []
    for part in parts:
        if any(c in part for c in ("*", "?", "[")):
            # Resolve relative to cwd
            pattern = part if os.path.isabs(part) else os.path.join(cwd, part)
            matches = sorted(_glob.glob(pattern))
            if matches:
                result.extend(matches)
            else:
                result.append(part)  # no match: pass through unchanged
        else:
            result.append(part)
    return result


def _handle_chain(line: str, cwd: str, env: dict, aliases: dict,
                  router, parser, eal, syslog, procfs):
    """Execute a chain of commands separated by ``;``, ``&&``, or ``||``.

    - ``;``   — run next regardless of exit code
    - ``&&``  — run next only if previous succeeded (exit 0)
    - ``||``  — run next only if previous failed (exit != 0)

    Note: Each segment is dispatched via subprocess, which means AURA
    built-in commands (``cd``, ``export``, aliases, etc.) are not available
    inside chains.  Use them as standalone commands instead.
    """
    import re
    import shlex
    import subprocess

    # Tokenise: split on &&, ||, ; while preserving order
    tokens = re.split(r"(&&|\|\||;)", line)
    tokens = [t.strip() for t in tokens]

    last_rc = 0
    pending_op = ";"  # first command always runs

    for token in tokens:
        if token in ("&&", "||", ";"):
            pending_op = token
            continue
        if not token:
            continue

        # Decide whether to execute this command
        if pending_op == "&&" and last_rc != 0:
            continue
        if pending_op == "||" and last_rc == 0:
            continue

        # Execute as a subprocess (simple approach)
        try:
            cmd_list = shlex.split(token)
        except ValueError:
            print(f"[shell] Parse error: {token}")
            last_rc = 1
            continue

        if not cmd_list:
            last_rc = 0
            continue

        try:
            result = subprocess.run(cmd_list, cwd=cwd, env=env)
            last_rc = result.returncode
        except FileNotFoundError:
            print(f"[shell] Command not found: {cmd_list[0]}")
            last_rc = 127
        except OSError as exc:
            print(f"[shell] Error: {exc}")
            last_rc = 1


def _expand_env_vars(text: str, env: dict) -> str:
    """Expand $VAR and ${VAR} references in *text*."""
    import re
    def _replacer(match):
        var = match.group(1) or match.group(2)
        return env.get(var, "")
    return re.sub(r"\$\{(\w+)\}|\$(\w+)", _replacer, text)


def _handle_pipe(line: str, cwd: str, env: dict):
    """Execute a pipeline of shell commands."""
    import subprocess
    segments = [s.strip() for s in line.split("|")]
    prev_stdout = None
    processes = []

    for i, segment in enumerate(segments):
        import shlex
        try:
            cmd_list = shlex.split(segment)
        except ValueError:
            print(f"[shell] Invalid command in pipe: {segment}")
            return

        is_last = (i == len(segments) - 1)
        proc = subprocess.Popen(
            cmd_list,
            stdin=prev_stdout,
            stdout=None if is_last else subprocess.PIPE,
            stderr=None,
            cwd=cwd,
            env=env,
        )
        processes.append(proc)
        if prev_stdout is not None:
            prev_stdout.close()
        prev_stdout = proc.stdout

    for proc in processes:
        proc.wait()


def _handle_redirect(line: str, cwd: str, env: dict):
    """Execute a command with output redirection (> or >>)."""
    import subprocess
    import shlex

    if ">>" in line:
        parts = line.split(">>", 1)
        mode = "a"
    else:
        parts = line.split(">", 1)
        mode = "w"

    cmd_str = parts[0].strip()
    filepath = parts[1].strip()

    if not os.path.isabs(filepath):
        filepath = os.path.join(cwd, filepath)

    try:
        cmd_list = shlex.split(cmd_str)
    except ValueError:
        print(f"[shell] Invalid command: {cmd_str}")
        return

    try:
        with open(filepath, mode, encoding="utf-8") as fh:
            subprocess.run(cmd_list, stdout=fh, stderr=None, cwd=cwd, env=env)
    except OSError as exc:
        print(f"[shell] Redirect error: {exc}")


def _print_shell_help():
    """Print help for the enhanced shell."""
    print("""
  AURA OS Shell — Built-in Commands
  ──────────────────────────────────────────────────
  Navigation & Files:
    cd <dir>          Change directory
    pwd               Print working directory
    ls [dir]          List directory contents
    cat <file>        Print file contents
    head <file> [n]   Print first n lines (default 10)
    tail <file> [n]   Print last n lines (default 10)
    mkdir <dir>       Create directory
    rm <path>         Remove file or directory
    touch <file>      Create empty file
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

  System:
    whoami            Print current user
    hostname          Print hostname
    date              Print current date/time
    uname [-a|-r|-m]  Print system information
    uptime            Show session uptime
    clear             Clear the terminal

  AURA OS Commands:
    ps                List tracked processes
    kill <pid>        Send signal to a process
    service <cmd>     Manage services (list/start/stop/...)
    log <cmd>         View system logs (tail/search/clear)
    sys               Show system status
    env               Show environment info
    pkg <cmd>         Package management
    run <file>        Run a script
    ai <prompt>       Query AI assistant
    proc [path]       Read virtual /proc files
    user <cmd>        User management (add/del/list/whoami/passwd)
    net <cmd>         Network management (status/ifconfig/ping/dns)
    init <cmd>        Init system (status/boot/shutdown)

  Shell Features:
    cmd1 | cmd2       Pipe output between commands
    cmd > file        Redirect output to file
    cmd >> file       Append output to file
    $VAR / ${VAR}     Environment variable expansion

    exit / quit       Exit the shell
    Ctrl-D            Exit the shell
    Ctrl-C            Cancel current input
""")


# ------------------------------------------------------------------
# Main entry
# ------------------------------------------------------------------

def main(argv=None):
    """Primary entry point for AURA OS CLI."""
    _bootstrap()

    from aura_os.eal import EAL
    from aura_os.engine.cli import build_parser
    from aura_os.kernel.syslog import Syslog

    parser = build_parser()
    args = parser.parse_args(argv)

    verbose = getattr(args, "verbose", False)

    try:
        eal = EAL()
    except Exception as exc:  # noqa: BLE001
        print(f"[aura] Failed to initialise EAL: {exc}", file=sys.stderr)
        return 1

    # Initialise system logger
    syslog = Syslog()
    syslog.info("kern", "AURA OS started")

    if args.command == "shell":
        script = getattr(args, "script", None)
        result = _run_shell(eal, script_file=script)
        return result if result is not None else 0

    if args.command is None:
        parser.print_help()
        return 0

    router = _build_router()

    try:
        return router.dispatch(args, eal)
    except KeyboardInterrupt:
        print()
        return 130
    except Exception as exc:  # noqa: BLE001
        if verbose:
            import traceback
            traceback.print_exc()
        else:
            print(f"[aura] Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
