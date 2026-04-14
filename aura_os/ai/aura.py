"""AURA AI persona — the primary intelligent assistant for AURA OS.

AURA (Adaptive Unified Runtime Assistant) provides:
- Context-aware responses about the running system
- Command suggestions and explanations
- System state interpretation
- Maintenance guidance
- Operator assistance

The persona layer sits on top of LocalInference but adds:
- System context injection (current state, logs, metrics)
- Conversation history via AuraSession
- Canned intelligent responses when no AI runtime is available
"""

from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional

if TYPE_CHECKING:
    from aura_os.ai.session import AuraSession


AURA_SYSTEM_PROMPT = """You are AURA, the AI assistant built into AURA OS.
You have access to real system information and help the operator manage,
understand, and maintain the running system. Be concise, accurate, and
practical. When suggesting commands, use the AURA CLI format (e.g.
'aura health', 'aura ps', 'aura service list'). If you don't know
something about the system state, say so."""


class AuraPersona:
    """The AURA AI assistant persona.

    Wraps LocalInference with system-context injection and a session-aware
    conversation interface.

    Args:
        session: An optional AuraSession for multi-turn memory.
        model: Override the default AI model name.
        inject_context: If True, prepend live system context to each prompt.
    """

    def __init__(
        self,
        session: Optional["AuraSession"] = None,
        model: Optional[str] = None,
        inject_context: bool = True,
    ):
        self._session = session
        self._model = model
        self._inject_context = inject_context

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def ask(self, user_prompt: str) -> str:
        """Send a prompt to AURA and return the response.

        System context is automatically injected when *inject_context* is True.
        Conversation history from the session is prepended for continuity.
        """
        full_prompt = self._build_prompt(user_prompt)
        response = self._query(full_prompt)
        if self._session:
            self._session.add_exchange(user_prompt, response)
        return response

    def explain_command(self, command: str) -> str:
        """Ask AURA to explain what an AURA command does."""
        return self.ask(f"Explain what this AURA command does: {command}")

    def suggest_fix(self, issue: str) -> str:
        """Ask AURA to suggest a fix for a described issue."""
        return self.ask(f"The system has this issue: {issue}. What should I do?")

    def analyze_log(self, log_entries: List[str]) -> str:
        """Ask AURA to analyze a list of log entries."""
        joined = "\n".join(log_entries[:20])
        return self.ask(
            f"Analyze these system log entries and summarize any concerns:\n{joined}"
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_prompt(self, user_prompt: str) -> str:
        parts = []

        # System context block
        if self._inject_context:
            ctx = self._gather_context()
            if ctx:
                parts.append(f"[System Context]\n{ctx}\n")

        # Session history
        if self._session:
            history = self._session.recent_exchanges(3)
            if history:
                history_text = "\n".join(
                    f"User: {e['user']}\nAURA: {e['aura']}"
                    for e in history
                )
                parts.append(f"[Recent Conversation]\n{history_text}\n")

        parts.append(f"User: {user_prompt}")
        return "\n".join(parts)

    def _gather_context(self) -> str:
        lines = []
        try:
            import platform
            lines.append(f"OS: {platform.system()} {platform.release()}")
        except Exception:
            pass
        try:
            from aura_os.kernel.syslog import Syslog
            entries = Syslog().tail(3)
            if entries:
                recent = "; ".join(e.get("message", "") for e in entries[-3:])
                lines.append(f"Recent logs: {recent}")
        except Exception:
            pass
        try:
            import psutil
            mem = psutil.virtual_memory()
            cpu = psutil.cpu_percent(interval=0.1)
            lines.append(f"CPU: {cpu:.0f}%  RAM: {mem.percent:.0f}%")
        except ImportError:
            pass
        except Exception:
            pass
        return "\n".join(lines)

    def _query(self, prompt: str) -> str:
        try:
            from aura_os.ai.inference import LocalInference
            return LocalInference().query(
                prompt,
                model=self._model,
                system=AURA_SYSTEM_PROMPT,
            )
        except Exception:
            return self._fallback_response(prompt)

    def _fallback_response(self, prompt: str) -> str:
        """Return a canned helpful response when no AI runtime is available."""
        prompt_lower = prompt.lower()
        if any(w in prompt_lower for w in ("health", "status", "ok")):
            return (
                "Run 'aura health' for a full system dashboard, "
                "'aura validate' for an integrity check, "
                "or 'aura diag' for detailed diagnostics."
            )
        if any(w in prompt_lower for w in ("process", "running", "ps")):
            return "Run 'aura ps' to list running processes."
        if any(w in prompt_lower for w in ("service", "daemon")):
            return "Run 'aura service list' to see all services."
        if any(w in prompt_lower for w in ("log", "error", "warn")):
            return "Run 'aura log tail' to view recent system logs."
        if any(w in prompt_lower for w in ("repair", "fix", "broken")):
            return (
                "Run 'aura repair' to attempt automatic repairs, "
                "or 'aura validate' to identify what's wrong first."
            )
        if any(w in prompt_lower for w in ("disk", "space", "storage")):
            return "Run 'aura disk df' to check disk usage."
        if any(w in prompt_lower for w in ("network", "internet", "connect")):
            return "Run 'aura net status' to check network connectivity."
        return (
            "[AURA] No AI runtime detected. "
            "Install Ollama (https://ollama.com) for full AI features. "
            "Run 'aura help' to see all available commands."
        )
