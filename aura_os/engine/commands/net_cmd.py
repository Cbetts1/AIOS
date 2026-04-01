"""Network management command handler for AURA OS."""


class NetCommand:
    """Handles the ``net`` sub-command."""

    def execute(self, args, eal) -> int:
        from aura_os.net import NetworkManager

        nm = NetworkManager()
        sub = args.net_command

        if sub == "status":
            return self._status(nm)
        if sub == "ifconfig":
            return self._ifconfig(nm)
        if sub == "ping":
            return self._ping(nm, args)
        if sub == "dns":
            return self._dns(nm, args)
        if sub == "download":
            return self._download(nm, args)
        print(f"net: unknown sub-command '{sub}'")
        return 1

    # ------------------------------------------------------------------

    def _status(self, nm) -> int:
        connected = nm.check_connectivity()
        hostname = nm.get_hostname()
        gateway = nm.get_default_gateway() or "unknown"
        status = "connected" if connected else "disconnected"
        print(f"  Status:   {status}")
        print(f"  Hostname: {hostname}")
        print(f"  Gateway:  {gateway}")
        return 0

    def _ifconfig(self, nm) -> int:
        ifaces = nm.list_interfaces()
        if not ifaces:
            print("  (no interfaces found)")
            return 0
        for iface in ifaces:
            status = "UP" if iface.get("is_up") else "DOWN"
            addrs = ", ".join(iface.get("addresses", [])) or "no address"
            print(f"  {iface['name']:<15} {status:<6}  {addrs}")
        return 0

    def _ping(self, nm, args) -> int:
        host = args.host
        count = getattr(args, "count", 4)
        result = nm.ping(host, count=count)
        if result.get("success"):
            recv = result["packets_received"]
            sent = result["packets_sent"]
            avg = result.get("avg_ms", 0.0)
            print(f"  PING {host}: {recv}/{sent} received, avg {avg:.1f} ms")
        else:
            print(f"  PING {host}: failed — host unreachable or ping not available")
        return 0 if result.get("success") else 1

    def _dns(self, nm, args) -> int:
        addresses = nm.dns_lookup(args.hostname)
        if not addresses:
            print(f"  dns: could not resolve '{args.hostname}'")
            return 1
        for addr in addresses:
            print(f"  {addr}")
        return 0

    def _download(self, nm, args) -> int:
        url = args.url
        dest = args.dest
        result = nm.download(url, dest)
        if result.get("ok"):
            size = result.get("bytes", 0)
            print(f"  ✓ Downloaded {url} → {dest} ({size} bytes)")
            return 0
        print(f"  ✗ Download failed: {result.get('error', 'unknown')}")
        return 1
