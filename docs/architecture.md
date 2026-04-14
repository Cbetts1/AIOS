# AURA OS Architecture

## 1. System Overview

AURA OS (Universal Adaptive User-Space Operating System Layer) is a real,
portable, modular shell operating system implemented in pure Python 3.8+.
It runs on top of any host — Linux, macOS, Android/Termux, or Windows —
and provides a unified CLI with file management, package management, AI
inference, a cooperative task scheduler, IPC, an interactive REPL shell,
and an optional web API.

The **OS core is real**: shell execution, process control, service management,
file operations, logging, and system diagnostics all call the real host OS.
Higher-level capabilities (Command Center, AI assistant, cloud integration,
build/repair tooling) are layered on top of the real OS foundation.

The design principle is *zero mandatory runtime dependencies*: every subsystem
degrades gracefully when optional components (psutil, readline, ollama,
llama.cpp, flask) are absent.

---

## 2. Layer Descriptions

```
┌──────────────────────────────────────────────────────────────────────┐
│  Layer 5 — Cloud / Mesh / Distributed  (aura_os/cloud/)              │
│    CloudClient · NodeRegistry · remote fleet management              │
├──────────────────────────────────────────────────────────────────────┤
│  Layer 4 — AI Layer  (aura_os/ai/)                                   │
│    AuraPersona · AuraSession · LocalInference · ModelManager         │
├──────────────────────────────────────────────────────────────────────┤
│  Layer 3 — Operator Interface                                         │
│    Command Center (aura_os/command_center/)  ·  Web API (aura_os/web/)│
│    Shell REPL (aura_os/shell/)               ·  Engine commands       │
├──────────────────────────────────────────────────────────────────────┤
│  Layer 2 — Build / Maintenance / Repair                              │
│    Validator · ManifestBuilder  (aura_os/build/)                     │
│    Diagnostics · Repair         (aura_os/maintenance/)               │
├──────────────────────────────────────────────────────────────────────┤
│  Layer 1 — OS Core Services                                          │
│    Kernel (12 subsystems) · FS · Pkg · Users · Net · Init · Config   │
├──────────────────────────────────────────────────────────────────────┤
│  Layer 0 — Environment Abstraction (EAL)                             │
│    Detector · Adapters: Linux · macOS · Android · Windows · Fallback │
└──────────────────────────────────────────────────────────────────────┘
                 (host OS: Linux / macOS / Android/Termux / Windows)
```

### 2.1 EAL — Environment Abstraction Layer (`aura_os/eal/`)

| Module | Role |
|---|---|
| `detector.py` | One-shot detection: `get_platform()` returns `termux`, `android`, `macos`, `linux`, `windows`, or `unknown` |
| `adapters/linux.py` | Linux: paths, pkg-manager detection (`apt`/`dnf`/`pacman`/`zypper`), `/proc` system info |
| `adapters/macos.py` | macOS: `sysctl` for memory, `sw_vers` for version, `brew`/`port` pkg manager, Apple Silicon detection |
| `adapters/android.py` | Termux/Android: Termux-specific paths (`/data/data/com.termux/…`), `pkg` package manager |
| `adapters/windows.py` | Windows: `winreg` CPU info, `psutil`/`wmic` memory, `winget`/`choco`/`scoop` pkg managers |
| `adapters/fallback.py` | Minimal POSIX adapter; no host assumptions beyond stdlib |
| `__init__.py` (EAL) | Selects adapter, exposes unified `read_file`, `write_file`, `run_command`, `get_env_info` API |

### 2.2 Engine (`aura_os/engine/`)

