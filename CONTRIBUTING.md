# Contributing to AURA OS

Thank you for taking the time to contribute! This document explains how to set up a development environment, run tests, and submit changes.

---

## Table of Contents

1. [Getting started](#getting-started)
2. [Development environment](#development-environment)
3. [Running tests](#running-tests)
4. [Code style](#code-style)
5. [Submitting changes](#submitting-changes)
6. [Adding a new CLI command](#adding-a-new-cli-command)
7. [Adding a new EAL adapter](#adding-a-new-eal-adapter)

---

## Getting started

```bash
git clone https://github.com/Cbetts1/AIOS.git
cd AIOS
pip install -e ".[dev]"
```

This installs AURA OS in editable mode with all dev dependencies (pytest, coverage, flask, psutil, cryptography).

---

## Development environment

| Variable | Default | Purpose |
|---|---|---|
| `AURA_HOME` | `~/.aura` | Runtime directory for all AURA data |
| `AURA_PORTABLE` | unset | Set to `1` to activate portable mode |

---

## Running tests

```bash
# All tests
python3 -m pytest tests/ -v

# Single test file
python3 -m pytest tests/test_engine.py -v

# With coverage
python3 -m pytest tests/ --cov=aura_os --cov-report=term-missing
```

The test suite requires **Python ≥ 3.8**.  
Tests that require optional packages (`psutil`, `cryptography`, `flask`) are auto-skipped when those packages are absent.

---

## Code style

- **No mandatory formatter** — match the style of the file you are editing.
- Keep lines under **100 characters** where practical.
- Use standard library imports only in core kernel/EAL code; optional imports must be wrapped in try/except or checked with `importlib.util.find_spec`.
- All new public functions/classes must have a one-line docstring minimum.

---

## Submitting changes

1. Fork the repository.
2. Create a feature branch: `git checkout -b feat/my-feature`
3. Commit your changes with a clear message.
4. Open a pull request against `main`.

**PR checklist:**
- [ ] Tests pass (`python3 -m pytest tests/`)
- [ ] New code has corresponding tests
- [ ] `CHANGELOG.md` updated under `[Unreleased]`
- [ ] No new mandatory runtime dependencies added

---

## Adding a new CLI command

Commands are registered in three places:

1. **Create** `aura_os/engine/commands/<name>_cmd.py` with a class implementing `execute(self, args, eal) -> int`.
2. **Export** the class from `aura_os/engine/commands/__init__.py`.
3. **Add a subparser** in `aura_os/engine/cli.py` inside `build_parser()`.
4. **Register** the handler in `_build_router()` in `aura_os/main.py`.

See `aura_os/engine/commands/disk_cmd.py` for a minimal example.

---

## Adding a new EAL adapter

1. Create `aura_os/eal/adapters/<platform>.py` inheriting from `BaseAdapter`.
2. Update `aura_os/eal/detector.py` to detect the new platform.
3. Update `aura_os/eal/__init__.py` to select the new adapter.
4. Add tests to `tests/test_eal.py`.
