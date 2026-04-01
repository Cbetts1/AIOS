"""``aura net`` command handler — networking operations."""

import json


class NetCommand:
    """Networking operations: ping, dns, http, scan, ifconfig."""

    def execute(self, args, eal) -> int:
        from aura_os.kernel.network import NetworkManager

        net = NetworkManager()
        sub = getattr(args, "net_command", None)

        if sub == "ping":
            host = getattr(args, "host", "8.8.8.8")
            result = net.ping(host)
            if result["reachable"]:
                print(f"  ✓ {host} reachable  ({result['latency_ms']} ms)")
            else:
                print(f"  ✗ {host} unreachable")
            return 0

        if sub == "dns":
            hostname = getattr(args, "hostname", "")
            result = net.dns_lookup(hostname)
            if result["addresses"]:
                print(f"  {hostname} → {', '.join(result['addresses'])}")
            else:
                print(f"  DNS lookup failed: {result.get('error', 'unknown')}")
            return 0

        if sub == "get":
            url = getattr(args, "url", "")
            result = net.http_get(url)
            if result["error"]:
                print(f"  Error: {result['error']}")
                return 1
            print(f"  Status: {result['status']}")
            print(result["body"][:2000])
            return 0

        if sub == "download":
            url = getattr(args, "url", "")
            dest = getattr(args, "dest", "download")
            result = net.download(url, dest)
            if result["ok"]:
                print(f"  ✓ Downloaded {result['size']} bytes → {result['path']}")
            else:
                print(f"  ✗ Download failed: {result['error']}")
            return 0

        if sub == "scan":
            host = getattr(args, "host", "localhost")
            results = net.port_scan(host)
            open_ports = [r for r in results if r["open"]]
            if open_ports:
                for r in open_ports:
                    svc = r["service"] or "unknown"
                    print(f"  {r['port']:>5}  open  ({svc})")
            else:
                print("  No open ports found")
            return 0

        if sub == "ifconfig":
            info = net.interfaces()
            print(f"  Hostname : {info['hostname']}")
            print(f"  FQDN     : {info['fqdn']}")
            print(f"  Local IP : {info['local_ip']}")
            online = net.is_online(timeout=3)
            print(f"  Online   : {'yes' if online else 'no'}")
            return 0

        # Default: show network status
        info = net.interfaces()
        online = net.is_online(timeout=3)
        print("─" * 50)
        print("  AURA OS — Network Status")
        print("─" * 50)
        print(f"  Hostname : {info['hostname']}")
        print(f"  Local IP : {info['local_ip']}")
        print(f"  Online   : {'yes' if online else 'no'}")
        print()
        return 0
