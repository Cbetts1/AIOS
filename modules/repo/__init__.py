"""
Repo Module — Git Repository Management
Wraps git operations through the EAL adapter.
"""

import os
from pathlib import Path


class RepoModule:
    """
    Provides create, list, status, and clone operations for git repositories.
    Falls back to informative messages when git is unavailable.
    """

    def __init__(self, env_map: dict, adapter):
        self.env = env_map
        self.adapter = adapter
        self._repos_dir = Path(env_map.get("storage_root", Path.home() / ".aura")) / "repos"
        self._repos_dir.mkdir(parents=True, exist_ok=True)
        self._git = adapter.which("git")

    # ------------------------------------------------------------------ #
    # Public operations
    # ------------------------------------------------------------------ #

    def create(self, name: str):
        """Create a new local git repository."""
        if not self._git:
            print("[repo] git is not installed. Cannot create repository.")
            return

        repo_path = self._repos_dir / name
        if repo_path.exists():
            print(f"[repo] Repository already exists: {repo_path}")
            return

        repo_path.mkdir(parents=True)
        rc, out, err = self.adapter.run([self._git, "init", str(repo_path)], capture=True)

        if rc == 0:
            # Create default README
            readme = repo_path / "README.md"
            readme.write_text(f"# {name}\n\nCreated by AURA OS.\n")
            self.adapter.run(
                [self._git, "-C", str(repo_path), "add", "README.md"],
                capture=True,
            )
            self.adapter.run(
                [self._git, "-C", str(repo_path), "commit", "-m", "Initial commit"],
                capture=True,
            )
            print(f"[repo] Created: {repo_path}")
        else:
            print(f"[repo] git init failed: {err.strip()}")

    def list_repos(self):
        """List all repositories managed by AURA."""
        repos = [d for d in sorted(self._repos_dir.iterdir()) if d.is_dir()]
        if not repos:
            print("[repo] No repositories found. Create one with: aura repo create <name>")
            return

        print(f"\n  Repositories in {self._repos_dir}:")
        print("  " + "─" * 40)
        for r in repos:
            is_git = (r / ".git").is_dir()
            tag = "[git]" if is_git else "     "
            print(f"  {tag}  {r.name}")
        print()

    def status(self, path: str = "."):
        """Show git status for the repository at *path*."""
        if not self._git:
            print("[repo] git is not installed.")
            return

        p = Path(path).expanduser().resolve()
        rc, out, err = self.adapter.run(
            [self._git, "-C", str(p), "status", "--short", "--branch"],
            capture=True,
        )
        if rc == 0:
            print(f"\n  {p}\n")
            print(out or "  (nothing to commit)")
        else:
            print(f"[repo] Not a git repository: {p}")

    def clone(self, url: str, dest=None):
        """Clone a remote repository (requires network)."""
        if not self._git:
            print("[repo] git is not installed.")
            return
        if not self.env.get("has_network"):
            print("[repo] No network connection available.")
            return

        cmd = [self._git, "clone", url]
        if dest:
            cmd.append(str(self._repos_dir / dest))
        else:
            cmd_str = str(self._repos_dir)
            cmd = [self._git, "-C", cmd_str, "clone", url]

        print(f"[repo] Cloning {url} …")
        rc, out, err = self.adapter.run(cmd, capture=False)
        if rc != 0:
            print(f"[repo] Clone failed.")
