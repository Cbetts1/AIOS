"""Tests for modern standalone OS features: users, net, init, VirtualFHS."""

import os
import tempfile

import pytest


# ---------------------------------------------------------------------------
# TestUserManager
# ---------------------------------------------------------------------------

class TestUserManager:
    """Tests for aura_os.users.UserManager."""

    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        from aura_os.users.manager import UserManager
        self.um = UserManager(base_dir=self.tmpdir)

    def test_add_and_exists(self):
        self.um.add_user("alice", "secret")
        assert self.um.user_exists("alice")

    def test_add_duplicate_raises(self):
        self.um.add_user("bob", "pass1")
        with pytest.raises(ValueError, match="already exists"):
            self.um.add_user("bob", "pass2")

    def test_remove_user(self):
        self.um.add_user("carol", "pw")
        self.um.remove_user("carol")
        assert not self.um.user_exists("carol")

    def test_remove_missing_raises(self):
        with pytest.raises(KeyError):
            self.um.remove_user("nobody")

    def test_list_users(self):
        self.um.add_user("dave", "pw", role="root")
        self.um.add_user("eve", "pw", role="guest")
        users = self.um.list_users()
        names = [u["username"] for u in users]
        assert "dave" in names
        assert "eve" in names

    def test_list_users_no_password_hash(self):
        self.um.add_user("frank", "secret")
        for u in self.um.list_users():
            assert "password_hash" not in u

    def test_authenticate_correct(self):
        self.um.add_user("grace", "mypassword")
        assert self.um.authenticate("grace", "mypassword")

    def test_authenticate_wrong(self):
        self.um.add_user("heidi", "rightpw")
        assert not self.um.authenticate("heidi", "wrongpw")

    def test_authenticate_missing_user(self):
        assert not self.um.authenticate("noone", "pw")

    def test_set_password(self):
        self.um.add_user("ivan", "old")
        ok = self.um.set_password("ivan", "old", "new")
        assert ok
        assert self.um.authenticate("ivan", "new")
        assert not self.um.authenticate("ivan", "old")

    def test_set_password_wrong_old(self):
        self.um.add_user("judy", "correct")
        ok = self.um.set_password("judy", "wrong", "new")
        assert not ok

    def test_set_password_missing_user(self):
        with pytest.raises(KeyError):
            self.um.set_password("ghost", "old", "new")

    def test_get_user(self):
        self.um.add_user("karl", "pw", role="root")
        record = self.um.get_user("karl")
        assert record is not None
        assert record["username"] == "karl"
        assert record["role"] == "root"
        assert "password_hash" in record

    def test_get_user_missing(self):
        assert self.um.get_user("missing") is None

    def test_invalid_username_raises(self):
        with pytest.raises(ValueError, match="Invalid username"):
            self.um.add_user("bad name!", "pw")

    def test_username_too_long_raises(self):
        with pytest.raises(ValueError):
            self.um.add_user("a" * 33, "pw")

    def test_invalid_role_raises(self):
        with pytest.raises(ValueError, match="Invalid role"):
            self.um.add_user("valid", "pw", role="superadmin")

    def test_valid_roles(self):
        for i, role in enumerate(["root", "user", "guest"]):
            self.um.add_user(f"u{i}", "pw", role=role)
            assert self.um.user_exists(f"u{i}")

    def test_get_current_user_returns_string(self):
        result = self.um.get_current_user()
        assert isinstance(result, str)
        assert len(result) > 0


# ---------------------------------------------------------------------------
# TestNetworkManager
# ---------------------------------------------------------------------------

class TestNetworkManager:
    """Tests for aura_os.net.NetworkManager."""

    def setup_method(self):
        from aura_os.net.manager import NetworkManager
        self.nm = NetworkManager()

    def test_list_interfaces_returns_list(self):
        ifaces = self.nm.list_interfaces()
        assert isinstance(ifaces, list)

    def test_list_interfaces_have_expected_keys(self):
        ifaces = self.nm.list_interfaces()
        for iface in ifaces:
            assert "name" in iface
            assert "addresses" in iface
            assert "is_up" in iface
            assert "is_loopback" in iface

    def test_check_connectivity_returns_bool(self):
        result = self.nm.check_connectivity()
        assert isinstance(result, bool)

    def test_dns_lookup_localhost(self):
        addresses = self.nm.dns_lookup("localhost")
        assert isinstance(addresses, list)

    def test_dns_lookup_invalid(self):
        addresses = self.nm.dns_lookup("this.hostname.does.not.exist.invalid")
        assert isinstance(addresses, list)
        assert addresses == []

    def test_get_hostname_returns_str(self):
        hostname = self.nm.get_hostname()
        assert isinstance(hostname, str)
        assert len(hostname) > 0

    def test_ping_returns_dict_with_required_keys(self):
        result = self.nm.ping("localhost", count=1, timeout=2)
        assert isinstance(result, dict)
        for key in ("host", "packets_sent", "packets_received", "avg_ms", "success"):
            assert key in result

    def test_ping_host_field(self):
        result = self.nm.ping("127.0.0.1", count=1, timeout=2)
        assert result["host"] == "127.0.0.1"

    def test_ping_packets_sent(self):
        result = self.nm.ping("localhost", count=2, timeout=2)
        assert result["packets_sent"] == 2

    def test_get_default_gateway_returns_str_or_none(self):
        gw = self.nm.get_default_gateway()
        assert gw is None or isinstance(gw, str)


