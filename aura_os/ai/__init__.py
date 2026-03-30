"""AI subsystem package for AURA OS."""

from .model_manager import ModelManager
from .inference import LocalInference
from .knowledge import build_system_prompt, lookup, AURA_COMMANDS, LINUX_COMMANDS, CODEBASE_ARCHITECTURE

__all__ = [
    "ModelManager",
    "LocalInference",
    "build_system_prompt",
    "lookup",
    "AURA_COMMANDS",
    "LINUX_COMMANDS",
    "CODEBASE_ARCHITECTURE",
]
