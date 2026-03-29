#!/usr/bin/env python3
"""AURA OS — main entry point."""

import os
import sys


def _bootstrap():
    """Ensure AURA_HOME is set before importing other modules."""
    if "AURA_HOME" not in os.environ:
        os.environ["AURA_HOME"] = os.path.expanduser("~/.aura")


def _run_shell(eal):
    """Launch a simple REPL for interactive use."""
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
    prompt = "aura> "

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

    print(f"AURA OS shell. Type 'exit' or Ctrl-D to quit.")
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
            break

        try:
            parsed = parser.parse_args(line.split())
            router.dispatch(parsed, eal)
        except SystemExit:
            # argparse calls sys.exit on --help; catch it gracefully in the REPL
            pass
        except Exception as exc:  # noqa: BLE001
            print(f"[shell] Error: {exc}")


def main(argv=None):
    """Primary entry point for AURA OS CLI."""
    _bootstrap()

    from aura_os.eal import EAL
    from aura_os.engine.cli import build_parser
    from aura_os.engine.router import CommandRouter
    from aura_os.engine.commands.run import RunCommand
    from aura_os.engine.commands.ai import AiCommand
    from aura_os.engine.commands.env_cmd import EnvCommand
    from aura_os.engine.commands.pkg import PkgCommand
    from aura_os.engine.commands.sys_cmd import SysCommand

    parser = build_parser()
    args = parser.parse_args(argv)

    verbose = getattr(args, "verbose", False)

    try:
        eal = EAL()
    except Exception as exc:  # noqa: BLE001
        print(f"[aura] Failed to initialise EAL: {exc}", file=sys.stderr)
        return 1

    if args.command == "shell":
        _run_shell(eal)
        return 0

    if args.command is None:
        parser.print_help()
        return 0

    router = CommandRouter()
    router.register("run", RunCommand)
    router.register("ai", AiCommand)
    router.register("env", EnvCommand)
    router.register("pkg", PkgCommand)
    router.register("sys", SysCommand)

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
