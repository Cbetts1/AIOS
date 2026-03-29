"""EAL adapters package."""

from .android import AndroidAdapter
from .linux import LinuxAdapter
from .fallback import FallbackAdapter

__all__ = ["AndroidAdapter", "LinuxAdapter", "FallbackAdapter"]
