"""``aura repo`` command handler — git repository management."""

import os
import shutil
import subprocess
from pathlib import Path


class RepoCommand:
    """Git repository management: create, list, status, clone.

    Repositories are stored under ``~/.aura/repos/`` by default.
    """

    def execute(self, args, eal) -> int:
        sub = getattr(args, "repo_command", None)

        if sub == "create":
            return self._create(args.name)
        if sub == "list":
            return self._list()
        if sub == "status":
            path = getattr(args, "path", ".")
            return self._status(path)
        if sub == "clone":
            dest = getattr(args, "dest", None)
            return self._clone(args.url, dest)

        print("[repo] Unknown sub-command. Run 'aura repo --help'.")
        return 1

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _repos_dir() -> Path:
        aura_home = os.environ.get("AURA_HOME", os.path.expanduser("~/.aura"))
        d = Path(aura_home) / "repos"
        d.mkdir(parents=True, exist_ok=True)
        return d

    @staticmethod
    def _has_git() -> bool:
        return shutil.which("git") is not None

    # ------------------------------------------------------------------
    # sub-commands
    # ------------------------------------------------------------------

    def _create(self, name: str) -> int:
        if not self._has_git():
            print("[repo] git is not installed.")
            return 1

        repo_path = self._repos_dir() / name
        if repo_path.exists():
            print(f"[repo] Repository already exists: {repo_path}")
            return 1

        repo_path.mkdir(parents=True)
        rc = subprocess.run(
            ["git", "init", str(repo_path)],
            capture_output=True,
        ).returncode

        if rc == 0:
            readme = repo_path / "README.md"
            readme.write_text(f"# {name}\n\nCreated by AURA OS.\n")
            subprocess.run(
                ["git", "-C", str(repo_path), "add", "README.md"],
                capture_output=True,
            )
            subprocess.run(
                ["git", "-C", str(repo_path), "commit", "-m", "Initial commit"],
                capture_output=True,
            )
            print(f"[repo] Created: {repo_path}")
            return 0

        print("[repo] git init failed.")
        return 1

    def _list(self) -> int:
        repos_dir = self._repos_dir()
        repos = sorted(d for d in repos_dir.iterdir() if d.is_dir())

        if not repos:
            print("[repo] No repositories found. Create one with: aura repo create <name>")
            return 0

        print(f"\n  Repositories in {repos_dir}:")
        print("  " + "─" * 40)
        for r in repos:
            tag = "[git]" if (r / ".git").is_dir() else "     "
            print(f"  {tag}  {r.name}")
        print()
        return 0

    @staticmethod
    def _status(path: str) -> int:
        if not shutil.which("git"):
            print("[repo] git is not installed.")
            return 1

        p = Path(path).expanduser().resolve()
        result = subprocess.run(
            ["git", "-C", str(p), "status", "--short", "--branch"],
            capture_output=True, text=True,
        )
        if result.returncode == 0:
            print(f"\n  {p}\n")
            print(result.stdout or "  (nothing to commit)")
            return 0

        print(f"[repo] Not a git repository: {p}")
        return 1

    def _clone(self, url: str, dest=None) -> int:
        if not self._has_git():
            print("[repo] git is not installed.")
            return 1

        repos_dir = self._repos_dir()
        cmd = ["git", "-C", str(repos_dir), "clone", url]
        if dest:
            cmd.append(dest)

        print(f"[repo] Cloning {url} …")
        result = subprocess.run(cmd)
        if result.returncode != 0:
            print("[repo] Clone failed.")
            return 1
        return 0
