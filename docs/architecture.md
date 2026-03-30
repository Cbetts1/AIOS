# AURA OS Architecture

## 1. System Overview

AURA OS (Universal Adaptive User-Space Operating System Layer) is a portable, modular shell operating system implemented in pure Python 3.8+. It runs on top of any POSIX host — Linux, macOS, Android/Termux — and provides a unified CLI with file management, package management, AI inference, a cooperative task scheduler, IPC, and an interactive REPL shell.

The design principle is *zero mandatory runtime dependencies*: every subsystem degrades gracefully when optional components (psutil, readline, ollama, llama.cpp) are absent.

---

## 2. Layer Descriptions

```
┌──────────────────────────────────────────────────────┐
│                   CLI / Shell (aura)                  │  ← user-facing
├──────────────┬───────────────────────────────────────┤
│  Engine       │  Commands: run · ai · env · pkg · sys │  ← command dispatch
├──────────────┴───────────────────────────────────────┤
│  EAL  — Environment Abstraction Layer                 │  ← host adaptation
│    Detector  │  Adapters: Linux · Android · Fallback  │
├──────────────┬────────────┬──────────────────────────┤
│  Kernel       │  FS        │  Pkg  │  AI  │  Config   │  ← core services
│  scheduler    │  VFS/KV    │  mgr  │  inf │  settings │
└──────────────┴────────────┴───────────────────────────┘
         (host OS: Linux / macOS / Android/Termux)
```

### 2.1 EAL — Environment Abstraction Layer (`aura_os/eal/`)

| Module | Role |
|---|---|
| `detector.py` | One-shot detection functions: `get_platform()`, `get_available_binaries()`, `get_storage_paths()`, `get_permissions()` |
| `adapters/linux.py` | Adapter for standard Linux: paths, pkg-manager detection (`apt`/`dnf`/`pacman`/`zypper`), `/proc` system info |
| `adapters/android.py` | Adapter for Termux/Android: Termux-specific paths (`/data/data/com.termux/…`), `pkg` package manager |
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

### 2.3 Kernel (`aura_os/kernel/`)

| Module | Role |
|---|---|
| `scheduler.py` | `Task` dataclass + `Scheduler`; cooperative execution of callables; background-thread support |
| `memory.py` | `MemoryTracker`: reads `/proc/meminfo` and `resource` module; context-manager for delta tracking |
| `ipc.py` | `IPCChannel`: JSON-lines file-based message queues under `~/.aura/ipc/` |

### 2.4 Filesystem (`aura_os/fs/`)

| Module | Role |
|---|---|
| `vfs.py` | `VirtualFS`: sandboxed filesystem rooted at `~/.aura/data/`; path-traversal protection via `realpath` comparison |
| `store.py` | `KVStore`: thread-safe, JSON-file-backed key-value store at `~/.aura/data/store.json` |

### 2.5 Package Management (`aura_os/pkg/`)

| Module | Role |
|---|---|
| `registry.py` | `LocalRegistry`: JSON registry at `~/.aura/pkg/registry.json`; CRUD for package manifests |
| `manager.py` | `PackageManager`: install from manifest file or registry name; uninstall; search; list |

### 2.6 AI (`aura_os/ai/`)

| Module | Role |
|---|---|
| `model_manager.py` | `ModelManager`: detects runtimes (ollama, llama-cli, ctransformers); lists `.gguf`/`.bin` model files |
| `inference.py` | `LocalInference`: routes prompts to ollama → llama-cli → instructional fallback |

### 2.7 Config (`aura_os/config/`)

| Module | Role |
|---|---|
| `defaults.py` | `DEFAULT_CONFIG` dict: canonical defaults for all subsystems |
| `settings.py` | `Settings` singleton: merges `~/.aura/config/settings.json` with defaults; dot-notation `get`/`set` |

---

## 3. Module Interaction

```
aura (shell script)
  └─ python3 -m aura_os.main
       ├─ EAL.__init__()          → detector → adapter
       ├─ build_parser()          → argparse tree
       ├─ CommandRouter.dispatch()
       │    └─ XxxCommand.execute(args, eal)
       │         ├─ eal.run_command(...)
       │         ├─ VirtualFS / KVStore
       │         ├─ PackageManager / LocalRegistry
       │         └─ LocalInference / ModelManager
       └─ Settings (singleton, loaded on first access)
```

Data flows:
1. The shell script sets `AURA_HOME` and invokes `python3 -m aura_os.main`.
2. `main.py` bootstraps `EAL`, which selects an adapter.
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
├── bin/          ← aura entry-point symlink / wrapper
├── config/
│   └── settings.json
├── data/
│   ├── store.json
│   └── .history
├── ipc/          ← IPCChannel message queues
├── lib/
│   └── aura_os/  ← installed library copy
├── logs/
├── models/       ← local AI model files (.gguf, .bin)
└── pkg/
    ├── installed/
    └── registry.json
```
