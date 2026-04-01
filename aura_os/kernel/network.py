"""Networking subsystem for AURA OS.

Provides lightweight, portable networking primitives:
- Connectivity checks (ping, DNS)
- HTTP client (GET/POST/download)
- Port scanning
- Network interface information
"""

import json
import os
import socket
import threading
import time
from typing import Dict, List, Optional
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError
from urllib.parse import urlparse


class NetworkManager:
    """Lightweight networking layer for AURA OS.

    Uses only stdlib (urllib, socket) so it works on every platform
    without any third-party dependencies.
    """

    _lock = threading.Lock()

    def __init__(self, timeout: int = 10):
        self._timeout = timeout
        self._dns_cache: Dict[str, str] = {}

    # ------------------------------------------------------------------
    # Connectivity
    # ------------------------------------------------------------------

    def ping(self, host: str = "8.8.8.8", port: int = 53,
             timeout: Optional[int] = None) -> Dict:
        """TCP-based connectivity check (works without root/raw sockets).

        Returns dict with ``reachable`` bool and ``latency_ms``.
        """
        t = timeout or self._timeout
        start = time.monotonic()
        try:
            sock = socket.create_connection((host, port), timeout=t)
            sock.close()
            latency = round((time.monotonic() - start) * 1000, 2)
            return {"reachable": True, "host": host, "port": port,
                    "latency_ms": latency}
        except (OSError, socket.timeout):
            return {"reachable": False, "host": host, "port": port,
                    "latency_ms": None}

    def is_online(self, timeout: int = 5) -> bool:
        """Quick check whether the host has internet connectivity."""
        return self.ping("8.8.8.8", 53, timeout=timeout)["reachable"]

    # ------------------------------------------------------------------
    # DNS
    # ------------------------------------------------------------------

    def dns_lookup(self, hostname: str) -> Dict:
        """Resolve *hostname* to IP addresses."""
        with self._lock:
            if hostname in self._dns_cache:
                return {"hostname": hostname,
                        "addresses": [self._dns_cache[hostname]],
                        "cached": True}
        try:
            results = socket.getaddrinfo(hostname, None, socket.AF_UNSPEC,
                                         socket.SOCK_STREAM)
            addrs = list({r[4][0] for r in results})
            with self._lock:
                if addrs:
                    self._dns_cache[hostname] = addrs[0]
            return {"hostname": hostname, "addresses": addrs, "cached": False}
        except socket.gaierror as exc:
            return {"hostname": hostname, "addresses": [],
                    "error": str(exc), "cached": False}

    def reverse_dns(self, ip: str) -> Dict:
        """Reverse-DNS lookup for an IP address."""
        try:
            hostname, _, _ = socket.gethostbyaddr(ip)
            return {"ip": ip, "hostname": hostname}
        except (socket.herror, socket.gaierror) as exc:
            return {"ip": ip, "hostname": None, "error": str(exc)}

    # ------------------------------------------------------------------
    # HTTP client
    # ------------------------------------------------------------------

    def http_get(self, url: str, headers: Optional[Dict] = None,
                 timeout: Optional[int] = None) -> Dict:
        """Perform an HTTP GET request.  Returns dict with status, body, headers."""
        t = timeout or self._timeout
        req = Request(url, method="GET")
        req.add_header("User-Agent", "AURA-OS/0.2")
        for k, v in (headers or {}).items():
            req.add_header(k, v)
        try:
            resp = urlopen(req, timeout=t)
            body = resp.read().decode("utf-8", errors="replace")
            return {"status": resp.status, "body": body,
                    "headers": dict(resp.headers), "error": None}
        except HTTPError as exc:
            return {"status": exc.code, "body": exc.read().decode(
                "utf-8", errors="replace"), "headers": {}, "error": str(exc)}
        except URLError as exc:
            return {"status": None, "body": "", "headers": {},
                    "error": str(exc)}

    def http_post(self, url: str, data: Optional[dict] = None,
                  headers: Optional[Dict] = None,
                  timeout: Optional[int] = None) -> Dict:
        """Perform an HTTP POST request with a JSON body."""
        t = timeout or self._timeout
        payload = json.dumps(data or {}).encode("utf-8")
        req = Request(url, data=payload, method="POST")
        req.add_header("User-Agent", "AURA-OS/0.2")
        req.add_header("Content-Type", "application/json")
        for k, v in (headers or {}).items():
            req.add_header(k, v)
        try:
            resp = urlopen(req, timeout=t)
            body = resp.read().decode("utf-8", errors="replace")
            return {"status": resp.status, "body": body,
                    "headers": dict(resp.headers), "error": None}
        except HTTPError as exc:
            return {"status": exc.code, "body": exc.read().decode(
                "utf-8", errors="replace"), "headers": {}, "error": str(exc)}
        except URLError as exc:
            return {"status": None, "body": "", "headers": {},
                    "error": str(exc)}

    def download(self, url: str, dest: str,
                 timeout: Optional[int] = None) -> Dict:
        """Download a file from *url* and write it to *dest*.

        Returns dict with ``ok``, ``size``, and ``path`` on success.
        """
        t = timeout or self._timeout
        req = Request(url, method="GET")
        req.add_header("User-Agent", "AURA-OS/0.2")
        try:
            resp = urlopen(req, timeout=t)
            os.makedirs(os.path.dirname(dest) or ".", exist_ok=True)
            with open(dest, "wb") as fh:
                data = resp.read()
                fh.write(data)
            return {"ok": True, "size": len(data), "path": dest,
                    "error": None}
        except (HTTPError, URLError, OSError) as exc:
            return {"ok": False, "size": 0, "path": dest,
                    "error": str(exc)}

    # ------------------------------------------------------------------
    # Port scanning
    # ------------------------------------------------------------------

    def port_scan(self, host: str, ports: Optional[List[int]] = None,
                  timeout: float = 1.0) -> List[Dict]:
        """Scan common (or specified) TCP ports on *host*.

        Returns list of dicts with ``port``, ``open``, ``service`` keys.
        """
        common_ports = ports or [
            22, 53, 80, 443, 3000, 3306, 5432, 6379, 8000, 8080, 8443, 9090,
        ]
        results = []
        for port in common_ports:
            try:
                sock = socket.create_connection((host, port), timeout=timeout)
                sock.close()
                svc = self._guess_service(port)
                results.append({"port": port, "open": True, "service": svc})
            except (OSError, socket.timeout):
                results.append({"port": port, "open": False, "service": None})
        return results

    # ------------------------------------------------------------------
    # Network interfaces
    # ------------------------------------------------------------------

    def interfaces(self) -> Dict:
        """Return basic network interface information."""
        info: Dict = {"hostname": socket.gethostname()}
        try:
            info["fqdn"] = socket.getfqdn()
        except Exception:
            info["fqdn"] = info["hostname"]
        # Local IP via a UDP-connect trick (no packets actually sent)
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("192.0.2.1", 80))
            info["local_ip"] = s.getsockname()[0]
            s.close()
        except Exception:
            info["local_ip"] = "127.0.0.1"
        return info

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _guess_service(port: int) -> Optional[str]:
        """Return a human-readable service name for common ports."""
        services = {
            22: "ssh", 53: "dns", 80: "http", 443: "https",
            3000: "dev-server", 3306: "mysql", 5432: "postgres",
            6379: "redis", 8000: "http-alt", 8080: "http-proxy",
            8443: "https-alt", 9090: "prometheus",
        }
        return services.get(port)
