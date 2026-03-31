"""'aura start' — clean OS boot sequence with Aura greeting."""

from __future__ import annotations

import platform
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from argparse import Namespace
    from aura_os.eal import EAL

# ANSI
BOLD = "\033[1m"
RESET = "\033[0m"
MAGENTA = "\033[35m"
CYAN = "\033[36m"
GREEN = "\033[32m"
DIM = "\033[2m"
CLEAR = "\033[2J\033[H"


def _boot_animation() -> None:
    """Display a brief boot sequence."""
    steps = [
        ("Initialising kernel", "kernel"),
        ("Loading environment abstraction layer", "eal"),
        ("Detecting platform", "detect"),
        ("Starting system logger", "syslog"),
        ("Loading Aura AI persona", "aura"),
        ("Command Center ready", "center"),
    ]
    print(f"\n  {BOLD}{MAGENTA}AURA OS — Boot Sequence{RESET}\n")
    for label, _tag in steps:
        print(f"  {DIM}[{GREEN}✓{RESET}{DIM}]{RESET} {label}")
        time.sleep(0.12)
    print()


class StartCommand:
    """Clean boot experience — system check + Aura greeting + Command Center."""

    def execute(self, args: "Namespace", eal: "EAL") -> int:
        from aura_os.ai.aura import AuraPersona
        from aura_os.kernel.syslog import Syslog

        syslog = Syslog()

        print(CLEAR, end="")
        _boot_animation()

        # Load or create Aura persona
        persona = AuraPersona.load()
        persona.mood = "active"
        persona.save()

        syslog.info("kern", "AURA OS boot sequence complete")

        uname = platform.uname()
        print(f"  {CYAN}System:{RESET}  {uname.system} {uname.release} ({uname.machine})")
        print(f"  {CYAN}Host:{RESET}    {uname.node}")
        print(f"  {CYAN}Python:{RESET}  {platform.python_version()}")
        print()
        print(f"  {BOLD}{MAGENTA}Aura>{RESET} {persona.greet()}")
        print()

        # Drop into Command Center
        from aura_os.command_center.dashboard import CommandCenter
        cc = CommandCenter(eal)
        cc.run_interactive()
        return 0
