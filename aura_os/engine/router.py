"""Command router for AURA OS engine."""

from typing import Dict, Type


class CommandRouter:
    """Dispatches parsed CLI arguments to the appropriate command handler.

    Handlers are registered by name via :meth:`register`.  When
    :meth:`dispatch` is called it looks up the correct handler class,
    instantiates it, and calls its ``execute(args, eal)`` method.

    All handler classes must implement::

        def execute(self, args, eal) -> int:
            ...
    """

    def __init__(self):
        self._handlers: Dict[str, Type] = {}

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(self, name: str, handler_class: Type):
        """Register *handler_class* for the command named *name*."""
        self._handlers[name] = handler_class

    # ------------------------------------------------------------------
    # Dispatch
    # ------------------------------------------------------------------

    def dispatch(self, parsed_args, eal) -> int:
        """Find the correct handler and invoke it.

        Returns the exit code returned by the handler (0 = success).
        Returns 1 if no handler is registered for the command.
        Returns 2 if *parsed_args.command* is None (no sub-command given).
        """
        command = getattr(parsed_args, "command", None)

        if command is None:
            # No sub-command: print help hint
            print("No command given. Run 'aura --help' for usage.")
            return 2

        handler_class = self._handlers.get(command)
        if handler_class is None:
            print(f"Unknown command '{command}'. Run 'aura --help' for usage.")
            return 1

        handler = handler_class()
        return handler.execute(parsed_args, eal)
