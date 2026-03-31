"""'aura web' — launch the Command Center web server."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from argparse import Namespace
    from aura_os.eal import EAL


class WebCommand:
    """Start the Command Center web server for remote/cloud access."""

    def execute(self, args: "Namespace", eal: "EAL") -> int:
        from aura_os.command_center.web import serve

        host = getattr(args, "host", "127.0.0.1")
        port = getattr(args, "port", 7070)
        serve(eal, host=host, port=port)
        return 0
