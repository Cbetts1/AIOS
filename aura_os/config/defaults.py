"""Default configuration values for AURA OS."""

DEFAULT_CONFIG = {
    "version": "0.2.0",
    "log_level": "INFO",
    "ai": {
        "default_model": "auto",
        "max_tokens": 512,
        "runtime": "auto"
    },
    "aura": {
        "name": "Aura",
        "greeting": (
            "Hello!  I'm Aura, your AI operating system.  "
            "Type a command or ask me anything.  Use 'help' to see what I can do."
        ),
        "persona_file": "~/.aura/data/aura_persona.json",
        "sessions_dir": "~/.aura/data/sessions"
    },
    "shell": {
        "prompt": "aura> ",
        "history_file": "~/.aura/data/.history"
    },
    "command_center": {
        "web_host": "127.0.0.1",
        "web_port": 7070,
        "auto_open_browser": False
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
