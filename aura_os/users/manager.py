"""User manager for AURA OS."""

import getpass
import hashlib
import json
import os
import re
import threading
from datetime import datetime, timezone
from typing import Optional

_USERNAME_RE = re.compile(r"^[a-zA-Z0-9_-]{1,32}$")
_VALID_ROLES = {"root", "user", "guest"}


class UserManager:
    """Manages AURA OS users stored as JSON files under ``~/.aura/users/``."""

    def __init__(self, base_dir: str = None):
        if base_dir is None:
            aura_home = os.environ.get("AURA_HOME", os.path.expanduser("~/.aura"))
            base_dir = os.path.join(aura_home, "users")
        self._base = base_dir
        os.makedirs(self._base, exist_ok=True)
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _user_path(self, username: str) -> str:
        return os.path.join(self._base, f"{username}.json")

    def _hash(self, password: str) -> str:
        return hashlib.sha256(password.encode("utf-8")).hexdigest()

    def _validate_username(self, username: str):
        if not _USERNAME_RE.match(username):
            raise ValueError(
                f"Invalid username '{username}': must be 1-32 chars, "
                "alphanumeric, underscore, or hyphen."
            )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def user_exists(self, username: str) -> bool:
        """Return True if *username* has a user record."""
        return os.path.isfile(self._user_path(username))

    def add_user(self, username: str, password: str, role: str = "user") -> None:
        """Create a new user record and home directory."""
        self._validate_username(username)
        if role not in _VALID_ROLES:
            raise ValueError(f"Invalid role '{role}': must be one of {_VALID_ROLES}.")
        with self._lock:
            if self.user_exists(username):
                raise ValueError(f"User '{username}' already exists.")
            aura_home = os.environ.get("AURA_HOME", os.path.expanduser("~/.aura"))
            home_dir = os.path.join(aura_home, "home", username)
            os.makedirs(home_dir, exist_ok=True)
            record = {
                "username": username,
                "password_hash": self._hash(password),
                "role": role,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "home": f"~/.aura/home/{username}",
                "shell": "/aura/bin/sh",
            }
            with open(self._user_path(username), "w", encoding="utf-8") as fh:
                json.dump(record, fh, indent=2)

    def remove_user(self, username: str) -> None:
        """Delete a user record."""
        with self._lock:
            path = self._user_path(username)
            if not os.path.isfile(path):
                raise KeyError(f"User '{username}' not found.")
            os.remove(path)

    def get_user(self, username: str) -> Optional[dict]:
        """Return the raw user record dict or *None* if not found."""
        path = self._user_path(username)
        if not os.path.isfile(path):
            return None
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)

    def list_users(self) -> list:
        """Return a list of user dicts without ``password_hash``."""
        users = []
        for fname in sorted(os.listdir(self._base)):
            if not fname.endswith(".json"):
                continue
            path = os.path.join(self._base, fname)
            try:
                with open(path, "r", encoding="utf-8") as fh:
                    record = json.load(fh)
                record.pop("password_hash", None)
                users.append(record)
            except (OSError, json.JSONDecodeError):
                continue
        return users

    def authenticate(self, username: str, password: str) -> bool:
        """Return True if *password* matches the stored hash for *username*."""
        record = self.get_user(username)
        if record is None:
            return False
        return record.get("password_hash") == self._hash(password)

    def set_password(self, username: str, old_password: str, new_password: str) -> bool:
        """Change password; returns True on success, False if old password is wrong."""
        with self._lock:
            record = self.get_user(username)
            if record is None:
                raise KeyError(f"User '{username}' not found.")
            if record.get("password_hash") != self._hash(old_password):
                return False
            record["password_hash"] = self._hash(new_password)
            with open(self._user_path(username), "w", encoding="utf-8") as fh:
                json.dump(record, fh, indent=2)
            return True

    def get_current_user(self) -> str:
        """Return the active AURA user name."""
        return os.environ.get("AURA_USER") or getpass.getuser()
