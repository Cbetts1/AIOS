"""AI subsystem package for AURA OS."""

from .model_manager import ModelManager
from .inference import LocalInference

__all__ = ["ModelManager", "LocalInference"]
