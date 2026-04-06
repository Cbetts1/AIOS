"""
AURA OS Bootstrap / Startup
Initialises the runtime, creates the directory tree, and launches the system.

.. deprecated::
    This legacy ``boot/`` package is superseded by ``aura_os/init/``.
    New code should use ``aura_os.init.sequence.InitManager`` instead.
"""

import os
import sys
import json
from pathlib import Path


# Ensure the AIOS repo root is always on sys.path when this script is run directly
AURA_ROOT = Path(__file__).resolve().parent.parent
if str(AURA_ROOT) not in sys.path:
    sys.path.insert(0, str(AURA_ROOT))


def _ensure_dirs(aura_home: Path):
    """Create all required runtime directories."""
    dirs = [
        "configs", "logs", "models", "tasks", "repos",
        "ui/templates", "data",
    ]
    for d in dirs:
        (aura_home / d).mkdir(parents=True, exist_ok=True)


def _write_default_config(aura_home: Path, env_map: dict):
    """Write system.json if it doesn't exist."""
    cfg_path = aura_home / "configs" / "system.json"
    if cfg_path.exists():
        return

    config = {
        "version": "1.0.0",
        "env_type": env_map.get("env_type", "unknown"),
        "storage_root": str(aura_home),
        "web_ui_port": 7070,
        "web_ui_host": "127.0.0.1",
        "ai_backend": "auto",
        "log_level": "info",
    }
    cfg_path.write_text(json.dumps(config, indent=2))


def _setup_termux_boot(aura_home: Path, adapter):
    """Register AURA with Termux:Boot if available."""
    try:
        from eal.adapters.android import AndroidAdapter
        if not isinstance(adapter, AndroidAdapter):
            return
        boot_script = aura_home / "boot" / "aura_start.sh"
        boot_script.parent.mkdir(parents=True, exist_ok=True)
        boot_script.write_text(
            f"#!/data/data/com.termux/files/usr/bin/bash\n"
            f"export AURA_HOME={aura_home}\n"
            f"cd {aura_home}\n"
            f"python3 {aura_home}/aura sys info\n"
        )
        boot_script.chmod(0o755)
        adapter.setup_termux_boot(boot_script)
    except Exception:
        pass


def _init_vfs(aura_home: Path):
    """Initialize the virtual FHS under aura_home/data/."""
    try:
        import sys as _sys
        repo_root = str(aura_home.parent) if aura_home.name == ".aura" else str(Path(__file__).resolve().parent.parent)
        if repo_root not in _sys.path:
            _sys.path.insert(0, repo_root)
        from aura_os.fs.fhs import VirtualFHS
        VirtualFHS(base_dir=str(aura_home / "data"))
    except Exception:
        pass


def run_bootstrap(aura_home: Path = None):
    """
    Full bootstrap sequence.
    Returns (env_map, adapter) ready for use.
    """
    from eal import load_env_map, get_adapter

    if aura_home is None:
        aura_home = Path(os.environ.get("AURA_HOME", Path.home() / ".aura"))

    os.environ["AURA_HOME"] = str(aura_home)

    print("[aura] Bootstrapping …")

    # 1. Detect environment
    env_map = load_env_map(aura_home / "configs" / "env_map.json")
    adapter = get_adapter(env_map)

    # 2. Create directory structure
    _ensure_dirs(aura_home)

    # 3. Initialize virtual FHS
    _init_vfs(aura_home)

    # 3. Write default config
    _write_default_config(aura_home, env_map)

    # 4. Termux:Boot integration (Android only)
    _setup_termux_boot(aura_home, adapter)

    print(f"[aura] Environment: {env_map['env_type']}")
    print(f"[aura] Storage root: {aura_home}")
    print("[aura] Bootstrap complete.")

    return env_map, adapter


if __name__ == "__main__":
    run_bootstrap()
