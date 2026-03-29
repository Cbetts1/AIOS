"""Default configuration values for AURA OS."""

DEFAULT_CONFIG = {
    "version": "0.1.0",
    "log_level": "INFO",
    "ai": {
        "default_model": "auto",
        "max_tokens": 512,
        "runtime": "auto"
    },
    "shell": {
        "prompt": "aura> ",
        "history_file": "~/.aura/data/.history"
    },
    "pkg": {
        "registry_url": None,  # offline mode
        "install_dir": "~/.aura/pkg/installed"
    },
    "fs": {
        "data_dir": "~/.aura/data",
        "max_vfs_size_mb": 1024
    }
}
