# Changelog

All notable changes to AURA OS are documented here.  
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).  
Versions follow [Semantic Versioning](https://semver.org/).

---

## [Unreleased]

### Added
- `pyproject.toml` for `pip install .` packaging with optional extras (`[ai]`, `[web]`, `[system]`, `[crypto]`, `[all]`, `[dev]`)
- GitHub Actions CI workflow (`ci.yml`) — matrix of Python 3.8 / 3.10 / 3.12 on Linux & macOS
- `CONTRIBUTING.md` contribution guide
- `LICENSE` (MIT)
- `CHANGELOG.md` (this file)

### Fixed
- `test_list_system_processes` and `test_process_tree_self` now skip gracefully when `psutil` is not installed

---

## [0.2.0] — 2024-xx-xx

### Added
- 22 CLI commands: `run`, `ai`, `env`, `pkg`, `sys`, `ps`, `kill`, `service`, `log`, `user`, `net`, `init`, `notify`, `cron`, `clip`, `plugin`, `secret`, `disk`, `health`, `monitor`, `web`, `shell`
- macOS EAL adapter (`sysctl` memory, `sw_vers` version, Apple Silicon detection)
- Windows EAL adapter (`winreg`, `psutil`/`wmic`, `winget`/`choco`/`scoop`)
- Fernet-encrypted secret store with PBKDF2 key derivation (100 000 iterations), XOR fallback
- Pub/sub event bus (`aura_os/kernel/events.py`)
- Cron scheduler (`aura_os/kernel/cron.py`)
- Cross-platform clipboard (`aura_os/kernel/clipboard.py`)
- Plugin system with hot-reload (`aura_os/kernel/plugins.py`)
- Virtual filesystem (`aura_os/fs/`): VFS, KVStore, procfs, FHS layout
- Package registry & manager (`aura_os/pkg/`)
- User management with PBKDF2 auth (`aura_os/users/`)
- Extended network manager (`aura_os/net/`)
- Boot/shutdown sequencer (`aura_os/init/`)
- REST API server (`aura_os/web/`) — Flask with stdlib fallback on port 7070
- Interactive REPL shell with alias support and script mode
- Portable mode via `.aura_portable` marker and `AURA_PORTABLE=1` env var

---

## [0.1.0] — initial release

### Added
- Core EAL with Linux, Android/Termux, and Fallback adapters
- Basic CLI engine with `run`, `ai`, `env`, `pkg`, `sys`
- Offline AI assistant (rule-based with optional GGUF model)
- Bootstrap installer (`install.sh`)
