# AIOS — AURA OS

**Adaptive User-space Runtime Architecture** — a fully portable, modular, offline-first OS-like layer that runs on top of any host (Termux/Android, Linux, macOS) and dynamically reconfigures itself based on available capabilities.

---

## Features

| Capability | Description |
|---|---|
| 🔍 **Environment detection** | Auto-detects Android/Termux, Linux, macOS, RAM, binaries, network |
| 🔌 **EAL adapters** | Unified file/process/network API per platform (`android`, `linux`, `fallback`) |
| 🤖 **Offline AI** | Rule-based assistant with optional GGUF model (llama-cpp-python) |
| 🖥️ **Dual UI** | Flask web dashboard (port 7070) with terminal fallback |
| 📁 **File system manager** | `ls`, `cat`, `find`, `mkdir`, `rm`, `edit` via EAL |
| 📦 **Repo manager** | `git init`, `commit`, `status`, `clone` via EAL |
| ⚙️ **Automation engine** | JSON task workflows with `run`, `log`, `sleep`, `write` steps |
| 🚀 **Bootstrap** | One-shot install + Termux:Boot / systemd integration |

---

## Directory Structure

The canonical implementation lives in `aura_os/`. The top-level `eal/`, `core/`, `modules/`, and `boot/` directories are **deprecated** legacy code retained for backwards compatibility.

```
AIOS/
├── aura                   ← CLI entry point  (run this)
├── install.sh             ← Master installation script
├── pyproject.toml         ← pip-installable package (pip install .)
│
├── aura_os/               ← CANONICAL Python package  ★
│   ├── main.py            ← Primary entry point & interactive shell
│   ├── eal/               ← Environment Abstraction Layer
│   │   ├── detector.py    ← Platform detection (linux/macos/android/windows)
│   │   └── adapters/      ← Linux · macOS · Android · Windows · Fallback
│   ├── engine/            ← Command dispatch
│   │   ├── cli.py         ← argparse parser (21 subcommands)
│   │   ├── router.py      ← CommandRouter
│   │   └── commands/      ← One file per CLI command
│   ├── kernel/            ← OS kernel subsystems (12)
│   │   ├── scheduler.py   ← Thread-pool task scheduler
│   │   ├── process.py     ← Process table & watchdog
│   │   ├── service.py     ← Background service manager
│   │   ├── ipc.py         ← File-based message queues
│   │   ├── memory.py      ← Memory tracking
│   │   ├── syslog.py      ← Structured system log
│   │   ├── network.py     ← Connectivity & HTTP utilities
│   │   ├── events.py      ← Pub/sub event bus & notifications
│   │   ├── cron.py        ← Cron scheduler
│   │   ├── clipboard.py   ← Cross-platform clipboard
│   │   ├── plugins.py     ← Plugin lifecycle (hot-reload)
│   │   └── secrets.py     ← Encrypted secret store (Fernet/PBKDF2)
│   ├── fs/                ← Virtual filesystem (VFS, KVStore, procfs, FHS)
│   ├── pkg/               ← Package registry & manager
│   ├── ai/                ← Local AI inference (ollama/llama.cpp)
│   ├── config/            ← Settings singleton & defaults
│   ├── users/             ← User management (PBKDF2 auth)
│   ├── net/               ← Extended network manager
│   ├── init/              ← Boot/shutdown sequencer
│   └── web/               ← REST API server (Flask or stdlib fallback)
│
├── tests/                 ← pytest suite (530+ tests)
├── docs/
│   └── architecture.md    ← Full architecture documentation
├── configs/
│   └── system.json        ← Default configuration
└── scripts/
    ├── refresh_env.sh     ← Re-run environment detection
    └── start_web.sh       ← Launch web API (deprecated: use `aura web`)

# Legacy directories (deprecated — do not use in new code):
# eal/      → superseded by aura_os/eal/
# core/     → superseded by aura_os/engine/
# modules/  → superseded by aura_os/kernel/
# boot/     → superseded by aura_os/init/
```

---

## Installation

### Quick Install (all platforms)

```bash
bash install.sh
```

The script will:
1. Detect your environment (Termux, apt, dnf, pacman, brew, …)
2. Install Python, git, and optional Flask
3. Create `~/.aura/` runtime directory
4. Add `AURA_HOME` and `PATH` to your shell profile
5. Set up Termux:Boot integration (Android only)

### Termux (Android)

```bash
pkg install git python
git clone https://github.com/Cbetts1/AIOS.git
cd AIOS
bash install.sh
```

### Linux / macOS

```bash
git clone https://github.com/Cbetts1/AIOS.git
cd AIOS
bash install.sh
```

