#!/usr/bin/env python3
"""AURA OS — main entry point."""

import os
import sys


def _bootstrap():
    """Ensure AURA_HOME is set before importing other modules."""
    if "AURA_HOME" not in os.environ:
        os.environ["AURA_HOME"] = os.path.expanduser("~/.aura")


def _run_shell(eal):
    """Launch the modern interactive shell."""
    from aura_os.shell.shell import run_shell
    run_shell(eal)


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

    from aura_os.shell.colors import red, cyan, dim

    try:
        eal = EAL()
    except Exception as exc:  # noqa: BLE001
        print(f"{red('[aura]')} Failed to initialise EAL: {exc}", file=sys.stderr)
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
            print(f"{red('[aura]')} Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
