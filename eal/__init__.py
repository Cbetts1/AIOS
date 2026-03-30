"""
Environment Abstraction Layer (EAL)
Detects the host environment and provides a unified API for AURA OS modules.
"""

import os
import sys
import json
import shutil
import platform
import subprocess
from pathlib import Path


AURA_HOME = Path(os.environ.get("AURA_HOME", Path(__file__).resolve().parent.parent))


def detect_environment():
    """
    Detect the host operating environment and return a capability map.

    Returns a dict with:
      - env_type: "android", "linux", "macos", "windows", "unknown"
      - is_termux: bool
      - binaries: dict of binary name -> path (or None)
      - storage_root: writable path used as AURA home
      - has_network: bool
      - ram_mb: int approximate RAM in MB (0 if unknown)
      - capabilities: list of enabled feature flags
    """
    env = {}

    # --- OS type detection ---
    system = platform.system().lower()
    is_termux = "com.termux" in os.environ.get("PREFIX", "") or \
                os.path.isdir("/data/data/com.termux")

    if is_termux:
        env["env_type"] = "android"
        env["is_termux"] = True
    elif system == "linux":
        env["env_type"] = "linux"
        env["is_termux"] = False
    elif system == "darwin":
        env["env_type"] = "macos"
        env["is_termux"] = False
    elif system == "windows":
        env["env_type"] = "windows"
        env["is_termux"] = False
    else:
        env["env_type"] = "unknown"
        env["is_termux"] = False

    # --- Binary availability ---
    binaries_to_check = [
        "python3", "python", "node", "npm", "bash", "sh",
        "git", "curl", "wget", "pip3", "pip", "flask",
        "termux-info", "pkg",
    ]
    binaries = {}
    for b in binaries_to_check:
        path = shutil.which(b)
        binaries[b] = path
    env["binaries"] = binaries

    # --- Python executable ---
    env["python"] = binaries.get("python3") or binaries.get("python") or sys.executable

    # --- Storage root ---
    env["storage_root"] = str(AURA_HOME)

    # --- Network check (offline-first: just detect interface existence) ---
    try:
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        try:
            sock.connect(("8.8.8.8", 53))
            env["has_network"] = True
        finally:
            sock.close()
    except Exception:
        env["has_network"] = False

    # --- RAM detection ---
    env["ram_mb"] = _detect_ram_mb()

    # --- Capability flags ---
    caps = []
    if binaries.get("node"):
        caps.append("node")
    if binaries.get("python3") or binaries.get("python"):
        caps.append("python")
    if binaries.get("git"):
        caps.append("git")
    if binaries.get("flask") or _python_module_available("flask"):
        caps.append("flask")
    if env["ram_mb"] == 0 or env["ram_mb"] >= 512:
        caps.append("web_ui")
    else:
        caps.append("terminal_ui")
    if env["ram_mb"] == 0 or env["ram_mb"] >= 1024:
        caps.append("heavy_modules")
    if is_termux:
        caps.append("termux")
    caps.append("terminal_ui")  # always available
    env["capabilities"] = list(set(caps))

    return env


def _detect_ram_mb():
    """Return total RAM in MB, or 0 if unknown."""
    try:
        if platform.system().lower() == "linux":
            with open("/proc/meminfo") as f:
                for line in f:
                    if line.startswith("MemTotal"):
                        kb = int(line.split()[1])
                        return kb // 1024
        elif platform.system().lower() == "darwin":
            out = subprocess.check_output(["sysctl", "-n", "hw.memsize"], text=True)
            return int(out.strip()) // (1024 * 1024)
    except Exception:
        pass
    return 0


def _python_module_available(module_name):
    """Return True if a Python module can be imported."""
    import importlib.util
    return importlib.util.find_spec(module_name) is not None


def get_adapter(env_map=None):
    """
    Return the appropriate EAL adapter instance based on the environment.
    """
    if env_map is None:
        env_map = detect_environment()

    env_type = env_map.get("env_type", "unknown")

    if env_map.get("is_termux") or env_type == "android":
        from eal.adapters.android import AndroidAdapter
        return AndroidAdapter(env_map)
    elif env_type == "macos":
        from eal.adapters.macos import MacOSAdapter
        return MacOSAdapter(env_map)
    elif env_type == "linux":
        from eal.adapters.linux import LinuxAdapter
        return LinuxAdapter(env_map)
    else:
        from eal.adapters.fallback import FallbackAdapter
        return FallbackAdapter(env_map)


def load_env_map(cache_path=None):
    """
    Load (or refresh) the environment capability map.
    Caches the result to disk so modules can read it quickly.
    """
    if cache_path is None:
        cache_path = AURA_HOME / "configs" / "env_map.json"

    env_map = detect_environment()

    try:
        cache_path = Path(cache_path)
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        with open(cache_path, "w") as f:
            json.dump(env_map, f, indent=2)
    except Exception:
        pass  # non-fatal

    return env_map
