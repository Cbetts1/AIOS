"""
Core Command Registry
Stores registered commands, their handlers, and metadata.
"""

from typing import Callable, Dict, Any, Optional


class CommandRegistry:
    """
    A simple registry that maps command names (strings) to handler functions.

    Each entry stores:
      - handler: callable(args: list, ctx: dict) -> None
      - description: short help text
      - usage: usage string shown in help
    """

    def __init__(self):
        self._commands: Dict[str, Dict[str, Any]] = {}

    def register(
        self,
        name: str,
        handler: Callable,
        description: str = "",
        usage: str = "",
    ):
        self._commands[name] = {
            "handler": handler,
            "description": description,
            "usage": usage or name,
        }

    def get(self, name: str) -> Optional[Dict[str, Any]]:
        return self._commands.get(name)

    def all_commands(self) -> Dict[str, Dict[str, Any]]:
        return dict(self._commands)

    def names(self):
        return list(self._commands.keys())
