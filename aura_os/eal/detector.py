"""Environment detection utilities for AURA OS."""

import os
import platform
import shutil
import sys
import tempfile
from typing import Dict, Optional


def is_termux() -> bool:
    """Return True if running inside Termux on Android."""
    if os.environ.get("TERMUX_VERSION"):
        return True
    return os.path.isdir("/data/data/com.termux")


def is_android() -> bool:
    """Return True if running on Android (including Termux)."""
    if is_termux():
        return True
    if os.path.isfile("/system/build.prop"):
        return True
    uname = platform.uname()
    return "android" in uname.release.lower() or "android" in uname.version.lower()


def is_linux() -> bool:
    """Return True if running on Linux."""
    return sys.platform.startswith("linux")


def is_macos() -> bool:
    """Return True if running on macOS."""
    return sys.platform == "darwin"


def is_windows() -> bool:
    """Return True if running on Windows."""
    return sys.platform in ("win32", "cygwin")


def get_platform() -> str:
    """Return a normalised platform identifier string."""
    if is_termux():
        return "termux"
    if is_android():
        return "android"
    if is_macos():
        return "macos"
    if is_linux():
        return "linux"
    if is_windows():
        return "windows"
    return "unknown"


def get_available_binaries() -> Dict[str, Optional[str]]:
    """Return a mapping of binary names to their full paths (or None)."""
    binaries = [
        "python3", "node", "bash", "curl", "wget", "git",
        "gcc", "make", "ffmpeg", "sqlite3", "ollama",
    ]
    return {name: shutil.which(name) for name in binaries}


def get_storage_paths() -> Dict[str, str]:
    """Return key storage paths relevant to AURA OS."""
    home_dir = os.path.expanduser("~")
    aura_home = os.environ.get("AURA_HOME", os.path.join(home_dir, ".aura"))

    if is_termux():
        temp_dir = "/data/data/com.termux/files/usr/tmp"
    else:
        temp_dir = tempfile.gettempdir()

    return {
        "home_dir": home_dir,
        "temp_dir": temp_dir,
        "aura_home": aura_home,
        "data_dir": os.path.join(aura_home, "data"),
    }


def get_permissions() -> Dict[str, bool]:
    """Return read/write permission flags for key paths."""
    paths = get_storage_paths()
    result: Dict[str, bool] = {}
    for label, path in paths.items():
        result[f"{label}_readable"] = os.access(path, os.R_OK) if os.path.exists(path) else False
        result[f"{label}_writable"] = os.access(path, os.W_OK) if os.path.exists(path) else False
    return result
