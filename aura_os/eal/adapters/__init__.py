"""EAL adapters package."""

from .android import AndroidAdapter
from .linux import LinuxAdapter
from .macos import MacOSAdapter
from .fallback import FallbackAdapter

__all__ = ["AndroidAdapter", "LinuxAdapter", "MacOSAdapter", "FallbackAdapter"]
