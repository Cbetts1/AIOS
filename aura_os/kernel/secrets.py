"""Encrypted secret / credential store for AURA OS.

Provides a lightweight secret manager stored under ``~/.aura/secrets/``:
- Secrets are encrypted at rest using AES-128-CBC (via ``cryptography``
  Fernet) when available, with an HMAC-XOR fallback otherwise.
- Thread-safe read/write with file-level locking
- Namespace support for grouping secrets
- TTL / expiry enforcement
- Secret rotation (versioned history)
- Append-only audit log (access events stored separately)
"""

import base64
import hashlib
import hmac
import json
import os
import threading
import time
from typing import Dict, List, Optional


def _make_fernet(key_bytes: bytes):
    """Return a ``cryptography.fernet.Fernet`` instance derived from *key_bytes*,
    or ``None`` if the package is not installed."""
    try:
        from cryptography.fernet import Fernet  # type: ignore
        # Fernet requires a 32-byte URL-safe base64 key
        fernet_key = base64.urlsafe_b64encode(key_bytes[:32])
        return Fernet(fernet_key)
    except ImportError:
        return None


class SecretStore:
    """File-backed encrypted secret manager.

    Encryption strategy (best available):
    1. ``cryptography`` Fernet (AES-128-CBC + HMAC-SHA256) — **recommended**
    2. HMAC-XOR stream cipher fallback — obfuscation only

    The encryption key is derived from a master passphrase via PBKDF2-HMAC
    (SHA-256, 100 000 iterations).

    Additional features vs the original implementation:
    - **TTL**: secrets can have an ``expires_at`` timestamp; expired entries
      are treated as missing.
    - **Rotation**: :meth:`rotate_secret` re-encrypts a secret with a new
      value while preserving one level of previous-value history.
    - **Audit log**: every ``get``, ``set``, ``delete``, and ``rotate``
      operation appends a JSON line to ``secrets/audit.log`` (key name and
      operation only — no values are logged).
    """

    AUDIT_FILE = "audit.log"

    def __init__(self, base_dir: str = None, passphrase: str = None):
        aura_home = os.environ.get("AURA_HOME",
                                   os.path.expanduser("~/.aura"))
        self._dir = base_dir or os.path.join(aura_home, "secrets")
        os.makedirs(self._dir, exist_ok=True)
        self._lock = threading.Lock()

        # Derive key material using PBKDF2-HMAC (100 k iterations)
        try:
            nodename = os.uname().nodename
        except AttributeError:
            import socket
            nodename = socket.gethostname()
        raw = passphrase or f"{nodename}:{aura_home}"
        self._key = hashlib.pbkdf2_hmac(
            "sha256", raw.encode(), b"aura-os-secrets-salt", iterations=100_000
        )
        self._fernet = _make_fernet(self._key)

    # ------------------------------------------------------------------
    # Encryption helpers
    # ------------------------------------------------------------------

    def _encrypt(self, plaintext: str) -> str:
        """Return an encrypted, base64-encoded representation of *plaintext*.

        Uses Fernet when available, otherwise falls back to HMAC-XOR.
        """
        data = plaintext.encode("utf-8")
        if self._fernet is not None:
            # Fernet already returns URL-safe base64 bytes
            return self._fernet.encrypt(data).decode("ascii")
        # Fallback: HMAC-XOR stream cipher
        stream = self._keystream(len(data))
        cipher = bytes(a ^ b for a, b in zip(data, stream))
        return "xor:" + base64.b64encode(cipher).decode("ascii")

    def _decrypt(self, ciphertext: str) -> str:
        """Decrypt *ciphertext* and return the original string."""
        if ciphertext.startswith("xor:"):
            # Legacy HMAC-XOR path
            cipher = base64.b64decode(ciphertext[4:])
            stream = self._keystream(len(cipher))
            plain = bytes(a ^ b for a, b in zip(cipher, stream))
            return plain.decode("utf-8")
        if self._fernet is not None:
            return self._fernet.decrypt(ciphertext.encode("ascii")).decode("utf-8")
        raise ValueError(
            "Secret was encrypted with Fernet but 'cryptography' is not installed. "
            "Install it with: pip install cryptography"
        )

    def _keystream(self, length: int) -> bytes:
        """Generate a repeating HMAC-based key-stream (XOR fallback only)."""
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
    # Audit log
    # ------------------------------------------------------------------

    def _audit(self, operation: str, key: str, namespace: str):
        """Append a single audit record (never raises)."""
        try:
            log_path = os.path.join(self._dir, self.AUDIT_FILE)
            record = {
                "ts": time.time(),
                "op": operation,
                "ns": namespace,
                "key": key,
            }
            with open(log_path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(record) + "\n")
            try:
                os.chmod(log_path, 0o600)
            except OSError:
                pass
        except Exception:
            pass

    def get_audit_log(self, limit: int = 100) -> List[Dict]:
        """Return the most recent *limit* audit records."""
        log_path = os.path.join(self._dir, self.AUDIT_FILE)
        if not os.path.isfile(log_path):
            return []
        records = []
        try:
            with open(log_path, "r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if line:
                        try:
                            records.append(json.loads(line))
                        except json.JSONDecodeError:
                            pass
        except OSError:
            pass
        return records[-limit:]

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _store_path(self, namespace: str = "default") -> str:
        # Sanitise: allow only alphanumeric, dash, and underscore characters
        import re as _re
        if not namespace or "\x00" in namespace:
            raise ValueError(f"Invalid secret namespace: {namespace!r}")
        safe = _re.sub(r"[^A-Za-z0-9_-]", "_", namespace)
        if not safe:
            raise ValueError(f"Invalid secret namespace: {namespace!r}")
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
        # Atomic write: write to a temp file then rename
        tmp_path = path + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)
        os.replace(tmp_path, path)
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_secret(self, key: str, value: str,
                   namespace: str = "default",
                   ttl: Optional[float] = None) -> Dict:
        """Store an encrypted secret.

        Args:
            key: Secret name.
            value: Secret value (will be encrypted at rest).
            namespace: Logical grouping namespace.
            ttl: Optional time-to-live in seconds.  After this many
                 seconds the secret is treated as expired/missing.

        Returns:
            Metadata dict with ``key``, ``namespace``, ``ok``.
        """
        with self._lock:
            store = self._load(namespace)
            existing = store.get(key, {})
            entry: Dict = {
                "value": self._encrypt(value),
                "created": existing.get("created", time.time()),
                "updated": time.time(),
            }
            if ttl is not None:
                entry["expires_at"] = time.time() + ttl
            elif "expires_at" in existing:
                # Preserve existing TTL on update unless explicitly removed
                entry["expires_at"] = existing["expires_at"]
            store[key] = entry
            self._save(store, namespace)
        self._audit("set", key, namespace)
        return {"key": key, "namespace": namespace, "ok": True}

    def get_secret(self, key: str,
                   namespace: str = "default") -> Optional[str]:
        """Retrieve and decrypt a secret.

        Returns ``None`` if the key does not exist or has expired.
        """
        with self._lock:
            store = self._load(namespace)
            entry = store.get(key)
        if entry is None:
            return None
        # Enforce TTL
        if "expires_at" in entry and time.time() > entry["expires_at"]:
            return None
        try:
            result = self._decrypt(entry["value"])
            self._audit("get", key, namespace)
            return result
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
                self._audit("delete", key, namespace)
                return True
        return False

    def rotate_secret(self, key: str, new_value: str,
                      namespace: str = "default") -> Dict:
        """Replace *key* with *new_value*, preserving the previous value.

        The previous encrypted value is stored under
        ``{key}.__prev__`` so it can be retrieved if rotation needs
        to be rolled back.

        Returns metadata dict with ``key``, ``namespace``, ``ok``,
        ``rotated_at``.
        """
        with self._lock:
            store = self._load(namespace)
            existing = store.get(key)
            if existing:
                # Preserve old encrypted value under a shadow key
                store[f"{key}.__prev__"] = {
                    "value": existing["value"],
                    "rotated_at": time.time(),
                    "was_key": key,
                }
            created = existing.get("created", time.time()) if existing else time.time()
            store[key] = {
                "value": self._encrypt(new_value),
                "created": created,
                "updated": time.time(),
            }
            if existing and "expires_at" in existing:
                store[key]["expires_at"] = existing["expires_at"]
            self._save(store, namespace)
        self._audit("rotate", key, namespace)
        return {"key": key, "namespace": namespace, "ok": True,
                "rotated_at": time.time()}

    def list_secrets(self, namespace: str = "default",
                     include_expired: bool = False) -> List[Dict]:
        """List all secret keys (not values) in a namespace.

        Expired secrets are hidden by default.
        """
        with self._lock:
            store = self._load(namespace)
        now = time.time()
        result = []
        for k, v in store.items():
            if k.endswith(".__prev__"):
                continue  # hide rotation shadow entries
            expires_at = v.get("expires_at")
            is_expired = expires_at is not None and now > expires_at
            if is_expired and not include_expired:
                continue
            result.append({
                "key": k,
                "created": v.get("created"),
                "updated": v.get("updated"),
                "expires_at": expires_at,
                "expired": is_expired,
                "encrypted_with": "fernet" if not v["value"].startswith("xor:") else "xor",
            })
        return result

    def list_namespaces(self) -> List[str]:
        """List all secret namespaces."""
        namespaces = []
        if os.path.isdir(self._dir):
            for f in os.listdir(self._dir):
                if f.endswith(".json"):
                    namespaces.append(f[:-5])
        return sorted(namespaces)