# ---------------------------------------------------------------------------
# TestInitManager
# ---------------------------------------------------------------------------

class TestInitManager:
    """Tests for aura_os.init.InitManager."""

    def setup_method(self):
        from aura_os.init.sequence import InitManager
        self.im = InitManager()

    def test_register_and_status(self):
        self.im.register("svc1", start_fn=lambda: None, description="Test service")
        statuses = self.im.status()
        names = [s["name"] for s in statuses]
        assert "svc1" in names

    def test_boot_returns_dict_with_expected_keys(self):
        self.im.register("a", start_fn=lambda: None)
        result = self.im.boot()
        assert "ok" in result
        assert "failed" in result
        assert "skipped" in result

    def test_boot_ok_unit(self):
        called = []
        self.im.register("unit_ok", start_fn=lambda: called.append(True))
        result = self.im.boot()
        assert "unit_ok" in result["ok"]
        assert called

    def test_boot_failed_unit(self):
        def bad():
            raise RuntimeError("boom")

        self.im.register("unit_fail", start_fn=bad)
        result = self.im.boot()
        assert "unit_fail" in result["failed"]

    def test_boot_skipped_on_required_failure(self):
        def bad():
            raise RuntimeError("fail")

        self.im.register("dep", start_fn=bad)
        self.im.register("dependent", start_fn=lambda: None, requires=["dep"])
        result = self.im.boot()
        assert "dep" in result["failed"]
        assert "dependent" in result["skipped"]

    def test_dependency_ordering(self):
        order = []
        self.im.register("second", start_fn=lambda: order.append("second"), after=["first"])
        self.im.register("first", start_fn=lambda: order.append("first"))
        self.im.boot()
        assert order.index("first") < order.index("second")

    def test_shutdown_calls_stop_fn(self):
        stopped = []
        self.im.register("svc", start_fn=lambda: None, stop_fn=lambda: stopped.append(True))
        self.im.boot()
        self.im.shutdown()
        assert stopped

    def test_shutdown_no_stop_fn(self):
        self.im.register("nostopper", start_fn=lambda: None)
        self.im.boot()
        self.im.shutdown()

    def test_status_contains_state(self):
        self.im.register("x", start_fn=lambda: None)
        self.im.boot()
        for entry in self.im.status():
            assert "state" in entry
            assert "name" in entry
            assert "description" in entry
            assert "error" in entry

    def test_empty_boot(self):
        result = self.im.boot()
        assert result == {"ok": [], "failed": [], "skipped": []}


# ---------------------------------------------------------------------------
# TestVirtualFHS
# ---------------------------------------------------------------------------

class TestVirtualFHS:
    """Tests for aura_os.fs.fhs.VirtualFHS."""

    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        from aura_os.fs.fhs import VirtualFHS
        self.fhs = VirtualFHS(base_dir=self.tmpdir)

    def test_standard_dirs_created(self):
        for d in ("etc", "var", "var/log", "home", "tmp", "bin", "usr", "usr/bin"):
            assert self.fhs.exists(d), f"Expected directory '{d}' to exist"

    def test_etc_hostname_exists(self):
        assert self.fhs.exists("etc/hostname")

    def test_etc_os_release_exists(self):
        assert self.fhs.exists("etc/os-release")

    def test_etc_hosts_exists(self):
        assert self.fhs.exists("etc/hosts")

    def test_etc_fstab_exists(self):
        assert self.fhs.exists("etc/fstab")

    def test_etc_aura_version_exists(self):
        assert self.fhs.exists("etc/aura/version")

    def test_etc_shells_exists(self):
        assert self.fhs.exists("etc/shells")

    def test_read_etc_hostname(self):
        content = self.fhs.read_etc("hostname")
        assert isinstance(content, str)
        assert len(content.strip()) > 0

    def test_read_etc_os_release_contains_aura(self):
        content = self.fhs.read_etc("os-release")
        assert "AURA" in content

    def test_read_etc_hosts_contains_localhost(self):
        content = self.fhs.read_etc("hosts")
        assert "localhost" in content

    def test_write_etc(self):
        self.fhs.write_etc("myconfig", "key=value\n")
        assert self.fhs.read_etc("myconfig") == "key=value\n"

    def test_etc_aura_version_matches_package(self):
        from aura_os import __version__
        content = self.fhs.read_etc("aura/version")
        assert content.strip() == __version__

    def test_reinit_does_not_overwrite_existing(self):
        self.fhs.write_etc("hostname", "custom-host")
        from aura_os.fs.fhs import VirtualFHS
        fhs2 = VirtualFHS(base_dir=self.tmpdir)
        assert fhs2.read_etc("hostname") == "custom-host"
