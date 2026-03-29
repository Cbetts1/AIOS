"""CLI interface (argparse) for AURA OS."""

import argparse
from aura_os import __version__


def build_parser() -> argparse.ArgumentParser:
    """Build and return the top-level argument parser."""
    parser = argparse.ArgumentParser(
        prog="aura",
        description="AURA OS — Universal Adaptive User-Space Operating System Layer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--version", action="version", version=f"aura {__version__}"
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", default=False,
        help="Enable verbose output",
    )

    subparsers = parser.add_subparsers(dest="command", metavar="<command>")
    subparsers.required = False

    # ------------------------------------------------------------------ run
    run_p = subparsers.add_parser("run", help="Run a script file")
    run_p.add_argument("file", help="Path to the script to run")
    run_p.add_argument(
        "args", nargs=argparse.REMAINDER,
        help="Arguments forwarded to the script",
    )

    # ------------------------------------------------------------------ ai
    ai_p = subparsers.add_parser("ai", help="Query a local AI model")
    ai_p.add_argument("prompt", help="Prompt text to send to the model")
    ai_p.add_argument("--model", default=None, help="Model name or path override")
    ai_p.add_argument(
        "--max-tokens", type=int, default=512, dest="max_tokens",
        help="Maximum number of tokens to generate (default: 512)",
    )

    # ------------------------------------------------------------------ env
    env_p = subparsers.add_parser("env", help="Show environment information")
    env_p.add_argument(
        "--json", action="store_true", dest="as_json",
        help="Output as JSON",
    )

    # ------------------------------------------------------------------ pkg
    pkg_p = subparsers.add_parser("pkg", help="Package management")
    pkg_sub = pkg_p.add_subparsers(dest="pkg_command", metavar="<pkg-command>")
    pkg_sub.required = True

    pkg_install = pkg_sub.add_parser("install", help="Install a package")
    pkg_install.add_argument("name_or_path", help="Package name or manifest path")

    pkg_remove = pkg_sub.add_parser("remove", help="Remove a package")
    pkg_remove.add_argument("name", help="Package name to remove")

    pkg_sub.add_parser("list", help="List installed packages")

    pkg_search = pkg_sub.add_parser("search", help="Search registry for packages")
    pkg_search.add_argument("query", help="Search query")

    pkg_info = pkg_sub.add_parser("info", help="Show package details")
    pkg_info.add_argument("name", help="Package name")

    # ------------------------------------------------------------------ sys
    sys_p = subparsers.add_parser("sys", help="Show system status")
    sys_p.add_argument(
        "--watch", action="store_true",
        help="Continuously refresh system status (every 2 s)",
    )

    # ------------------------------------------------------------------ shell
    subparsers.add_parser("shell", help="Launch the AURA interactive shell")

    return parser
