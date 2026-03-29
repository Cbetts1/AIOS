"""
AURA OS Modules Package
Provides dynamic loading utilities for AURA modules.
"""

import importlib
from pathlib import Path


def load_module(module_name: str, env_map: dict, adapter):
    """
    Dynamically load and instantiate a named AURA module.
    Returns the module instance or raises ImportError.
    """
    mod = importlib.import_module(f"modules.{module_name}")
    cls_name = module_name.capitalize() + "Module"
    cls = getattr(mod, cls_name)
    return cls(env_map, adapter)


def available_modules(env_map: dict) -> list:
    """
    Return a list of module names that are compatible with the current environment.
    """
    caps = set(env_map.get("capabilities", []))
    modules = []

    # AI module: always available (has rule-based fallback)
    modules.append("ai")

    # Browser module: always available (has terminal fallback)
    modules.append("browser")

    # Repo module: requires git
    if "git" in caps:
        modules.append("repo")

    # Automation module: always available
    modules.append("automation")

    return modules
