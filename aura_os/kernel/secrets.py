"""Encrypted secret / credential store for AURA OS.

Provides a lightweight secret manager stored under ``~/.aura/secrets/``:
- Secrets are encrypted at rest using HMAC-derived XOR obfuscation
  (sufficient for casual protection; swap to Fernet for production use)
- Thread-safe read/write
- Namespace support for grouping secrets
"""

import base64
import hashlib
import hmac
import json
import os
import threading
import time
from typing import Dict, List, Optional


class SecretStore:
    """File-backed encrypted secret manager.

    Secrets are stored as base64-encoded, HMAC-XOR-obfuscated blobs in a
    JSON file.  The encryption key is derived from a master passphrase
    (defaults to the machine's hostname + AURA_HOME path if none is set).

    .. note::

       This provides *obfuscation*, not cryptographic security.  For
       production use, integrate with ``cryptography.fernet`` or a
       system keyring.
    """

    def __init__(self, base_dir: str = None, passphrase: str = None):
        aura_home = os.environ.get("AURA_HOME",
                                   os.path.expanduser("~/.aura"))
        self._dir = base_dir or os.path.join(aura_home, "secrets")
        os.makedirs(self._dir, exist_ok=True)
        self._lock = threading.Lock()
        # Derive key material using a proper KDF
        raw = passphrase or f"{os.uname().nodename}:{aura_home}"
        self._key = hashlib.pbkdf2_hmac(
            "sha256", raw.encode(), b"aura-os-secrets-salt", iterations=100_000
        )

    # ------------------------------------------------------------------
    # Encryption helpers
    # ------------------------------------------------------------------

    def _encrypt(self, plaintext: str) -> str:
        """Return a base64-encoded obfuscated version of *plaintext*."""
        data = plaintext.encode("utf-8")
        stream = self._keystream(len(data))
        cipher = bytes(a ^ b for a, b in zip(data, stream))
        return base64.b64encode(cipher).decode("ascii")

    def _decrypt(self, ciphertext: str) -> str:
        """Reverse the obfuscation and return the original string."""
        cipher = base64.b64decode(ciphertext)
        stream = self._keystream(len(cipher))
        plain = bytes(a ^ b for a, b in zip(cipher, stream))
        return plain.decode("utf-8")

    def _keystream(self, length: int) -> bytes:
        """Generate a repeating key-stream from the master key."""
        stream = b""
        counter = 0
        while len(stream) < length:
            block = hmac.new(self._key,
                             counter.to_bytes(4, "big"),
                             hashlib.sha256).digest()
            stream += block
            counter += 1
        return stream[:length]

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _store_path(self, namespace: str = "default") -> str:
        safe = namespace.replace("/", "_").replace("..", "__")
        return os.path.join(self._dir, f"{safe}.json")

    def _load(self, namespace: str = "default") -> Dict:
        path = self._store_path(namespace)
        if not os.path.isfile(path):
            return {}
        with open(path, "r", encoding="utf-8") as fh:
            try:
                return json.load(fh)
            except json.JSONDecodeError:
                return {}

    def _save(self, data: Dict, namespace: str = "default"):
        path = self._store_path(namespace)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)
        # Restrict file permissions (owner-only)
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_secret(self, key: str, value: str,
                   namespace: str = "default") -> Dict:
        """Store an encrypted secret.  Returns metadata dict."""
        with self._lock:
            store = self._load(namespace)
            store[key] = {
                "value": self._encrypt(value),
                "created": store.get(key, {}).get("created", time.time()),
                "updated": time.time(),
            }
            self._save(store, namespace)
        return {"key": key, "namespace": namespace, "ok": True}

    def get_secret(self, key: str,
                   namespace: str = "default") -> Optional[str]:
        """Retrieve and decrypt a secret.  Returns None if not found."""
        with self._lock:
            store = self._load(namespace)
            entry = store.get(key)
        if entry is None:
            return None
        try:
            return self._decrypt(entry["value"])
        except Exception:
            return None

    def delete_secret(self, key: str,
                      namespace: str = "default") -> bool:
        """Delete a secret.  Returns True on success."""
        with self._lock:
            store = self._load(namespace)
            if key in store:
                del store[key]
                self._save(store, namespace)
                return True
        return False

    def list_secrets(self, namespace: str = "default") -> List[Dict]:
        """List all secret keys (not values) in a namespace."""
        with self._lock:
            store = self._load(namespace)
        return [
            {"key": k, "created": v.get("created"),
             "updated": v.get("updated")}
            for k, v in store.items()
        ]

    def list_namespaces(self) -> List[str]:
        """List all secret namespaces."""
        namespaces = []
        if os.path.isdir(self._dir):
            for f in os.listdir(self._dir):
                if f.endswith(".json"):
                    namespaces.append(f[:-5])
        return sorted(namespaces)
