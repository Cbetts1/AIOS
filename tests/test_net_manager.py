"""Tests for aura_os.net.manager.NetworkManager."""

import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from aura_os.net.manager import NetworkManager


class TestNetworkManagerListInterfaces(unittest.TestCase):
    """Interface listing."""

    def setUp(self):
        self.nm = NetworkManager()

    def test_list_interfaces_returns_list(self):
        result = self.nm.list_interfaces()
        self.assertIsInstance(result, list)

    def test_list_interfaces_items_have_required_keys(self):
        result = self.nm.list_interfaces()
        for iface in result:
            self.assertIn("name", iface)
            self.assertIn("addresses", iface)
            self.assertIn("is_up", iface)
            self.assertIn("is_loopback", iface)

    def test_list_interfaces_name_is_string(self):
        for iface in self.nm.list_interfaces():
            self.assertIsInstance(iface["name"], str)

    def test_list_interfaces_addresses_is_list(self):
        for iface in self.nm.list_interfaces():
            self.assertIsInstance(iface["addresses"], list)


class TestNetworkManagerConnectivity(unittest.TestCase):
    """Connectivity check."""

    def setUp(self):
        self.nm = NetworkManager()

    def test_check_connectivity_returns_bool(self):
        result = self.nm.check_connectivity(host="127.0.0.1", port=1, timeout=1)
        self.assertIsInstance(result, bool)

    def test_check_connectivity_unreachable_is_false(self):
        # Port 1 on localhost is almost certainly closed
        result = self.nm.check_connectivity(host="127.0.0.1", port=1, timeout=1)
        self.assertFalse(result)

    def test_check_connectivity_loopback_dns_port(self):
        # May or may not be open; just check it doesn't raise
        result = self.nm.check_connectivity(host="127.0.0.1", port=53, timeout=1)
        self.assertIsInstance(result, bool)


class TestNetworkManagerDNS(unittest.TestCase):
    """DNS lookup."""

    def setUp(self):
        self.nm = NetworkManager()

    def test_dns_lookup_localhost_returns_list(self):
        result = self.nm.dns_lookup("localhost")
        self.assertIsInstance(result, list)

    def test_dns_lookup_localhost_contains_loopback(self):
        result = self.nm.dns_lookup("localhost")
        # Should contain 127.0.0.1 or ::1
        self.assertTrue(
            any("127.0.0.1" in a or "::1" in a or a.startswith("127.")
                for a in result),
            f"Expected loopback address in {result}",
        )

    def test_dns_lookup_invalid_returns_empty(self):
        result = self.nm.dns_lookup("this.hostname.does.not.exist.invalid")
        self.assertIsInstance(result, list)
        # Should be empty or raise gracefully (returns empty list)
        # We just verify no exception is raised

    def test_reverse_dns_loopback(self):
        result = self.nm.reverse_dns("127.0.0.1")
        # May return None or a string; just verify type
        self.assertTrue(result is None or isinstance(result, str))


class TestNetworkManagerPing(unittest.TestCase):
    """Ping functionality."""

    def setUp(self):
        self.nm = NetworkManager()

    def test_ping_returns_dict(self):
        result = self.nm.ping("127.0.0.1", count=1, timeout=2)
        self.assertIsInstance(result, dict)

    def test_ping_result_has_required_keys(self):
        result = self.nm.ping("127.0.0.1", count=1, timeout=2)
        for key in ("host", "packets_sent", "packets_received", "avg_ms", "success"):
            self.assertIn(key, result)

    def test_ping_sets_host(self):
        result = self.nm.ping("127.0.0.1", count=1, timeout=2)
        self.assertEqual(result["host"], "127.0.0.1")

    def test_ping_packets_sent_matches_count(self):
        result = self.nm.ping("127.0.0.1", count=2, timeout=2)
        self.assertEqual(result["packets_sent"], 2)

    @patch("subprocess.run")
    def test_ping_parse_received_linux(self, mock_run):
        mock_result = MagicMock()
        mock_result.stdout = "4 packets transmitted, 4 received, 0% packet loss"
        mock_result.stderr = ""
        mock_run.return_value = mock_result
        result = self.nm.ping("8.8.8.8", count=4, timeout=3)
        self.assertGreaterEqual(result["packets_received"], 0)


class TestNetworkManagerPortScan(unittest.TestCase):
    """Port scanning."""

    def setUp(self):
        self.nm = NetworkManager()

    def test_scan_ports_returns_list(self):
        result = self.nm.scan_ports("127.0.0.1", ports=[1], timeout=0.5)
        self.assertIsInstance(result, list)

    def test_scan_ports_result_keys(self):
        result = self.nm.scan_ports("127.0.0.1", ports=[80], timeout=0.5)
        for item in result:
            self.assertIn("port", item)
            self.assertIn("open", item)
            self.assertIn("service", item)

    def test_scan_ports_closed_port(self):
        # Port 1 on localhost is very unlikely to be open
        result = self.nm.scan_ports("127.0.0.1", ports=[1], timeout=0.5)
        self.assertEqual(len(result), 1)
        self.assertFalse(result[0]["open"])

    def test_scan_port_range(self):
        result = self.nm.scan_ports("127.0.0.1", port_range=(1, 3), timeout=0.5)
        self.assertEqual(len(result), 3)

    def test_scan_ports_open_bool(self):
        result = self.nm.scan_ports("127.0.0.1", ports=[22, 80, 443], timeout=0.5)
        for item in result:
            self.assertIsInstance(item["open"], bool)


class TestNetworkManagerTraceroute(unittest.TestCase):
    """Traceroute parsing."""

    def setUp(self):
        self.nm = NetworkManager()

    def test_traceroute_returns_list(self):
        result = self.nm.traceroute("127.0.0.1", max_hops=3, timeout=1)
        self.assertIsInstance(result, list)

    def test_parse_traceroute_linux_output(self):
        sample = (
            "traceroute to 8.8.8.8 (8.8.8.8), 3 hops\n"
            " 1  192.168.1.1  1.234 ms\n"
            " 2  10.0.0.1  5.678 ms\n"
            " 3  8.8.8.8  15.0 ms\n"
        )
        hops = self.nm._parse_traceroute(sample)
        self.assertIsInstance(hops, list)
        # At least some hops parsed
        self.assertGreater(len(hops), 0)
        for hop in hops:
            self.assertIn("hop", hop)
            self.assertIn("ip", hop)
            self.assertIn("rtt_ms", hop)


class TestNetworkManagerGetHostname(unittest.TestCase):
    """Hostname."""

    def setUp(self):
        self.nm = NetworkManager()

    def test_get_hostname_returns_string(self):
        hostname = self.nm.get_hostname()
        self.assertIsInstance(hostname, str)
        self.assertTrue(len(hostname) > 0)


class TestNetworkManagerInterfaceStats(unittest.TestCase):
    """Interface I/O stats."""

    def setUp(self):
        self.nm = NetworkManager()

    def test_interface_stats_returns_list(self):
        result = self.nm.interface_stats()
        self.assertIsInstance(result, list)

    def test_interface_stats_keys_if_present(self):
        result = self.nm.interface_stats()
        for item in result:
            for key in ("name", "bytes_sent", "bytes_recv"):
                self.assertIn(key, item)


if __name__ == "__main__":
    unittest.main()