| Module | Role |
|---|---|
| `cli.py` | Builds the `argparse` parser tree; defines all subcommands and flags |
| `router.py` | `CommandRouter`: maps command names to handler classes; calls `handler.execute(args, eal)` |
| `commands/run.py` | Detects file type by extension and spawns the correct runtime |
| `commands/ai.py` | Delegates to `LocalInference`; prints the model response |
| `commands/env_cmd.py` | Renders `eal.get_env_info()` as human-readable text or JSON |
| `commands/pkg.py` | Wraps `PackageManager`; handles install/remove/list/search/info |
| `commands/sys_cmd.py` | Displays CPU, memory, disk, uptime, process count; `--watch` mode |
| `commands/ps_cmd.py` | Lists tracked AURA processes from the process table |
| `commands/kill_cmd.py` | Sends signals to tracked processes |
| `commands/service_cmd.py` | Service lifecycle: list/start/stop/restart/enable/disable/create |
| `commands/log_cmd.py` | Syslog: tail/search/clear |
| `commands/user_cmd.py` | User management: add/del/list/whoami/passwd/info |
| `commands/net_cmd.py` | Network: status/ifconfig/ping/dns/download |
| `commands/init_cmd.py` | Init system: status/boot/shutdown |
| `commands/notify_cmd.py` | Notification queue: send/list/clear |
| `commands/cron_cmd.py` | Cron scheduler: add/list/remove/enable/disable |
| `commands/clip_cmd.py` | Clipboard: copy/paste/history/clear |
| `commands/plugin_cmd.py` | Plugin lifecycle: scan/list/load/unload/reload/create |
| `commands/secret_cmd.py` | Secret store: set/get/delete/list/namespaces |
| `commands/disk_cmd.py` | Disk analysis: df/du/top/vfs |
| `commands/health_cmd.py` | System health dashboard |
| `commands/monitor_cmd.py` | Real-time resource monitor |
| `commands/web_cmd.py` | Web API server: starts HTTP REST API on port 7070 |

### 2.3 Kernel (`aura_os/kernel/`)

| Module | Role |
|---|---|
| `scheduler.py` | `Task` dataclass + `Scheduler`; thread-pool execution, timeouts, retries, deferred tasks, cancellation |
| `memory.py` | `MemoryTracker`: reads `/proc/meminfo` and `resource` module; context-manager for delta tracking |
| `ipc.py` | `IPCChannel`: JSON-lines file-based message queues under `~/.aura/ipc/`; hardened channel-name validation |
| `process.py` | `ProcessManager`: process table for spawned subprocesses; CPU/memory tracking; resource watchdog |
| `service.py` | `ServiceManager`: long-running background service lifecycle with auto-start and persistence |
| `syslog.py` | `Syslog`: structured append-only log with severity levels; JSON-lines file format |
| `network.py` | `NetworkManager`: connectivity checks, HTTP client, DNS, port scanning |
| `events.py` | `EventBus` + `NotificationManager`: pub/sub event bus and persistent notification queue |
| `cron.py` | `CronScheduler`: file-backed cron with interval strings and cron-expression support |
| `clipboard.py` | `ClipboardManager`: cross-platform clipboard (xclip/pbcopy/termux); in-memory fallback + history |
| `plugins.py` | `PluginManager`: discover/load/unload/hot-reload Python plugins with `activate()`/`deactivate()` hooks |
| `secrets.py` | `SecretStore`: PBKDF2-derived key, Fernet (AES-128-CBC) encryption; TTL, audit log, rotation |

### 2.4 Filesystem (`aura_os/fs/`)

| Module | Role |
|---|---|
| `vfs.py` | `VirtualFS`: sandboxed filesystem rooted at `~/.aura/data/`; path-traversal protection |
| `store.py` | `KVStore`: thread-safe, JSON-file-backed key-value store at `~/.aura/data/store.json` |
| `procfs.py` | `ProcFS`: virtual `/proc`-like interface for AURA runtime state |
| `fhs.py` | `VirtualFHS`: virtual directory hierarchy following Linux FHS conventions |

### 2.5 Package Management (`aura_os/pkg/`)

| Module | Role |
|---|---|
| `registry.py` | `LocalRegistry`: JSON registry at `~/.aura/pkg/registry.json`; CRUD for package manifests |
| `manager.py` | `PackageManager`: install from manifest file or registry name; uninstall; search; list |

### 2.6 AI (`aura_os/ai/`)

| Module | Role |
|---|---|
| `model_manager.py` | `ModelManager`: detects runtimes (ollama HTTP, ollama CLI, llama-cli, ctransformers); lists model files |
| `inference.py` | `LocalInference`: routes prompts to ollama → llama-cli → instructional fallback; streaming support |
| `aura.py` | `AuraPersona`: context-aware AI assistant; injects live system state into prompts; fallback responses when no runtime |
| `session.py` | `AuraSession`: multi-turn conversation history; persisted under `~/.aura/ai/sessions/` |

