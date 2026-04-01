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

    # ------------------------------------------------------------------ user
    user_p = subparsers.add_parser("user", help="User management")
    user_sub = user_p.add_subparsers(dest="user_command", metavar="<user-command>")
    user_sub.required = True

    user_sub.add_parser("list", help="List all users")
    user_sub.add_parser("whoami", help="Show current user")

    user_add = user_sub.add_parser("add", help="Add a new user")
    user_add.add_argument("username", help="Username")
    user_add.add_argument("--password", default=None, help="Password (prompted if omitted)")
    user_add.add_argument(
        "--role", default="user", choices=["root", "user", "guest"],
        help="User role",
    )

    user_del = user_sub.add_parser("del", help="Delete a user")
    user_del.add_argument("username", help="Username to delete")

    user_passwd = user_sub.add_parser("passwd", help="Change a user's password")
    user_passwd.add_argument("username", help="Username")

    user_info = user_sub.add_parser("info", help="Show user details")
    user_info.add_argument("username", help="Username")

    # ------------------------------------------------------------------ net
    net_p = subparsers.add_parser("net", help="Network management")
    net_sub = net_p.add_subparsers(dest="net_command", metavar="<net-command>")
    net_sub.required = True

    net_sub.add_parser("status", help="Show network status")
    net_sub.add_parser("ifconfig", help="List network interfaces")

    net_ping = net_sub.add_parser("ping", help="Ping a host")
    net_ping.add_argument("host", help="Hostname or IP to ping")
    net_ping.add_argument(
        "-c", "--count", type=int, default=4,
        help="Number of pings (default 4)",
    )

    net_dns = net_sub.add_parser("dns", help="DNS lookup")
    net_dns.add_argument("hostname", help="Hostname to resolve")

    net_dl = net_sub.add_parser("download", help="Download a file")
    net_dl.add_argument("url", help="URL to download")
    net_dl.add_argument("dest", help="Destination path")

    # ------------------------------------------------------------------ init
    init_p = subparsers.add_parser("init", help="Init system management")
    init_sub = init_p.add_subparsers(dest="init_command", metavar="<init-command>")
    init_sub.required = True

    init_sub.add_parser("status", help="Show init unit status")
    init_sub.add_parser("boot", help="Run boot sequence")
    init_sub.add_parser("shutdown", help="Run shutdown sequence")

    # ------------------------------------------------------------------ cron
    cron_p = subparsers.add_parser("cron", help="Cron job scheduling")
    cron_sub = cron_p.add_subparsers(dest="cron_command", metavar="<cron-command>")

    cron_sub.add_parser("list", help="List cron jobs")

    cron_add = cron_sub.add_parser("add", help="Add a new cron job")
    cron_add.add_argument("name", help="Job name")
    cron_add.add_argument("--schedule", required=True, help="Cron schedule expression")
    cron_add.add_argument("--cmd", required=True, dest="cmd", help="Command to run")

    cron_remove = cron_sub.add_parser("remove", help="Remove a cron job")
    cron_remove.add_argument("id", help="Job ID")

    cron_enable = cron_sub.add_parser("enable", help="Enable a cron job")
    cron_enable.add_argument("id", help="Job ID")

    cron_disable = cron_sub.add_parser("disable", help="Disable a cron job")
    cron_disable.add_argument("id", help="Job ID")

    # ------------------------------------------------------------------ clip
    clip_p = subparsers.add_parser("clip", help="Clipboard management")
    clip_sub = clip_p.add_subparsers(dest="clip_command", metavar="<clip-command>")

    clip_copy = clip_sub.add_parser("copy", help="Copy text to clipboard")
    clip_copy.add_argument("text", help="Text to copy")

    clip_sub.add_parser("paste", help="Paste from clipboard")

    clip_hist = clip_sub.add_parser("history", help="Show clipboard history")
    clip_hist.add_argument(
        "-n", "--limit", type=int, default=10, help="Max entries to show (default: 10)",
    )

    clip_sub.add_parser("clear", help="Clear clipboard history")

    # ------------------------------------------------------------------ notify
    notify_p = subparsers.add_parser("notify", help="Notification management")
    notify_sub = notify_p.add_subparsers(dest="notify_command", metavar="<notify-command>")

    notify_send = notify_sub.add_parser("send", help="Send a notification")
    notify_send.add_argument("title", help="Notification title")
    notify_send.add_argument("--body", default="", help="Notification body")
    notify_send.add_argument(
        "--level", default="info",
        help="Notification level: info, warning, warn, error, success (default: info)",
    )

    notify_list = notify_sub.add_parser("list", help="List notifications")
    notify_list.add_argument(
        "--unread", action="store_true", help="Show only unread notifications",
    )

    notify_read = notify_sub.add_parser("read", help="Mark a notification as read")
    notify_read.add_argument("id", help="Notification ID")

    notify_sub.add_parser("clear", help="Clear all notifications")

    # ------------------------------------------------------------------ plugin
    plugin_p = subparsers.add_parser("plugin", help="Plugin management")
    plugin_sub = plugin_p.add_subparsers(dest="plugin_command", metavar="<plugin-command>")

    plugin_sub.add_parser("list", help="List installed plugins")
    plugin_sub.add_parser("scan", help="Scan for available plugins")

    plugin_load = plugin_sub.add_parser("load", help="Load a plugin")
    plugin_load.add_argument("name", help="Plugin name")

    plugin_unload = plugin_sub.add_parser("unload", help="Unload a plugin")
    plugin_unload.add_argument("name", help="Plugin name")

    plugin_create = plugin_sub.add_parser("create", help="Scaffold a new plugin")
    plugin_create.add_argument("name", help="Plugin name")
    plugin_create.add_argument("--description", default="", help="Plugin description")

    # ------------------------------------------------------------------ secret
    secret_p = subparsers.add_parser("secret", help="Secret/credential management")
    secret_sub = secret_p.add_subparsers(dest="secret_command", metavar="<secret-command>")

    secret_set = secret_sub.add_parser("set", help="Store a secret")
    secret_set.add_argument("key", help="Secret key")
    secret_set.add_argument("value", help="Secret value")
    secret_set.add_argument("--namespace", default="default", help="Namespace (default: default)")

    secret_get = secret_sub.add_parser("get", help="Retrieve a secret")
    secret_get.add_argument("key", help="Secret key")
    secret_get.add_argument("--namespace", default="default", help="Namespace (default: default)")

    secret_del = secret_sub.add_parser("delete", help="Delete a secret")
    secret_del.add_argument("key", help="Secret key")
    secret_del.add_argument("--namespace", default="default", help="Namespace (default: default)")

    secret_list = secret_sub.add_parser("list", help="List secrets in a namespace")
    secret_list.add_argument("--namespace", default="default", help="Namespace (default: default)")

    secret_sub.add_parser("namespaces", help="List all namespaces")

    return parser
