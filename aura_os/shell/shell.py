"""Modern interactive shell for AURA OS.

Uses ``prompt_toolkit`` when available for a rich experience:
- Tab completion for all commands and sub-commands
- Auto-suggestions from command history
- Syntax-highlighted prompt with platform context
- Vi / Emacs key-bindings

Falls back gracefully to the built-in ``readline``-based shell when
``prompt_toolkit`` is not installed.
"""

import os
import sys
from typing import Optional

from aura_os.shell.colors import (
    bold, bright_cyan, cyan, dim, green, header, info, muted, red, yellow,
)


# ──────────────────────────────────────────────────────────────────────
# prompt_toolkit shell
# ──────────────────────────────────────────────────────────────────────

def _run_prompt_toolkit_shell(parser, router, eal):
    """Launch the interactive shell using ``prompt_toolkit``."""
    from prompt_toolkit import PromptSession
    from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
    from prompt_toolkit.history import FileHistory
    from prompt_toolkit.formatted_text import ANSI

    from aura_os.shell.completer import make_prompt_toolkit_completer

    history_path = os.path.expanduser(
        os.environ.get("AURA_HOME", "~/.aura") + "/data/.history"
    )
    os.makedirs(os.path.dirname(history_path), exist_ok=True)

    completer = make_prompt_toolkit_completer()
    history = FileHistory(history_path)
    platform = getattr(eal, "platform", "aura")

    # Build a colored prompt
    prompt_text = ANSI(
        f"{dim('[')}{ cyan(platform) }{dim(']')} {bold(bright_cyan('aura'))} {dim('❯')} "
    )

    session = PromptSession(
        history=history,
        auto_suggest=AutoSuggestFromHistory(),
        completer=completer,
        complete_while_typing=False,
    )

    _print_welcome(eal)

    while True:
        try:
            line = session.prompt(prompt_text).strip()
        except EOFError:
            print()
            break
        except KeyboardInterrupt:
            print()
            continue

        if not line:
            continue
        if line.lower() in ("exit", "quit"):
            print(f"  {dim('Goodbye!')}")
            break

        _execute_line(line, parser, router, eal)


# ──────────────────────────────────────────────────────────────────────
# readline fallback shell
# ──────────────────────────────────────────────────────────────────────

def _run_readline_shell(parser, router, eal):
    """Launch the interactive shell using Python's built-in readline."""
    import atexit

    history_path = os.path.expanduser(
        os.environ.get("AURA_HOME", "~/.aura") + "/data/.history"
    )
    os.makedirs(os.path.dirname(history_path), exist_ok=True)

    try:
        import readline
        from aura_os.shell.completer import ReadlineCompleter

        try:
            readline.read_history_file(history_path)
        except OSError:
            pass
        atexit.register(readline.write_history_file, history_path)

        # Enable tab completion
        completer = ReadlineCompleter()
        readline.set_completer(completer.complete)
        readline.parse_and_bind("tab: complete")
    except ImportError:
        pass

    platform = getattr(eal, "platform", "aura")
    prompt = f"[{platform}] aura ❯ "

    _print_welcome(eal)

    while True:
        try:
            line = input(prompt).strip()
        except EOFError:
            print()
            break
        except KeyboardInterrupt:
            print()
            continue

        if not line:
            continue
        if line.lower() in ("exit", "quit"):
            print(f"  {dim('Goodbye!')}")
            break

        _execute_line(line, parser, router, eal)


# ──────────────────────────────────────────────────────────────────────
# Shared helpers
# ──────────────────────────────────────────────────────────────────────

def _print_welcome(eal):
    """Print a welcome banner when the shell starts."""
    from aura_os import __version__
    platform = getattr(eal, "platform", "unknown")

    print()
    print(f"  {header('⬡ AURA OS')} {dim('v' + __version__)}")
    print(f"  {dim('Platform:')} {cyan(platform)}  "
          f"{dim('|')}  {dim('Type')} {bold('help')} {dim('for commands,')} "
          f"{bold('exit')} {dim('to quit')}")
    print(f"  {dim('Tab-completion and history enabled.')}")
    print()


def _execute_line(line: str, parser, router, eal):
    """Parse and execute a single command line."""
    try:
        parsed = parser.parse_args(line.split())
        router.dispatch(parsed, eal)
    except SystemExit:
        # argparse calls sys.exit on --help / error; catch in REPL
        pass
    except Exception as exc:  # noqa: BLE001
        print(f"  {red('[error]')} {exc}")


# ──────────────────────────────────────────────────────────────────────
# Public entry point
# ──────────────────────────────────────────────────────────────────────

def run_shell(eal):
    """Launch the AURA interactive shell.

    Automatically selects ``prompt_toolkit`` if available, otherwise
    falls back to readline.
    """
    from aura_os.engine.cli import build_parser
    from aura_os.engine.router import CommandRouter
    from aura_os.engine.commands.run import RunCommand
    from aura_os.engine.commands.ai import AiCommand
    from aura_os.engine.commands.env_cmd import EnvCommand
    from aura_os.engine.commands.pkg import PkgCommand
    from aura_os.engine.commands.sys_cmd import SysCommand

    router = CommandRouter()
    router.register("run", RunCommand)
    router.register("ai", AiCommand)
    router.register("env", EnvCommand)
    router.register("pkg", PkgCommand)
    router.register("sys", SysCommand)

    parser = build_parser()

    try:
        import prompt_toolkit  # noqa: F401
        _run_prompt_toolkit_shell(parser, router, eal)
    except ImportError:
        _run_readline_shell(parser, router, eal)
