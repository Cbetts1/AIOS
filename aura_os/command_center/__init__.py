"""Command Center for AURA OS.

The Command Center is the primary operator control plane, providing a
real-time dashboard and administrative interface for managing all aspects
of the running system.

Usage::

    from aura_os.command_center import CommandCenter
    cc = CommandCenter(eal)
    cc.show()          # print one-shot status dashboard
    cc.run_tui()       # interactive TUI loop (Ctrl-C to exit)
"""

from .center import CommandCenter

__all__ = ["CommandCenter"]
