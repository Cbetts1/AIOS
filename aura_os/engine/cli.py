"""CLI interface (argparse) for AURA OS."""

import argparse
import signal
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

    # ------------------------------------------------------------------ ps
    subparsers.add_parser("ps", help="List tracked processes")

    # ------------------------------------------------------------------ kill
    kill_p = subparsers.add_parser("kill", help="Send signal to a process")
    kill_p.add_argument("pid", type=int, help="Process ID to signal")
    kill_p.add_argument(
        "-s", "--signal", type=int, default=signal.SIGTERM, dest="signal_num",
        help="Signal number (default: 15/SIGTERM)",
    )

    # ------------------------------------------------------------------ service
    svc_p = subparsers.add_parser("service", help="Manage background services")
    svc_sub = svc_p.add_subparsers(dest="svc_command", metavar="<svc-command>")
    svc_sub.required = True

    svc_sub.add_parser("list", help="List all services")

    svc_start = svc_sub.add_parser("start", help="Start a service")
    svc_start.add_argument("name", help="Service name")

    svc_stop = svc_sub.add_parser("stop", help="Stop a service")
    svc_stop.add_argument("name", help="Service name")

    svc_restart = svc_sub.add_parser("restart", help="Restart a service")
    svc_restart.add_argument("name", help="Service name")

    svc_status = svc_sub.add_parser("status", help="Show service status")
    svc_status.add_argument("name", help="Service name")

    svc_enable = svc_sub.add_parser("enable", help="Enable auto-start")
    svc_enable.add_argument("name", help="Service name")

    svc_disable = svc_sub.add_parser("disable", help="Disable auto-start")
    svc_disable.add_argument("name", help="Service name")

    svc_create = svc_sub.add_parser("create", help="Create a new service definition")
    svc_create.add_argument("name", help="Service name")
    svc_create.add_argument("--cmd", required=True, help="Command to run")
    svc_create.add_argument("--description", default="", help="Service description")

    # ------------------------------------------------------------------ log
    log_p = subparsers.add_parser("log", help="View system logs")
    log_sub = log_p.add_subparsers(dest="log_command", metavar="<log-command>")

    log_tail = log_sub.add_parser("tail", help="Show recent log entries (default)")
    log_tail.add_argument(
        "-n", "--lines", type=int, default=25,
        help="Number of lines to show (default: 25)",
    )

    log_search = log_sub.add_parser("search", help="Search log entries")
    log_search.add_argument("pattern", help="Text pattern to search for")

    log_sub.add_parser("clear", help="Clear the system log")

    # ------------------------------------------------------------------ shell
    subparsers.add_parser("shell", help="Launch the AURA interactive shell")

    # ------------------------------------------------------------------ help
    subparsers.add_parser("help", help="Show all available commands")

    # ------------------------------------------------------------------ fs
    fs_p = subparsers.add_parser("fs", help="File system operations")
    fs_sub = fs_p.add_subparsers(dest="fs_command", metavar="<fs-command>")
    fs_sub.required = True

    fs_ls = fs_sub.add_parser("ls", help="List files / directories")
    fs_ls.add_argument("path", nargs="?", default=".", help="Directory to list")

    fs_cat = fs_sub.add_parser("cat", help="Print file contents")
    fs_cat.add_argument("file", help="File to display")

    fs_find = fs_sub.add_parser("find", help="Search for files")
    fs_find.add_argument("root", nargs="?", default=".", help="Root directory")
    fs_find.add_argument("pattern", nargs="?", default="", help="Filename pattern")

    fs_mkdir = fs_sub.add_parser("mkdir", help="Create directory")
    fs_mkdir.add_argument("path", help="Directory path to create")

    fs_rm = fs_sub.add_parser("rm", help="Delete file or directory")
    fs_rm.add_argument("path", help="Path to delete")

    fs_edit = fs_sub.add_parser("edit", help="Open file in text editor")
    fs_edit.add_argument("file", help="File to edit")

    # ------------------------------------------------------------------ repo
    repo_p = subparsers.add_parser("repo", help="Git repository management")
    repo_sub = repo_p.add_subparsers(dest="repo_command", metavar="<repo-command>")
    repo_sub.required = True

    repo_create = repo_sub.add_parser("create", help="Create a new git repository")
    repo_create.add_argument("name", help="Repository name")

    repo_sub.add_parser("list", help="List managed repositories")

    repo_status = repo_sub.add_parser("status", help="Show git status")
    repo_status.add_argument("path", nargs="?", default=".", help="Repository path")

    repo_clone = repo_sub.add_parser("clone", help="Clone a remote repository")
    repo_clone.add_argument("url", help="Repository URL")
    repo_clone.add_argument("dest", nargs="?", default=None, help="Destination name")

    # ------------------------------------------------------------------ auto
    auto_p = subparsers.add_parser("auto", help="Task automation")
    auto_sub = auto_p.add_subparsers(dest="auto_command", metavar="<auto-command>")
    auto_sub.required = True

    auto_sub.add_parser("list", help="List automation tasks")

    auto_create = auto_sub.add_parser("create", help="Create a task template")
    auto_create.add_argument("name", help="Task name")

    auto_run = auto_sub.add_parser("run", help="Execute a task")
    auto_run.add_argument("name", help="Task name to execute")

    return parser
