"""HTTP/cloud client for AURA OS.

Provides real HTTP/HTTPS capabilities for:
- API calls to remote services
- File downloads
- Health checks / pinging remote endpoints
- JSON API interaction
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from typing import Any, Dict, Optional, Tuple


DEFAULT_TIMEOUT = 10


class CloudClient:
    """Real HTTP client for cloud/remote API interaction.

    All methods use Python stdlib ``urllib`` — no extra dependencies required.
    The client adds AURA OS user-agent headers and handles common errors.

    Args:
        base_url: Optional base URL prepended to relative paths.
        timeout: Request timeout in seconds (default 10).
        headers: Default HTTP headers to include in every request.
    """

    _USER_AGENT = "AURA-OS/0.2.0 (cloud-client)"

    def __init__(self, base_url: str = "", timeout: int = DEFAULT_TIMEOUT,
                 headers: Optional[Dict[str, str]] = None):
        self._base = base_url.rstrip("/")
        self._timeout = timeout
        self._headers = headers or {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def ping(self, url: str) -> Tuple[bool, int, float]:
        """Ping an HTTP endpoint.

        Returns:
            Tuple of (reachable, status_code, latency_ms).
        """
        full_url = self._resolve(url)
        start = time.monotonic()
        try:
            req = urllib.request.Request(
                full_url, method="HEAD", headers=self._build_headers()
            )
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                code = resp.status
            latency = (time.monotonic() - start) * 1000
            return True, code, round(latency, 1)
        except urllib.error.HTTPError as exc:
            latency = (time.monotonic() - start) * 1000
            return True, exc.code, round(latency, 1)
        except (urllib.error.URLError, OSError, TimeoutError):
            return False, 0, 0.0

    def get(self, path: str, params: Optional[Dict[str, str]] = None,
            as_json: bool = True) -> Tuple[int, Any]:
        """Perform an HTTP GET.

        Args:
            path: URL path (appended to base_url if relative).
            params: Query-string parameters.
            as_json: If True, decode response body as JSON.

        Returns:
            Tuple of (status_code, response_body).
        """
        url = self._resolve(path)
        if params:
            qs = "&".join(f"{k}={v}" for k, v in params.items())
            url = f"{url}?{qs}"
        try:
            req = urllib.request.Request(url, headers=self._build_headers())
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                body = resp.read()
                code = resp.status
            if as_json:
                try:
                    return code, json.loads(body)
                except (json.JSONDecodeError, ValueError):
                    return code, body.decode("utf-8", errors="replace")
            return code, body.decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            return exc.code, exc.reason
        except (urllib.error.URLError, OSError) as exc:
            return 0, str(exc)

    def post_json(self, path: str,
                  data: Dict[str, Any]) -> Tuple[int, Any]:
        """Perform an HTTP POST with a JSON body.

        Returns:
            Tuple of (status_code, response_body).
        """
        url = self._resolve(path)
        payload = json.dumps(data).encode("utf-8")
        headers = self._build_headers()
        headers["Content-Type"] = "application/json"
        headers["Content-Length"] = str(len(payload))
        try:
            req = urllib.request.Request(
                url, data=payload, headers=headers, method="POST"
            )
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                body = resp.read()
                code = resp.status
            try:
                return code, json.loads(body)
            except (json.JSONDecodeError, ValueError):
                return code, body.decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            return exc.code, exc.reason
        except (urllib.error.URLError, OSError) as exc:
            return 0, str(exc)

    def download(self, url: str, dest_path: str,
                 chunk_size: int = 65536) -> Tuple[bool, str]:
        """Download a file to *dest_path*.

        Returns:
            Tuple of (success, message).
        """
        full_url = self._resolve(url)
        try:
            req = urllib.request.Request(full_url, headers=self._build_headers())
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                with open(dest_path, "wb") as fh:
                    while True:
                        chunk = resp.read(chunk_size)
                        if not chunk:
                            break
                        fh.write(chunk)
            return True, dest_path
        except (urllib.error.URLError, OSError) as exc:
            return False, str(exc)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _resolve(self, path: str) -> str:
        if path.startswith("http://") or path.startswith("https://"):
            return path
        return f"{self._base}/{path.lstrip('/')}" if self._base else path

    def _build_headers(self) -> Dict[str, str]:
        h = {"User-Agent": self._USER_AGENT}
        h.update(self._headers)
        return h


# ---------------------------------------------------------------------------
# CLI command wrapper
# ---------------------------------------------------------------------------

class CloudCommand:
    """``aura cloud`` — cloud and remote API operations."""

    def execute(self, args, eal) -> int:
        sub = getattr(args, "cloud_cmd", "status")
        if sub == "ping":
            return self._cmd_ping(args)
        if sub == "get":
            return self._cmd_get(args)
        if sub == "nodes":
            return self._cmd_nodes(args)
        if sub == "status":
            return self._cmd_status()
        print(f"[cloud] Unknown sub-command: {sub}")
        return 1

    def _cmd_status(self) -> int:
        print("[cloud] Cloud layer operational.")
        print("[cloud] Use: aura cloud ping <url>")
        print("             aura cloud get <url>")
        print("             aura cloud nodes")
        return 0

    def _cmd_ping(self, args) -> int:
        url = getattr(args, "url", None)
        if not url:
            print("[cloud ping] Usage: aura cloud ping <url>")
            return 1
        client = CloudClient()
        reachable, code, latency = client.ping(url)
        sym = "✓" if reachable else "✗"
        print(f"  {sym}  {url}  code={code}  latency={latency}ms")
        return 0 if reachable else 1

    def _cmd_get(self, args) -> int:
        url = getattr(args, "url", None)
        if not url:
            print("[cloud get] Usage: aura cloud get <url>")
            return 1
        import json as _json
        client = CloudClient()
        code, body = client.get(url)
        print(f"[cloud] HTTP {code}")
        if isinstance(body, (dict, list)):
            print(_json.dumps(body, indent=2))
        else:
            print(body[:2000])
        return 0 if code in range(200, 300) else 1

    def _cmd_nodes(self, args) -> int:
        from aura_os.cloud.nodes import NodeRegistry
        import os
        home = os.environ.get("AURA_HOME", os.path.expanduser("~/.aura"))
        nr = NodeRegistry(home)
        nodes = nr.list_nodes()
        if not nodes:
            print("[cloud] No nodes registered.  Use: aura cloud nodes add <name> <url>")
            return 0
        print("[cloud] Registered nodes:")
        for node in nodes:
            status = node.get("status", "unknown")
            sym = "✓" if status == "online" else "○"
            print(f"  {sym}  {node['name']:<20}  {node['url']}")
        return 0
