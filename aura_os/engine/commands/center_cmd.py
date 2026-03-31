"""'aura center' — launch the Command Center dashboard."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from argparse import Namespace
    from aura_os.eal import EAL


class CenterCommand:
    """Launch the interactive Command Center dashboard."""

    def execute(self, args: "Namespace", eal: "EAL") -> int:
        from aura_os.command_center.dashboard import CommandCenter
        cc = CommandCenter(eal)
        cc.run_interactive()
        return 0
