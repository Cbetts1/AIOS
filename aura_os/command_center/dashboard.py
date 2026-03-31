"""Command Center — terminal dashboard for AURA OS.

Draws a rich, multi-panel dashboard in the terminal using only the
standard library (no curses dependency required).  Panels include:

  • System Status  (CPU, memory, disk)
  • Aura AI Chat   (interactive prompt)
  • Services       (running / stopped)
  • Processes      (tracked PIDs)
  • Recent Logs    (last syslog entries)
"""

from __future__ import annotations

import os
import platform
import shutil
import textwrap
import time
from typing import TYPE_CHECKING, List, Optional

if TYPE_CHECKING:
    from aura_os.eal import EAL

# ── ANSI helpers ────────────────────────────────────────────────────
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"
CYAN = "\033[36m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
MAGENTA = "\033[35m"
BLUE = "\033[34m"
WHITE = "\033[97m"
BG_DARK = "\033[48;5;235m"
CLEAR = "\033[2J\033[H"

HLINE_CHAR = "─"
VLINE_CHAR = "│"
CORNER_TL = "╭"
CORNER_TR = "╮"
CORNER_BL = "╰"
CORNER_BR = "╯"


def _box(title: str, lines: List[str], width: int, color: str = CYAN) -> str:
    """Draw a bordered box with a title and content lines."""
    inner = width - 2
    out: List[str] = []
    # top border
    out.append(f"{color}{CORNER_TL}{HLINE_CHAR} {BOLD}{title}{RESET}{color} "
               f"{HLINE_CHAR * max(0, inner - len(title) - 3)}{CORNER_TR}{RESET}")
    # content
    for line in lines:
        text = line[:inner]
        padding = inner - len(text)
        out.append(f"{color}{VLINE_CHAR}{RESET}{text}{' ' * padding}{color}{VLINE_CHAR}{RESET}")
    # bottom border
    out.append(f"{color}{CORNER_BL}{HLINE_CHAR * inner}{CORNER_BR}{RESET}")
    return "\n".join(out)