### 2.7 Config (`aura_os/config/`)

| Module | Role |
|---|---|
| `defaults.py` | `DEFAULT_CONFIG` dict: canonical defaults for all subsystems |
| `settings.py` | `Settings` singleton: merges `~/.aura/config/settings.json` with defaults; dot-notation `get`/`set` |

### 2.8 Users (`aura_os/users/`)

| Module | Role |
|---|---|
| `manager.py` | `UserManager`: PBKDF2-HMAC-SHA256 (260k iterations) password hashing; constant-time comparison; CRUD |

### 2.9 Network Manager (`aura_os/net/`)

| Module | Role |
|---|---|
| `manager.py` | `NetworkManager`: interface listing/stats (psutil/proc/ifconfig), traceroute, port scan, bandwidth estimation |

### 2.10 Init Manager (`aura_os/init/`)

| Module | Role |
|---|---|
| `sequence.py` | `InitManager`: systemd-inspired boot sequencer with topological sort, `after`/`requires` dependencies |

### 2.11 Web API (`aura_os/web/`)

| Module | Role |
|---|---|
| `__init__.py` | `WebServer`: REST API on port 7070; Flask backend preferred, stdlib `http.server` fallback |
| REST endpoints | `GET /api/status`, `GET /api/ps`, `GET /api/log`, `POST /api/ai` |

### 2.12 Command Center (`aura_os/command_center/`)

| Module | Role |
|---|---|
| `center.py` | `CommandCenter`: aggregated live dashboard for CPU, RAM, disk, processes, services, network, logs, and health score |
| `CenterCommand` | `aura center` — one-shot dashboard or `--watch` continuous refresh TUI |

### 2.13 Shell (`aura_os/shell/`)

| Module | Role |
|---|---|
| `repl.py` | `AuraShell`: real interactive REPL backed by the host OS; pipe/redirect/background/alias/script support |
| `ShellCommand` | `aura shell` — start the interactive shell; `--script FILE` for non-interactive execution |

### 2.14 Build & Validation (`aura_os/build/`)

| Module | Role |
|---|---|
| `validator.py` | `Validator`: checks Python version, directory structure, kernel imports, psutil, disk space, log writerability |
| `manifest.py` | `ManifestBuilder`: generates JSON manifest of installed packages, kernel modules, filesystem, services; diff support |
| CLI | `aura validate`, `aura build manifest`, `aura build diff <old> <new>` |

### 2.15 Maintenance & Repair (`aura_os/maintenance/`)

| Module | Role |
|---|---|
| `diagnostics.py` | `Diagnostics`: real system diagnostic checks (platform, Python, hardware, network, filesystem, kernel, dependencies) |
| `repair.py` | `Repair`: recreates missing dirs, restores corrupt configs, rotates large logs, purges stale state files |
| CLI | `aura diag`, `aura repair [all\|dirs\|config\|logs\|state]` |

### 2.16 Cloud & Network (`aura_os/cloud/`)

| Module | Role |
|---|---|
| `client.py` | `CloudClient`: real HTTP/HTTPS client (stdlib `urllib`); ping, GET, POST JSON, file download |
| `nodes.py` | `NodeRegistry`: persist and query remote AURA OS nodes; liveness pinging via `CloudClient` |
| CLI | `aura cloud ping <url>`, `aura cloud get <url>`, `aura cloud nodes`, `aura cloud status` |

---

## 3. Module Interaction

```
aura (shell script)
  └─ python3 -m aura_os.main
       ├─ EAL.__init__()          → detector → adapter (linux/macos/android/windows/fallback)
       ├─ build_parser()          → argparse tree (28 commands)
       ├─ CommandRouter.dispatch()
       │    └─ XxxCommand.execute(args, eal)
       │         ├─ eal.run_command(...)
       │         ├─ VirtualFS / KVStore
       │         ├─ PackageManager / LocalRegistry
       │         ├─ LocalInference / ModelManager / AuraPersona / AuraSession
       │         ├─ CommandCenter (live dashboard)
       │         ├─ AuraShell (interactive REPL)
       │         ├─ Validator / ManifestBuilder (build layer)
       │         ├─ Diagnostics / Repair (maintenance layer)
       │         ├─ CloudClient / NodeRegistry (cloud layer)
       │         ├─ UserManager
       │         ├─ NetworkManager (net/)
       │         ├─ InitManager
       │         └─ WebServer
       └─ Settings (singleton, loaded on first access)
```
       │         ├─ VirtualFS / KVStore
       │         ├─ PackageManager / LocalRegistry
       │         ├─ LocalInference / ModelManager
       │         ├─ UserManager
       │         ├─ NetworkManager (net/)
       │         ├─ InitManager
       │         └─ WebServer
       └─ Settings (singleton, loaded on first access)
