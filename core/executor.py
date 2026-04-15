"""
Capability Forge OS — Capability executor.

For the v1 prototype, execution returns a structured result dict without
spawning sandboxed subprocesses.
"""

from typing import Any, Dict, Optional

from core.models import Capability


class ExecutionResult:
    """Structured result returned by the executor."""

    def __init__(
        self,
        capability_name: str,
        status: str,
        intent: str,
        result: str,
        capability_id: Optional[str] = None,
    ) -> None:
        self.capability_name = capability_name
        self.capability_id = capability_id or capability_name
        self.status = status
        self.intent = intent
        self.result = result

    def to_dict(self) -> Dict[str, Any]:
        return {
            "capability_name": self.capability_name,
            "capability_id": self.capability_id,
            "status": self.status,
            "intent": self.intent,
            "result": self.result,
        }

    def __str__(self) -> str:
        return (
            f"[{self.status}] {self.capability_name}: {self.result}"
        )


class CapabilityExecutor:
    """Executes a matched Capability and returns an ExecutionResult."""

    def execute(self, capability: Capability, intent: str) -> ExecutionResult:
        """
        Execute *capability* for the given *intent*.

        In the v1 prototype this is a simulated execution that confirms the
        capability was matched and returns a human-readable result string.
        """
        if capability.status != "active":
            return ExecutionResult(
                capability_name=capability.name,
                capability_id=capability.id,
                status="skipped",
                intent=intent,
                result=f"Capability '{capability.name}' is not active (status={capability.status}).",
            )

        result_text = self._simulate(capability, intent)
        return ExecutionResult(
            capability_name=capability.name,
            capability_id=capability.id,
            status="success",
            intent=intent,
            result=result_text,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _simulate(self, cap: Capability, intent: str) -> str:
        inputs_str = ", ".join(cap.inputs) if cap.inputs else "none"
        outputs_str = ", ".join(cap.outputs) if cap.outputs else "none"
        return (
            f"Capability '{cap.name}' executed.\n"
            f"  Description : {cap.description}\n"
            f"  Type        : {cap.type}\n"
            f"  Inputs      : {inputs_str}\n"
            f"  Outputs     : {outputs_str}\n"
            f"  Runtime     : {cap.runtime}\n"
            f"  Entrypoint  : {cap.entrypoint or 'n/a'}\n"
            f"  Intent      : {intent}"
        )
