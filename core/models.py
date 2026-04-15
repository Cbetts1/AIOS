"""
Capability Forge OS — Capability data model.
"""

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List


@dataclass
class Capability:
    """Represents a single capability in the Capability Forge registry."""

    id: str
    name: str
    repo: str
    description: str
    type: str
    inputs: List[str]
    outputs: List[str]
    runtime: str
    dependencies: List[str]
    ai_routable: bool
    generatable: bool
    status: str
    entrypoint: str
    version: str

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Capability":
        """Create a Capability from a plain dictionary (e.g., parsed JSON)."""
        return cls(
            id=data["id"],
            name=data["name"],
            repo=data.get("repo", ""),
            description=data.get("description", ""),
            type=data.get("type", "generic"),
            inputs=data.get("inputs", []),
            outputs=data.get("outputs", []),
            runtime=data.get("runtime", "python"),
            dependencies=data.get("dependencies", []),
            ai_routable=data.get("ai_routable", True),
            generatable=data.get("generatable", True),
            status=data.get("status", "active"),
            entrypoint=data.get("entrypoint", ""),
            version=data.get("version", "0.1.0"),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to a plain dictionary."""
        return asdict(self)