```

Data flows:
1. The shell script sets `AURA_HOME` and invokes `python3 -m aura_os.main`.
2. `main.py` bootstraps `EAL`, which detects the platform and selects an adapter.
3. The argparse parser tokenises argv; `CommandRouter` looks up the handler.
4. Handlers call EAL methods for I/O and subprocess execution, and access core service classes directly.
5. `Settings` is a singleton — any module can call `Settings().get("key")` and get the merged config.

---

## 4. How to Add a New Command

1. **Create `aura_os/engine/commands/mycommand.py`** with a class that has:
   ```python
   class MyCommand:
       """Docstring."""
       def execute(self, args, eal) -> int:
           # ... your implementation ...
           return 0  # exit code
   ```
2. **Add the subparser** in `aura_os/engine/cli.py` inside `build_parser()`:
   ```python
   my_p = subparsers.add_parser("mycommand", help="Does something")
   my_p.add_argument("--flag", ...)
   ```
3. **Register the handler** in `aura_os/main.py`:
   ```python
   from aura_os.engine.commands.mycommand import MyCommand
   router.register("mycommand", MyCommand)
   ```
4. **Export** in `aura_os/engine/commands/__init__.py`:
   ```python
   from .mycommand import MyCommand
   ```
5. Write tests in `tests/test_engine.py`.

---

## 5. How to Add a New Adapter

1. **Create `aura_os/eal/adapters/myadapter.py`** implementing:
   ```python
   class MyAdapter:
       def get_home(self) -> str: ...
       def get_prefix(self) -> str: ...
       def get_tmp(self) -> str: ...
       def run_command(self, cmd: list, capture: bool = True) -> tuple: ...
       def available_pkg_manager(self) -> str | None: ...
       def get_system_info(self) -> dict: ...
   ```
2. **Export** in `aura_os/eal/adapters/__init__.py`.
3. **Update `EAL._select_adapter()`** in `aura_os/eal/__init__.py` to return `MyAdapter()` when appropriate.
4. **Update `detector.get_platform()`** if a new platform identifier is needed.

---

## 6. Directory Layout at Runtime

```
~/.aura/
├── ai/
│   └── sessions/     ← AuraSession conversation history (JSON)
├── bin/              ← aura entry-point symlink / wrapper
├── cloud/
│   └── nodes.json    ← NodeRegistry remote nodes
├── configs/
│   └── system.json   ← system configuration (managed by Repair)
├── config/
│   └── settings.json ← Settings singleton store
├── cron/
│   └── jobs.json     ← persisted cron job definitions
├── data/
│   ├── store.json
│   └── .history
├── home/
│   └── <username>/   ← per-user home directories
├── ipc/              ← IPCChannel message queues
├── lib/
│   └── aura_os/      ← installed library copy
├── logs/             ← Syslog and service logs
├── models/           ← local AI model files (.gguf, .bin)
├── pkg/
│   ├── installed/
│   └── registry.json
├── plugins/          ← plugin directories (each with plugin.json + main.py)
├── repos/            ← cloned/tracked repos
├── secrets/          ← encrypted secrets (per-namespace JSON files + audit.log)
├── services/         ← service manifests (JSON)
├── shell_history     ← AuraShell readline history
├── tasks/            ← deferred task definitions
└── users/            ← user records (per-user JSON files)
```

---

## 7. Legacy Layer

The repository also contains a legacy implementation in the top-level directories:

| Legacy path | Superseded by |
|---|---|
| `eal/` | `aura_os/eal/` |
| `core/` | `aura_os/engine/` |
| `modules/` | `aura_os/kernel/` |
| `boot/` | `aura_os/init/` |

These directories are **deprecated** — all new development should target the `aura_os/` package.  They are retained for backwards compatibility and will be removed in a future release.
