"""
Package Management Module — Termux/Kali-style package manager for AURA OS.

Wraps the host package manager (apt, dnf, pacman, brew, pkg, winget, etc.)
behind a unified interface so ``aura pkg install curl`` works everywhere.

Includes a curated catalog of recommended packages organised by category
(like Termux's ``pkg`` or Kali's meta-packages).
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Optional


# ──────────────────────────────────────────────────────────────────────────────
# Curated package catalog — maps friendly names to platform-specific names
# ──────────────────────────────────────────────────────────────────────────────

# Each entry: "friendly_name": {
#     "description": "...",
#     "category": "...",
#     "apt": "pkg_name", "dnf": "pkg_name", "pacman": "pkg_name",
#     "brew": "pkg_name", "pkg": "pkg_name",   # Termux
#     "winget": "pkg_name", "choco": "pkg_name", "scoop": "pkg_name",
# }
# A value of None means "not available on that platform".

CATALOG: dict[str, dict] = {
    # ── Core tools ──
    "curl": {
        "description": "Command-line HTTP client",
        "category": "core",
        "apt": "curl", "dnf": "curl", "pacman": "curl",
        "brew": "curl", "pkg": "curl",
        "winget": "cURL.cURL", "choco": "curl", "scoop": "curl",
    },
    "wget": {
        "description": "Non-interactive network downloader",
        "category": "core",
        "apt": "wget", "dnf": "wget", "pacman": "wget",
        "brew": "wget", "pkg": "wget",
        "winget": "JernejSimoncic.Wget", "choco": "wget", "scoop": "wget",
    },
    "git": {
        "description": "Distributed version control system",
        "category": "core",
        "apt": "git", "dnf": "git", "pacman": "git",
        "brew": "git", "pkg": "git",
        "winget": "Git.Git", "choco": "git", "scoop": "git",
    },
    "python": {
        "description": "Python 3 interpreter",
        "category": "core",
        "apt": "python3", "dnf": "python3", "pacman": "python",
        "brew": "python@3", "pkg": "python",
        "winget": "Python.Python.3.12", "choco": "python3", "scoop": "python",
    },
    "vim": {
        "description": "Vi Improved — terminal text editor",
        "category": "editors",
        "apt": "vim", "dnf": "vim-enhanced", "pacman": "vim",
        "brew": "vim", "pkg": "vim",
        "winget": None, "choco": "vim", "scoop": "vim",
    },
    "nano": {
        "description": "Simple terminal text editor",
        "category": "editors",
        "apt": "nano", "dnf": "nano", "pacman": "nano",
        "brew": "nano", "pkg": "nano",
        "winget": None, "choco": "nano", "scoop": None,
    },
    # ── Networking ──
    "nmap": {
        "description": "Network discovery and security auditing",
        "category": "networking",
        "apt": "nmap", "dnf": "nmap", "pacman": "nmap",
        "brew": "nmap", "pkg": "nmap",
        "winget": "Insecure.Nmap", "choco": "nmap", "scoop": None,
    },
    "openssh": {
        "description": "Secure Shell client and server",
        "category": "networking",
        "apt": "openssh-client", "dnf": "openssh-clients", "pacman": "openssh",
        "brew": "openssh", "pkg": "openssh",
        "winget": None, "choco": "openssh", "scoop": None,
    },
    "net-tools": {
        "description": "Classic networking utilities (ifconfig, netstat)",
        "category": "networking",
        "apt": "net-tools", "dnf": "net-tools", "pacman": "net-tools",
        "brew": None, "pkg": "net-tools",
        "winget": None, "choco": None, "scoop": None,
    },
    # ── Development ──
    "nodejs": {
        "description": "JavaScript runtime",
        "category": "development",
        "apt": "nodejs", "dnf": "nodejs", "pacman": "nodejs",
        "brew": "node", "pkg": "nodejs",
        "winget": "OpenJS.NodeJS.LTS", "choco": "nodejs-lts", "scoop": "nodejs-lts",
    },
    "gcc": {
        "description": "GNU C/C++ compiler",
        "category": "development",
        "apt": "gcc", "dnf": "gcc", "pacman": "gcc",
        "brew": "gcc", "pkg": "clang",
        "winget": None, "choco": "mingw", "scoop": "gcc",
    },
    "make": {
        "description": "Build automation tool",
        "category": "development",
        "apt": "make", "dnf": "make", "pacman": "make",
        "brew": "make", "pkg": "make",
        "winget": None, "choco": "make", "scoop": "make",
    },
    "jq": {
        "description": "Command-line JSON processor",
        "category": "development",
        "apt": "jq", "dnf": "jq", "pacman": "jq",
        "brew": "jq", "pkg": "jq",
        "winget": "jqlang.jq", "choco": "jq", "scoop": "jq",
    },
    # ── Security ──
    "openssl": {
        "description": "TLS/SSL toolkit",
        "category": "security",
        "apt": "openssl", "dnf": "openssl", "pacman": "openssl",
        "brew": "openssl", "pkg": "openssl-tool",
        "winget": None, "choco": "openssl", "scoop": None,
    },
    "gnupg": {
        "description": "GNU Privacy Guard — encryption and signing",
        "category": "security",
        "apt": "gnupg", "dnf": "gnupg2", "pacman": "gnupg",
        "brew": "gnupg", "pkg": "gnupg",
        "winget": "GnuPG.GnuPG", "choco": "gnupg", "scoop": None,
    },
    # ── System utilities ──
    "htop": {
        "description": "Interactive process viewer",
        "category": "system",
        "apt": "htop", "dnf": "htop", "pacman": "htop",
        "brew": "htop", "pkg": "htop",
        "winget": None, "choco": None, "scoop": None,
    },
    "tmux": {
        "description": "Terminal multiplexer",
        "category": "system",
        "apt": "tmux", "dnf": "tmux", "pacman": "tmux",
        "brew": "tmux", "pkg": "tmux",
        "winget": None, "choco": None, "scoop": None,
    },
    "tree": {
        "description": "Directory listing in tree format",
        "category": "system",
        "apt": "tree", "dnf": "tree", "pacman": "tree",
        "brew": "tree", "pkg": "tree",
        "winget": None, "choco": "tree", "scoop": None,
    },
    "zip": {
        "description": "Archive compression utility",
        "category": "system",
        "apt": "zip", "dnf": "zip", "pacman": "zip",
        "brew": None, "pkg": "zip",
        "winget": None, "choco": None, "scoop": None,
    },
    "unzip": {
        "description": "Archive extraction utility",
        "category": "system",
        "apt": "unzip", "dnf": "unzip", "pacman": "unzip",
        "brew": None, "pkg": "unzip",
        "winget": None, "choco": None, "scoop": None,
    },
    # ── Shells ──
    "zsh": {
        "description": "Z shell",
        "category": "shells",
        "apt": "zsh", "dnf": "zsh", "pacman": "zsh",
        "brew": "zsh", "pkg": "zsh",
        "winget": None, "choco": None, "scoop": None,
    },
    "fish": {
        "description": "Friendly interactive shell",
        "category": "shells",
        "apt": "fish", "dnf": "fish", "pacman": "fish",
        "brew": "fish", "pkg": "fish",
        "winget": None, "choco": None, "scoop": None,
    },
}


class PkgModule:
    """
    Unified package manager for AURA OS.

    Detects the host package manager via the EAL adapter, maps friendly
    package names through the catalog, and provides install / remove /
    list / search operations.
    """

    def __init__(self, env_map: dict, adapter):
        self.env = env_map
        self.adapter = adapter
        self._pm: Optional[str] = adapter.get_package_manager()
        self._pm_canonical = self._canonicalize_pm(self._pm)

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def install(self, name: str) -> bool:
        """Install a package by friendly or native name. Returns True on success."""
        native = self._resolve(name)
        if native is None:
            print(f"[aura pkg] Package '{name}' is not available for {self._pm or 'this platform'}.")
            return False
        print(f"[aura pkg] Installing '{name}' (native: {native}) via {self._pm} …")
        ok = self.adapter.install_package(native)
        if ok:
            print(f"[aura pkg] ✓ '{name}' installed successfully.")
        else:
            print(f"[aura pkg] ✗ Failed to install '{name}'.")
        return ok

    def remove(self, name: str) -> bool:
        """Remove a package by friendly or native name. Returns True on success."""
        native = self._resolve(name)
        if native is None:
            native = name  # try raw name
        cmd = self._build_remove_cmd(native)
        if cmd is None:
            print(f"[aura pkg] Cannot remove packages on this platform (no package manager).")
            return False
        print(f"[aura pkg] Removing '{name}' …")
        rc, _, err = self.adapter.run(cmd, capture=True)
        if rc == 0:
            print(f"[aura pkg] ✓ '{name}' removed.")
            return True
        print(f"[aura pkg] ✗ Failed to remove '{name}': {err.strip()}")
        return False

    def list_installed(self):
        """Print installed packages (host-level)."""
        cmd = self._build_list_cmd()
        if cmd is None:
            print("[aura pkg] Cannot list packages on this platform.")
            return
        rc, out, _ = self.adapter.run(cmd, capture=True, timeout=30)
        if rc == 0 and out:
            print(out)
        else:
            print("[aura pkg] No output from package manager.")

    def search(self, query: str):
        """Search the curated catalog (offline) and optionally the host PM (online)."""
        query_lower = query.lower()
        hits = []
        for name, info in CATALOG.items():
            if (query_lower in name
                    or query_lower in info.get("description", "").lower()
                    or query_lower in info.get("category", "").lower()):
                available = self._resolve(name) is not None
                hits.append((name, info, available))

        if hits:
            print(f"\n  AURA Package Catalog — matches for '{query}'")
            print("  " + "─" * 50)
            for name, info, available in sorted(hits, key=lambda h: h[0]):
                status = "✓" if available else "✗"
                print(f"  [{status}] {name:<14} {info['description']}  ({info['category']})")
            print()
        else:
            print(f"[aura pkg] No catalog matches for '{query}'.")

    def catalog(self):
        """Print the full curated catalog grouped by category."""
        by_cat: dict[str, list] = {}
        for name, info in CATALOG.items():
            cat = info.get("category", "other")
            by_cat.setdefault(cat, []).append((name, info))

        print("\n  AURA Package Catalog")
        print("  " + "─" * 50)
        for cat in sorted(by_cat):
            print(f"\n  [{cat.upper()}]")
            for name, info in sorted(by_cat[cat]):
                available = self._resolve(name) is not None
                status = "✓" if available else "✗"
                print(f"    [{status}] {name:<14} {info['description']}")
        print()

    def info(self, name: str):
        """Show detailed info about a catalog package."""
        entry = CATALOG.get(name)
        if entry is None:
            print(f"[aura pkg] '{name}' is not in the catalog. Try 'aura pkg search {name}'.")
            return
        native = self._resolve(name)
        installed = shutil.which(name) is not None
        print(f"\n  Package: {name}")
        print(f"  Description: {entry['description']}")
        print(f"  Category: {entry['category']}")
        print(f"  Native name: {native or 'N/A (not available on this platform)'}")
        print(f"  Installed: {'yes' if installed else 'no'}")
        print(f"  Package manager: {self._pm or 'none detected'}")
        print()

    # ------------------------------------------------------------------ #
    # Internals
    # ------------------------------------------------------------------ #

    @staticmethod
    def _canonicalize_pm(pm: Optional[str]) -> Optional[str]:
        """Map 'apt-get' → 'apt', etc. to look up catalog entries."""
        if pm is None:
            return None
        mapping = {
            "apt-get": "apt",
            "yum": "dnf",
        }
        return mapping.get(pm, pm)

    def _resolve(self, name: str) -> Optional[str]:
        """Return the native package name for the current PM, or *name* if not in catalog."""
        entry = CATALOG.get(name)
        if entry is None:
            return name  # not in catalog — pass through as-is
        if self._pm_canonical is None:
            return None
        native = entry.get(self._pm_canonical)
        return native  # may be None if not available on this platform

    def _build_remove_cmd(self, native: str):
        pm = self._pm
        if not pm:
            return None
        if pm in ("apt-get", "apt"):
            return ["sudo", pm, "remove", "-y", native]
        if pm in ("dnf", "yum"):
            return ["sudo", pm, "remove", "-y", native]
        if pm == "pacman":
            return ["sudo", "pacman", "-R", "--noconfirm", native]
        if pm == "brew":
            return ["brew", "uninstall", native]
        if pm == "pkg":
            return ["pkg", "uninstall", "-y", native]
        if pm == "zypper":
            return ["sudo", "zypper", "remove", "-y", native]
        if pm == "winget":
            return ["winget", "uninstall", native]
        if pm == "choco":
            return ["choco", "uninstall", "-y", native]
        if pm == "scoop":
            return ["scoop", "uninstall", native]
        return None

    def _build_list_cmd(self):
        pm = self._pm
        if not pm:
            return None
        if pm in ("apt-get", "apt"):
            return ["dpkg", "--list"]
        if pm in ("dnf", "yum"):
            return [pm, "list", "installed"]
        if pm == "pacman":
            return ["pacman", "-Q"]
        if pm == "brew":
            return ["brew", "list"]
        if pm == "pkg":
            return ["pkg", "list-installed"]
        if pm == "zypper":
            return ["zypper", "se", "--installed-only"]
        if pm == "winget":
            return ["winget", "list"]
        if pm == "choco":
            return ["choco", "list"]
        if pm == "scoop":
            return ["scoop", "list"]
        return None
