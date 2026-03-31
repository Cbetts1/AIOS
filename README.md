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

```
AIOS/
├── aura                   ← CLI entry point  (run this)
├── install.sh             ← Master installation script
├── boot/
│   └── startup.py         ← Bootstrap & initialisation
├── core/
│   ├── engine.py          ← Command parser & dispatcher
│   ├── registry.py        ← Command registry
│   └── filesystem.py      ← File system manager
├── eal/
│   ├── __init__.py        ← Environment detection & adapter factory
│   └── adapters/
│       ├── __init__.py    ← BaseAdapter (shared interface)
│       ├── android.py     ← Termux/Android adapter
│       ├── linux.py       ← Linux/macOS adapter
│       └── fallback.py    ← Windows / unknown adapter
├── modules/
│   ├── ai/                ← Offline AI assistant
│   ├── browser/           ← Web UI + terminal dashboard
│   ├── repo/              ← Git repository management
│   └── automation/        ← Task runner & workflow engine
├── configs/
│   └── system.json        ← Default configuration
├── scripts/
│   ├── refresh_env.sh     ← Re-run environment detection
│   └── start_web.sh       ← Launch web UI
├── tests/
│   └── test_aura.py       ← 52 unit tests
└── logs/                  ← Runtime logs
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
aura help                  Show all commands
aura sys [--watch]         System information (CPU, RAM, disk)
aura env [--json]          Full environment information
aura shell                 Launch interactive AURA shell

aura run <file>            Run .py / .sh / .js file
aura ai "<prompt>"         Offline AI assistant

aura fs ls [path]          List files/directories
aura fs cat <file>         Print file contents
aura fs find [root] [pat]  Search for files
aura fs mkdir <path>       Create directory
aura fs rm <path>          Delete file or directory
aura fs edit <file>        Open in text editor

aura pkg install <name>    Install a package
aura pkg remove <name>     Remove a package
aura pkg list              List installed packages
aura pkg search <query>    Search for packages
aura pkg info <name>       Package details

aura repo create <name>    Init a new git repo
aura repo list             List managed repos
aura repo status [path]    Show git status
aura repo clone <url>      Clone remote repo (needs network)

aura auto list             List automation tasks
aura auto create <name>    Create a task template
aura auto run <name>       Execute a task

aura ps                    List tracked processes
aura kill <pid> [-s SIG]   Send signal to a process

aura service list          List all services
aura service start <name>  Start a service
aura service stop <name>   Stop a service
aura service create <name> Create a service definition

aura log [tail|search|clear]  View / search system logs
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
