"""Kernel subsystem package for AURA OS."""

from .scheduler import Scheduler, Task
from .memory import MemoryTracker
from .ipc import IPCChannel
from .process import ProcessManager, ProcessEntry
from .service import ServiceManager, ServiceEntry
from .syslog import Syslog
from .network import NetworkManager
from .events import EventBus, NotificationManager
from .cron import CronScheduler, CronJob
from .clipboard import ClipboardManager
from .plugins import PluginManager, PluginMeta
from .secrets import SecretStore

__all__ = [
    "Scheduler",
    "Task",
    "MemoryTracker",
    "IPCChannel",
    "ProcessManager",
    "ProcessEntry",
    "ServiceManager",
    "ServiceEntry",
    "Syslog",
    "NetworkManager",
    "EventBus",
    "NotificationManager",
    "CronScheduler",
    "CronJob",
    "ClipboardManager",
    "PluginManager",
    "PluginMeta",
    "SecretStore",
]
