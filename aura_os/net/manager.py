"""Network manager for AURA OS."""

import socket
import subprocess
import sys
from typing import Optional


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