### Manual (no install script)

```bash
export AURA_HOME=~/.aura
export PATH="$(pwd):$PATH"
python3 boot/startup.py   # bootstrap once
aura help
```

---

## Commands

```
# System
aura sys                   Show system status (CPU, memory, disk, uptime)
aura sys --watch           Continuously refresh system status
aura env                   Show full environment info
aura env --json            Output as JSON
aura health                System health dashboard
aura monitor               Real-time resource monitor

# Processes & services
aura ps                    List tracked processes
aura kill <pid>            Signal a process (default: SIGTERM)
aura service list          List background services
aura service start <name>  Start a service
aura service stop <name>   Stop a service

# Package management
aura pkg install <name>    Install a package
aura pkg remove <name>     Remove a package
aura pkg list              List installed packages
aura pkg search <query>    Search the registry

# Scripting & AI
aura run <file>            Run .py / .sh / .js file
aura ai "<prompt>"         Query local AI model (ollama/llama.cpp)
aura shell                 Launch interactive REPL shell
aura shell --script <file> Execute commands from a script file (non-interactive)

# Network
aura net status            Network connectivity status
aura net ifconfig          List network interfaces
aura net ping <host>       Ping a host
aura net dns <hostname>    DNS lookup

# Users
aura user add <name>       Add a new user
aura user del <name>       Delete a user
aura user list             List all users
aura user whoami           Show current user

# Secrets
aura secret set <key> <val>  Store an encrypted secret
aura secret get <key>        Retrieve a secret
aura secret list             List secret keys

# Plugins
aura plugin scan           Scan for available plugins
aura plugin load <name>    Load a plugin
aura plugin reload <name>  Hot-reload a plugin
aura plugin create <name>  Scaffold a new plugin

# Scheduling
aura cron add <name> --schedule "*/5 * * * *" --cmd "echo hi"
aura cron list             List cron jobs

# Other
aura log tail              Show recent system log
aura init status           Show boot unit status
aura disk df               Filesystem usage (like df -h)
aura web                   Start REST API server (http://localhost:7070)
aura web --port 8080        Start on a custom port
```

---

## Example Workflows

### Run a script

```bash
aura run myscript.py
aura run deploy.sh
```

### Ask the AI assistant

```bash
aura ai "how do I create a git repo"
aura ai "write a python function to read a csv"
aura ai "what commands are available"
```

### Manage repositories

```bash
aura repo create myapp
aura repo list
aura repo status myapp
```

### Automation

```bash
aura auto create deploy
# Edit ~/.aura/tasks/deploy.json
aura auto run deploy
```

### Web UI

```bash
aura ui web
# Open http://localhost:7070 in your browser
```

---

## Using a Local AI Model

AURA uses a rule-based fallback by default. To enable a real local LLM:

1. Install llama-cpp-python:
   ```bash
   pip install llama-cpp-python
   ```
2. Place a `.gguf` model file in `~/.aura/models/` (e.g. `tinyllama.gguf`)
3. Run any `aura ai` command — the model is auto-detected

Recommended small models:
- TinyLlama 1.1B (≈600 MB): works on most devices including Android
- Phi-2 (≈1.7 GB): better quality, requires ≥2 GB RAM

---

## Adaptation Logic

At startup, AURA builds a **capability map**:

```json
{
  "env_type": "linux",
  "is_termux": false,
  "capabilities": ["python", "git", "node", "flask", "web_ui", "heavy_modules"],
  "ram_mb": 8192,
  "has_network": false
}
```

Modules are then selected dynamically:

| Condition | Behaviour |
|---|---|
| `flask` in caps | Enable web UI |
| `flask` absent | Fall back to terminal dashboard |
| `git` in caps | Enable repo module |
| `ram_mb < 512` | Disable heavy modules |
| `is_termux` | Use pkg / Termux:Boot |
| No network | Operate fully offline |

---

## Running Tests

```bash
python3 -m unittest tests.test_aura -v
```

52 tests covering EAL detection, adapters, command engine, all modules, and bootstrap.

---

## Architecture

```
CLI (aura)
    │
    ▼
CommandEngine ──► CommandRegistry
    │
    ├──► EAL (detect_environment → get_adapter)
    │        ├── AndroidAdapter  (Termux)
    │        ├── LinuxAdapter    (Linux/macOS)
    │        └── FallbackAdapter (Windows/unknown)
    │
    ├──► modules/ai         (offline AI assistant)
    ├──► modules/browser    (web UI / terminal dashboard)
    ├──► modules/repo       (git management)
    ├──► modules/automation (task runner)
    └──► core/filesystem    (file operations)
```
