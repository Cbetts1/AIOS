"""``aura help`` command handler — show all available commands."""

from aura_os import __version__


class HelpCommand:
    """Display a human-friendly listing of every AURA command."""

    _HELP_TEXT = f"""\
AURA OS v{__version__} — Adaptive User-space Runtime Architecture

Commands:
  aura help                  Show this help message
  aura sys [--watch]         System information (CPU, RAM, disk)
  aura env [--json]          Environment information
  aura run <file> [args]     Run a script file (.py/.sh/.js/…)
  aura ai "<prompt>"         Query a local AI model
  aura shell                 Launch the interactive AURA shell

  aura fs ls [path]          List files / directories
  aura fs cat <file>         Print file contents
  aura fs find [root] [pat]  Search for files
  aura fs mkdir <path>       Create directory
  aura fs rm <path>          Delete file or directory
  aura fs edit <file>        Open in text editor

  aura pkg install <name>    Install a package
  aura pkg remove <name>     Remove a package
  aura pkg list              List installed packages
  aura pkg search <query>    Search for packages
  aura pkg info <name>       Show package details

  aura repo create <name>    Init a new git repository
  aura repo list             List managed repositories
  aura repo status [path]    Show git status
  aura repo clone <url>      Clone a remote repository

  aura auto list             List automation tasks
  aura auto create <name>    Create a task template
  aura auto run <name>       Execute a task

  aura ps                    List tracked processes
  aura kill <pid> [-s SIG]   Send signal to a process

  aura service list          List all services
  aura service start <name>  Start a service
  aura service stop <name>   Stop a service
  aura service create <name> Create a service definition

  aura log [tail|search|clear]  View / search system logs

Use 'aura <command> --help' for detailed usage of any command.
"""

    def execute(self, args, eal) -> int:
        print(self._HELP_TEXT)
        return 0