class CommandCenter:
    """Terminal-based Command Center for AURA OS."""

    def __init__(self, eal: "EAL"):
        self._eal = eal

    # ── data collectors ─────────────────────────────────────────────

    def _system_status(self) -> List[str]:
        """Collect system status lines."""
        lines: List[str] = []
        uname = platform.uname()
        lines.append(f" OS       : {uname.system} {uname.release}")
        lines.append(f" Host     : {uname.node}")
        lines.append(f" Arch     : {uname.machine}")
        lines.append(f" Python   : {platform.python_version()}")

        # Memory (best-effort)
        try:
            from aura_os.kernel.memory import MemoryTracker
            mem = MemoryTracker().get_system_memory()
            total_mb = mem["total"] // (1024 * 1024) if mem.get("total") else "?"
            used_mb = mem["used"] // (1024 * 1024) if mem.get("used") else "?"
            pct = mem.get("percent", "?")
            lines.append(f" Memory   : {used_mb} MB / {total_mb} MB ({pct}%)")
        except Exception:
            lines.append(" Memory   : (unavailable)")

        # Disk
        try:
            usage = shutil.disk_usage("/")
            total_gb = usage.total / (1024 ** 3)
            used_gb = usage.used / (1024 ** 3)
            lines.append(f" Disk (/) : {used_gb:.1f} GB / {total_gb:.1f} GB")
        except Exception:
            lines.append(" Disk     : (unavailable)")

        return lines

    def _aura_status(self) -> List[str]:
        """Return Aura persona status lines."""
        from aura_os.ai.aura import AuraPersona
        persona = AuraPersona.load()
        lines = [
            f" Name     : {persona.name} v{persona.version}",
            f" Mood     : {persona.mood}",
            f" Caps     : {len(persona.capabilities)}",
        ]
        # AI runtime
        try:
            from aura_os.ai.model_manager import ModelManager
            mm = ModelManager()
            rt = mm.get_active_runtime()
            lines.append(f" Runtime  : {rt or 'none (install ollama)'}")
            models = mm.list_models()
            lines.append(f" Models   : {len(models)} local")
        except Exception:
            lines.append(" Runtime  : (unavailable)")
        return lines

    def _services_panel(self) -> List[str]:
        """List services with status indicators."""
        lines: List[str] = []
        try:
            from aura_os.kernel.service import ServiceManager
            sm = ServiceManager()
            services = sm.list()
            if not services:
                lines.append("  (no services defined)")
            for svc in services[:8]:
                icon = f"{GREEN}●{RESET}" if svc.status == "running" else f"{RED}○{RESET}"
                lines.append(f" {icon} {svc.name:<20} {svc.status}")
        except Exception:
            lines.append("  (unavailable)")
        return lines

    def _processes_panel(self) -> List[str]:
        """List tracked processes."""
        lines: List[str] = []
        try:
            from aura_os.kernel.process import ProcessManager
            pm = ProcessManager()
            procs = pm.list()
            if not procs:
                lines.append("  (no tracked processes)")
            for p in procs[:8]:
                lines.append(f"  PID {p.pid:<8} {p.name:<16} {p.status}")
        except Exception:
            lines.append("  (unavailable)")
        return lines

    def _logs_panel(self) -> List[str]:
        """Show recent syslog entries."""
        lines: List[str] = []
        try:
            from aura_os.kernel.syslog import Syslog
            sl = Syslog()
            entries = sl.get_entries(limit=6)
            if not entries:
                lines.append("  (no log entries)")
            for entry in entries:
                lines.append(f"  {entry}")
        except Exception:
            lines.append("  (unavailable)")
        return lines

    # ── render ──────────────────────────────────────────────────────

    def render(self) -> str:
        """Render the full dashboard as a string."""
        try:
            term_width = os.get_terminal_size().columns
        except OSError:
            term_width = 80
        panel_w = max(40, term_width)

        header = (
            f"\n  {BOLD}{MAGENTA}╔══════════════════════════════════════╗{RESET}\n"
            f"  {BOLD}{MAGENTA}║   AURA OS — Command Center          ║{RESET}\n"
            f"  {BOLD}{MAGENTA}╚══════════════════════════════════════╝{RESET}\n"
        )

        parts = [header]
        parts.append(_box("System Status", self._system_status(), panel_w, CYAN))
        parts.append("")
        parts.append(_box("Aura AI", self._aura_status(), panel_w, MAGENTA))
        parts.append("")
        parts.append(_box("Services", self._services_panel(), panel_w, GREEN))
        parts.append("")
        parts.append(_box("Processes", self._processes_panel(), panel_w, YELLOW))
        parts.append("")
        parts.append(_box("Recent Logs", self._logs_panel(), panel_w, BLUE))
        parts.append("")
        parts.append(
            f"  {DIM}Commands: "
            f"'aura ai <prompt>' | 'aura sys' | 'aura service list' | "
            f"'aura center' | 'exit'{RESET}"
        )
        parts.append("")

        return "\n".join(parts)

    def show(self) -> None:
        """Print the dashboard to stdout."""
        print(CLEAR, end="")
        print(self.render())

    # ── interactive loop ────────────────────────────────────────────

    def run_interactive(self) -> None:
        """Run the Command Center in interactive mode.

        Displays the dashboard, then drops into a prompt where the user
        can issue commands or talk to Aura.
        """
        from aura_os.ai.aura import AuraPersona
        from aura_os.ai.session import Session, SessionManager
        from aura_os.ai.inference import LocalInference
        from aura_os.ai.model_manager import ModelManager
        from aura_os.engine.cli import build_parser
        from aura_os.engine.router import CommandRouter
        from aura_os.engine.commands.run import RunCommand
        from aura_os.engine.commands.ai import AiCommand
        from aura_os.engine.commands.env_cmd import EnvCommand
        from aura_os.engine.commands.pkg import PkgCommand
        from aura_os.engine.commands.sys_cmd import SysCommand
        from aura_os.engine.commands.ps_cmd import PsCommand
        from aura_os.engine.commands.kill_cmd import KillCommand
        from aura_os.engine.commands.service_cmd import ServiceCommand
        from aura_os.engine.commands.log_cmd import LogCommand

        persona = AuraPersona.load()
        sm = SessionManager()
        session = sm.new_session()
        mm = ModelManager()
        inference = LocalInference(model_manager=mm)

        router = CommandRouter()
        for name, cls in [
            ("run", RunCommand), ("ai", AiCommand), ("env", EnvCommand),
            ("pkg", PkgCommand), ("sys", SysCommand), ("ps", PsCommand),
            ("kill", KillCommand), ("service", ServiceCommand), ("log", LogCommand),
        ]:
            router.register(name, cls)
        parser = build_parser()

        # Show dashboard
        self.show()
        print(f"  {BOLD}{MAGENTA}Aura>{RESET} {persona.greet()}")
        print()

        while True:
            try:
                line = input(f"  {BOLD}{MAGENTA}You>{RESET} ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break

            if not line:
                continue

            lower = line.lower()
            if lower in ("exit", "quit", "bye"):
                print(f"  {MAGENTA}Aura>{RESET} Goodbye! Session saved.")
                session.save()
                break

            if lower == "dashboard":
                self.show()
                continue

            if lower == "help":
                self._print_help()
                continue

            session.add_user_message(line)

            # Try as AURA command first
            handled = self._try_command(line, parser, router)
            if handled:
                session.add_aura_message("(command executed)")
                continue

            # Otherwise, send to Aura AI
            response = self._ask_aura(line, inference, persona)
            session.add_aura_message(response)
            print(f"  {MAGENTA}Aura>{RESET} {response}")
            print()

    # ── helpers ─────────────────────────────────────────────────────

    def _try_command(self, line: str, parser, router) -> bool:
        """Attempt to dispatch *line* as an AURA CLI command.  Returns True if handled."""
        try:
            parsed = parser.parse_args(line.split())
            if parsed.command:
                router.dispatch(parsed, self._eal)
                return True
        except (SystemExit, Exception):
            pass
        return False

    def _ask_aura(self, prompt: str, inference, persona) -> str:
        """Query the AI backend with Aura's persona context."""
        full_prompt = f"[System: {persona.build_system_prompt()}]\nUser: {prompt}\nAura:"
        try:
            return inference.query(full_prompt)
        except Exception:
            return (
                "I'm not connected to an AI backend right now.  "
                "Install ollama (https://ollama.com) to unlock my full potential, "
                "or type a command like 'sys', 'ps', 'service list'."
            )

    def _print_help(self) -> None:
        print(f"""
  {BOLD}AURA OS Command Center — Help{RESET}
  {HLINE_CHAR * 50}

  {BOLD}Dashboard:{RESET}
    dashboard         Refresh the dashboard view
    help              Show this help message
    exit / quit       Exit the Command Center

  {BOLD}System Commands:{RESET}
    sys               System status (CPU, memory, disk)
    ps                List tracked processes
    service list      List all services
    log tail          Show recent log entries
    env               Environment information
    pkg list          List installed packages

  {BOLD}AI / Aura:{RESET}
    ai <prompt>       Direct AI query
    <anything else>   Ask Aura in natural language

  {BOLD}Files & Scripts:{RESET}
    run <file>        Execute a script
""")
