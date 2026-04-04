"""Network manager for AURA OS.

Enhancements vs original:
- **Interface stats**: TX/RX bytes, packets, errors, drops (via psutil)
- **Port scanning**: check a range of TCP ports on a host
- **Traceroute**: hop-by-hop path to destination (cross-platform)
- **Bandwidth estimation**: simple throughput test via HTTP download
- **Reverse DNS**: IP → hostname lookup
- **Public IP detection**: fetch external IP from a public API
"""

import socket
import subprocess
import sys
import time
from typing import Dict, List, Optional


class NetworkManager:
    """Provides network introspection and utility methods."""

    # ------------------------------------------------------------------
    # Interface listing
    # ------------------------------------------------------------------

    def list_interfaces(self) -> list:
        """Return a list of network interface dicts.

        Each dict contains: name, addresses, is_up, is_loopback.
        Falls back through psutil → /proc/net/dev → ifconfig.
        """
        try:
            return self._interfaces_psutil()
        except Exception:
            pass
        if sys.platform.startswith("linux"):
            try:
                return self._interfaces_proc()
            except Exception:
                pass
        try:
            return self._interfaces_ifconfig()
        except Exception:
            return []

    def _interfaces_psutil(self) -> list:
        import psutil  # optional dependency

        ifaces = []
        stats = psutil.net_if_stats()
        addrs = psutil.net_if_addrs()
        for name, stat in stats.items():
            addresses = [
                a.address
                for a in addrs.get(name, [])
                if a.address and not a.address.startswith("%")
            ]
            ifaces.append(
                {
                    "name": name,
                    "addresses": addresses,
                    "is_up": stat.isup,
                    "is_loopback": name == "lo" or name.startswith("lo"),
                }
            )
        return ifaces

    def _interfaces_proc(self) -> list:
        ifaces = []
        with open("/proc/net/dev", "r") as fh:
            lines = fh.readlines()[2:]
        for line in lines:
            name = line.split(":")[0].strip()
            if not name:
                continue
            addresses = self._get_addresses_socket(name)
            ifaces.append(
                {
                    "name": name,
                    "addresses": addresses,
                    "is_up": True,
                    "is_loopback": name == "lo",
                }
            )
        return ifaces

    def _interfaces_ifconfig(self) -> list:
        result = subprocess.run(
            ["ifconfig"], capture_output=True, text=True, timeout=5
        )
        ifaces = []
        current = None
        for line in result.stdout.splitlines():
            if line and not line.startswith(" ") and not line.startswith("\t"):
                name = line.split(":")[0].split()[0]
                current = {
                    "name": name,
                    "addresses": [],
                    "is_up": "UP" in line,
                    "is_loopback": "LOOPBACK" in line,
                }
                ifaces.append(current)
            elif current and ("inet " in line or "inet6 " in line):
                parts = line.split()
                try:
                    idx = parts.index("inet") if "inet" in parts else parts.index("inet6")
                    current["addresses"].append(parts[idx + 1])
                except (ValueError, IndexError):
                    pass
        return ifaces

    def _get_addresses_socket(self, iface: str) -> list:
        """Try to retrieve the IPv4 address for *iface* via socket."""
        try:
            import fcntl
            import struct

            SIOCGIFADDR = 0x8915
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            packed = struct.pack("256s", iface[:15].encode())
            result = fcntl.ioctl(s.fileno(), SIOCGIFADDR, packed)
            s.close()
            addr = socket.inet_ntoa(result[20:24])
            return [addr]
        except Exception:
            return []

    # ------------------------------------------------------------------
    # Interface I/O statistics
    # ------------------------------------------------------------------

    def interface_stats(self) -> List[Dict]:
        """Return per-interface TX/RX counters.

        Requires psutil.  Returns an empty list otherwise.

        Each dict: name, bytes_sent, bytes_recv, packets_sent,
        packets_recv, errin, errout, dropin, dropout.
        """
        try:
            import psutil
            counters = psutil.net_io_counters(pernic=True)
            return [
                {
                    "name": name,
                    "bytes_sent": c.bytes_sent,
                    "bytes_recv": c.bytes_recv,
                    "packets_sent": c.packets_sent,
                    "packets_recv": c.packets_recv,
                    "errin": c.errin,
                    "errout": c.errout,
                    "dropin": c.dropin,
                    "dropout": c.dropout,
                }
                for name, c in counters.items()
            ]
        except Exception:
            return []

    # ------------------------------------------------------------------
    # Connectivity
    # ------------------------------------------------------------------

    def check_connectivity(self, host: str = "8.8.8.8", port: int = 53, timeout: int = 3) -> bool:
        """Return True if a TCP connection to *host*:*port* succeeds."""
        try:
            with socket.create_connection((host, port), timeout=timeout):
                return True
        except OSError:
            return False

    # ------------------------------------------------------------------
    # Ping
    # ------------------------------------------------------------------

    def ping(self, host: str, count: int = 4, timeout: int = 5) -> dict:
        """Ping *host* and return a result dict.

        Keys: host, packets_sent, packets_received, avg_ms, success.
        """
        base = {
            "host": host,
            "packets_sent": count,
            "packets_received": 0,
            "avg_ms": 0.0,
            "success": False,
        }
        try:
            if sys.platform == "win32":
                cmd = ["ping", "-n", str(count), "-w", str(timeout * 1000), host]
            else:
                cmd = ["ping", "-c", str(count), "-W", str(timeout), host]
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=timeout * count + 5
            )
            output = result.stdout + result.stderr
            received = self._parse_ping_received(output)
            avg_ms = self._parse_ping_avg(output)
            base["packets_received"] = received
            base["avg_ms"] = avg_ms
            base["success"] = received > 0
        except Exception:
            pass
        return base

    def _parse_ping_received(self, output: str) -> int:
        import re

        for pattern in [
            r"(\d+) received",
            r"(\d+) packets received",
            r"Received = (\d+)",
        ]:
            m = re.search(pattern, output)
            if m:
                return int(m.group(1))
        return 0

    def _parse_ping_avg(self, output: str) -> float:
        import re

        for pattern in [
            r"min/avg/max[^=]*=\s*[\d.]+/([\d.]+)/",
            r"Average = ([\d.]+)ms",
            r"avg\s*=\s*([\d.]+)",
        ]:
            m = re.search(pattern, output)
            if m:
                return float(m.group(1))
        return 0.0

    # ------------------------------------------------------------------
    # Traceroute
    # ------------------------------------------------------------------

    def traceroute(self, host: str, max_hops: int = 30, timeout: int = 3) -> List[Dict]:
        """Perform a traceroute to *host* and return a list of hop dicts.

        Each dict: hop (int), ip (str or None), rtt_ms (float or None).

        Uses the system ``traceroute`` (Linux/macOS) or ``tracert`` (Windows).
        Returns an empty list on failure.
        """
        hops: List[Dict] = []
        try:
            if sys.platform == "win32":
                cmd = ["tracert", "-d", "-h", str(max_hops), "-w",
                       str(timeout * 1000), host]
            elif sys.platform == "darwin":
                cmd = ["traceroute", "-n", "-m", str(max_hops),
                       "-w", str(timeout), host]
            else:
                cmd = ["traceroute", "-n", "-m", str(max_hops),
                       "-w", str(timeout), host]

            result = subprocess.run(
                cmd, capture_output=True, text=True,
                timeout=max_hops * timeout + 10,
            )
            hops = self._parse_traceroute(result.stdout)
        except Exception:
            pass
        return hops

    def _parse_traceroute(self, output: str) -> List[Dict]:
        import re

        hops = []
        for line in output.splitlines():
            m = re.match(
                r"\s*(\d+)\s+(\*|[\d.]+|[a-zA-Z0-9._-]+)\s*"
                r"(?:(\*|\d+\.?\d*)\s*ms)?",
                line,
            )
            if not m:
                continue
            hop_num = int(m.group(1))
            ip_str = m.group(2)
            rtt_str = m.group(3)
            hops.append({
                "hop": hop_num,
                "ip": None if ip_str == "*" else ip_str,
                "rtt_ms": None if (rtt_str is None or rtt_str == "*")
                else float(rtt_str),
            })
        return hops

    # ------------------------------------------------------------------
    # Port scanning
    # ------------------------------------------------------------------

    def scan_ports(
        self,
        host: str,
        ports: List[int] = None,
        port_range: tuple = None,
        timeout: float = 1.0,
    ) -> List[Dict]:
        """Scan TCP ports on *host* and return open/closed status.

        Args:
            host: Target hostname or IP.
            ports: Explicit list of ports to scan.
            port_range: Tuple (start, end) for a range scan.
            timeout: Per-port connect timeout in seconds.

        Returns:
            List of dicts: ``{"port": int, "open": bool, "service": str}``.

        .. warning::
            Only scan hosts you own or have explicit permission to scan.
        """
        if ports is None:
            if port_range:
                ports = list(range(port_range[0], port_range[1] + 1))
            else:
                # Common ports
                ports = [
                    21, 22, 23, 25, 53, 80, 110, 143, 443, 465,
                    587, 993, 995, 3306, 3389, 5432, 6379, 8080, 8443, 27017,
                ]

        results = []
        for port in ports:
            open_flag = False
            try:
                with socket.create_connection((host, port), timeout=timeout):
                    open_flag = True
            except (ConnectionRefusedError, OSError):
                pass
            service = self._port_service(port) if open_flag else ""
            results.append({"port": port, "open": open_flag, "service": service})
        return results

    def _port_service(self, port: int) -> str:
        """Return a common service name for *port*, or empty string."""
        try:
            return socket.getservbyport(port, "tcp")
        except OSError:
            return ""

    # ------------------------------------------------------------------
    # DNS
    # ------------------------------------------------------------------

    def dns_lookup(self, hostname: str) -> list:
        """Return a list of IP address strings for *hostname*."""
        try:
            infos = socket.getaddrinfo(hostname, None)
            seen = []
            for info in infos:
                addr = info[4][0]
                if addr not in seen:
                    seen.append(addr)
            return seen
        except OSError:
            return []

    def reverse_dns(self, ip: str) -> Optional[str]:
        """Reverse-lookup an IP address to a hostname.  Returns None on failure."""
        try:
            return socket.gethostbyaddr(ip)[0]
        except OSError:
            return None

    # ------------------------------------------------------------------
    # Public IP
    # ------------------------------------------------------------------

    def get_public_ip(self, timeout: int = 5) -> Optional[str]:
        """Fetch the public (external) IP address via a web API.

        Returns the IP string or None if unreachable.
        """
        import urllib.request

        for url in (
            "https://api.ipify.org",
            "https://ifconfig.me/ip",
            "https://icanhazip.com",
        ):
            try:
                with urllib.request.urlopen(url, timeout=timeout) as resp:
                    ip = resp.read().decode().strip()
                    # Basic sanity: contains a dot (IPv4) or colon (IPv6)
                    if "." in ip or ":" in ip:
                        return ip
            except Exception:
                continue
        return None

    # ------------------------------------------------------------------
    # Bandwidth estimation
    # ------------------------------------------------------------------

    def estimate_bandwidth(
        self,
        url: str = "http://speedtest.tele2.net/1MB.zip",
        timeout: int = 15,
    ) -> Dict:
        """Estimate download bandwidth by timing an HTTP download.

        Returns a dict with ``bytes_downloaded``, ``elapsed_s``,
        ``speed_mbps``, ``success``.

        The default URL is a 1 MiB test file on a public speed-test server.
        """
        import urllib.request

        result = {
            "url": url,
            "bytes_downloaded": 0,
            "elapsed_s": 0.0,
            "speed_mbps": 0.0,
            "success": False,
        }
        try:
            start = time.monotonic()
            with urllib.request.urlopen(url, timeout=timeout) as resp:
                data = resp.read()
            elapsed = time.monotonic() - start
            result["bytes_downloaded"] = len(data)
            result["elapsed_s"] = round(elapsed, 3)
            result["speed_mbps"] = round(
                (len(data) * 8) / (elapsed * 1_000_000), 2
            ) if elapsed > 0 else 0.0
            result["success"] = True
        except Exception as exc:
            result["error"] = str(exc)
        return result

    # ------------------------------------------------------------------
    # Gateway / hostname
    # ------------------------------------------------------------------

    def get_default_gateway(self) -> Optional[str]:
        """Return the default gateway IP or None."""
        if sys.platform.startswith("linux"):
            return self._gateway_proc()
        if sys.platform == "darwin":
            return self._gateway_macos()
        return None

    def _gateway_proc(self) -> Optional[str]:
        try:
            with open("/proc/net/route", "r") as fh:
                for line in fh.readlines()[1:]:
                    parts = line.split()
                    if len(parts) >= 3 and parts[1] == "00000000":
                        gw_hex = parts[2]
                        gw_int = int(gw_hex, 16)
                        return socket.inet_ntoa(
                            gw_int.to_bytes(4, byteorder="little")
                        )
        except Exception:
            pass
        return None

    def _gateway_macos(self) -> Optional[str]:
        try:
            result = subprocess.run(
                ["route", "-n", "get", "default"],
                capture_output=True, text=True, timeout=5,
            )
            for line in result.stdout.splitlines():
                if "gateway:" in line:
                    return line.split("gateway:")[-1].strip()
        except Exception:
            pass
        return None

    def get_hostname(self) -> str:
        """Return the system hostname."""
        return socket.gethostname()

