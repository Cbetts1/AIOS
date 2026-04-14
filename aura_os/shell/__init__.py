"""Interactive Shell module for AURA OS.

Provides a real command-line shell with:
- Real OS command execution via subprocess
- Built-in AURA commands
- Variable expansion
- History management
- Pipe and redirect support
- Tab completion (when readline is available)
"""

from .repl import AuraShell

__all__ = ["AuraShell"]
