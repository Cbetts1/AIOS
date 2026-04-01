"""Tests for the new kernel subsystems added to AURA OS.

Covers: NetworkManager, EventBus, NotificationManager, CronScheduler,
        ClipboardManager, PluginManager, SecretStore, and their CLI commands.
"""

import json
import os
import shutil
import sys
import tempfile
import threading
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from aura_os.engine.cli import build_parser
from aura_os.engine.router import CommandRouter


# ======================================================================
# Test NetworkManager
# ======================================================================

class TestNetworkManager(unittest.TestCase):
    """Tests for aura_os.kernel.network.NetworkManager."""

    def setUp(self):
        from aura_os.kernel.network import NetworkManager
        self.net = NetworkManager(timeout=5)

    def test_ping_localhost(self):
        """Pinging localhost should succeed."""
        result = self.net.ping("127.0.0.1", 80, timeout=2)
        # Port 80 may not be open, but the dict should have expected keys
        self.assertIn("reachable", result)
        self.assertIn("host", result)
        self.assertEqual(result["host"], "127.0.0.1")

    def test_ping_unreachable(self):
        """Pinging a non-routable address should fail gracefully."""
        result = self.net.ping("192.0.2.1", 1, timeout=1)
        self.assertFalse(result["reachable"])
        self.assertIsNone(result["latency_ms"])

    def test_dns_lookup_localhost(self):
        result = self.net.dns_lookup("localhost")
        self.assertEqual(result["hostname"], "localhost")
        self.assertIsInstance(result["addresses"], list)

    def test_dns_lookup_invalid(self):
        result = self.net.dns_lookup("this.host.does.not.exist.invalid")
        self.assertEqual(result["addresses"], [])
        self.assertIn("error", result)

    def test_dns_cache(self):
        """Second lookup should be cached."""
        self.net.dns_lookup("localhost")
        result = self.net.dns_lookup("localhost")
        self.assertTrue(result.get("cached", False))

    def test_reverse_dns(self):
        result = self.net.reverse_dns("127.0.0.1")
        self.assertIn("ip", result)
        self.assertEqual(result["ip"], "127.0.0.1")

    def test_interfaces(self):
        info = self.net.interfaces()
        self.assertIn("hostname", info)
        self.assertIn("local_ip", info)
        self.assertIsInstance(info["hostname"], str)

    def test_port_scan_localhost(self):
        results = self.net.port_scan("127.0.0.1", ports=[1, 2, 3],
                                     timeout=0.5)
        self.assertEqual(len(results), 3)
        for r in results:
            self.assertIn("port", r)
            self.assertIn("open", r)

    def test_guess_service(self):
        from aura_os.kernel.network import NetworkManager
        self.assertEqual(NetworkManager._guess_service(80), "http")
        self.assertEqual(NetworkManager._guess_service(443), "https")
        self.assertIsNone(NetworkManager._guess_service(99999))

    def test_http_get_invalid_url(self):
        result = self.net.http_get("http://192.0.2.1:1/not-real", timeout=1)
        self.assertIsNotNone(result["error"])

    def test_http_post_invalid_url(self):
        result = self.net.http_post("http://192.0.2.1:1/not-real",
                                    data={"a": 1}, timeout=1)
        self.assertIsNotNone(result["error"])

    def test_download_invalid(self):
        dest = os.path.join(tempfile.mkdtemp(), "file.bin")
        result = self.net.download("http://192.0.2.1:1/nope", dest, timeout=1)
        self.assertFalse(result["ok"])
        shutil.rmtree(os.path.dirname(dest), ignore_errors=True)


# ======================================================================
# Test EventBus
# ======================================================================

class TestEventBus(unittest.TestCase):
    """Tests for aura_os.kernel.events.EventBus."""

    def setUp(self):
        from aura_os.kernel.events import EventBus
        self.bus = EventBus()

    def test_subscribe_and_emit(self):
        received = []
        self.bus.subscribe("test.topic", lambda e: received.append(e))
        self.bus.emit("test.topic", {"key": "value"})
        self.assertEqual(len(received), 1)
        self.assertEqual(received[0].topic, "test.topic")
        self.assertEqual(received[0].data, {"key": "value"})

    def test_wildcard_subscribe(self):
        received = []
        self.bus.subscribe("fs.*", lambda e: received.append(e))
        self.bus.emit("fs.write", {"file": "a.txt"})
        self.bus.emit("fs.read", {"file": "b.txt"})
        self.bus.emit("net.ping", {})  # should NOT match
        self.assertEqual(len(received), 2)

    def test_unsubscribe(self):
        received = []
        cb = lambda e: received.append(e)
        self.bus.subscribe("x", cb)
        self.bus.emit("x")
        self.assertEqual(len(received), 1)
        self.bus.unsubscribe("x", cb)
        self.bus.emit("x")
        self.assertEqual(len(received), 1)  # no new events

    def test_emit_async(self):
        received = []
        self.bus.subscribe("async.test",
                           lambda e: received.append(e.topic))
        self.bus.emit_async("async.test")
        time.sleep(0.2)
        self.assertEqual(received, ["async.test"])

    def test_history(self):
        self.bus.emit("a", {"n": 1})
        self.bus.emit("b", {"n": 2})
        h = self.bus.history()
        self.assertEqual(len(h), 2)
        self.assertEqual(h[0]["topic"], "a")

    def test_history_filter(self):
        self.bus.emit("a.x")
        self.bus.emit("b.y")
        h = self.bus.history(topic="a.x")
        self.assertEqual(len(h), 1)

    def test_subscriber_error_does_not_crash(self):
        """A subscriber that raises should not affect other subscribers."""
        ok_received = []
        self.bus.subscribe("err", lambda e: 1 / 0)
        self.bus.subscribe("err", lambda e: ok_received.append(True))
        self.bus.emit("err")
        self.assertEqual(len(ok_received), 1)

    def test_match_exact(self):
        from aura_os.kernel.events import EventBus
        self.assertTrue(EventBus._match("fs.write", "fs.write"))
        self.assertFalse(EventBus._match("fs.write", "fs.read"))

    def test_match_wildcard(self):
        from aura_os.kernel.events import EventBus
        self.assertTrue(EventBus._match("fs.*", "fs.write"))
        self.assertTrue(EventBus._match("fs.*", "fs.read"))
        self.assertFalse(EventBus._match("fs.*", "net.ping"))


# ======================================================================
# Test NotificationManager
# ======================================================================

class TestNotificationManager(unittest.TestCase):
    """Tests for aura_os.kernel.events.NotificationManager."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        from aura_os.kernel.events import NotificationManager
        self.nm = NotificationManager(base_dir=self.tmpdir)

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_send_and_list(self):
        self.nm.send("Test", "Body text", level="info")
        items = self.nm.list_all()
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["title"], "Test")
        self.assertFalse(items[0]["read"])

    def test_mark_read(self):
        n = self.nm.send("Hello")
        self.assertTrue(self.nm.mark_read(n["id"]))
        items = self.nm.list_all()
        self.assertTrue(items[0]["read"])

    def test_mark_read_nonexistent(self):
        self.assertFalse(self.nm.mark_read("fake-id"))

    def test_unread_count(self):
        self.nm.send("A")
        self.nm.send("B")
        self.assertEqual(self.nm.unread_count(), 2)
        n = self.nm.list_all()[0]
        self.nm.mark_read(n["id"])
        self.assertEqual(self.nm.unread_count(), 1)

    def test_clear(self):
        self.nm.send("X")
        self.nm.clear()
        self.assertEqual(len(self.nm.list_all()), 0)

    def test_unread_only_filter(self):
        n = self.nm.send("Read me")
        self.nm.send("Keep me")
        self.nm.mark_read(n["id"])
        unread = self.nm.list_all(unread_only=True)
        self.assertEqual(len(unread), 1)
        self.assertEqual(unread[0]["title"], "Keep me")

    def test_notification_levels(self):
        for level in ("info", "warn", "error", "success"):
            n = self.nm.send(f"Level-{level}", level=level)
            self.assertEqual(n["level"], level)


# ======================================================================
# Test CronScheduler
# ======================================================================

class TestCronScheduler(unittest.TestCase):
    """Tests for aura_os.kernel.cron.CronScheduler."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        from aura_os.kernel.cron import CronScheduler
        self.cron = CronScheduler(base_dir=self.tmpdir)

    def tearDown(self):
        self.cron.stop()
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_add_job(self):
        job = self.cron.add_job("test", "every 5m", "echo hello")
        self.assertEqual(job.name, "test")
        self.assertEqual(job.schedule, "every 5m")
        self.assertTrue(job.enabled)

    def test_list_jobs(self):
        self.cron.add_job("a", "every 1h", "cmd1")
        self.cron.add_job("b", "every 30s", "cmd2")
        jobs = self.cron.list_jobs()
        self.assertEqual(len(jobs), 2)

    def test_remove_job(self):
        job = self.cron.add_job("rm-me", "every 10s", "true")
        self.assertTrue(self.cron.remove_job(job.id))
        self.assertEqual(len(self.cron.list_jobs()), 0)

    def test_remove_nonexistent(self):
        self.assertFalse(self.cron.remove_job("fake-id"))

    def test_enable_disable(self):
        job = self.cron.add_job("toggle", "every 1m", "true")
        self.assertTrue(self.cron.disable_job(job.id))
        jobs = self.cron.list_jobs()
        self.assertFalse(jobs[0]["enabled"])
        self.assertTrue(self.cron.enable_job(job.id))
        jobs = self.cron.list_jobs()
        self.assertTrue(jobs[0]["enabled"])

    def test_parse_interval_seconds(self):
        from aura_os.kernel.cron import CronScheduler
        self.assertEqual(CronScheduler._parse_interval("every 30s"), 30.0)
        self.assertEqual(CronScheduler._parse_interval("every 5m"), 300.0)
        self.assertEqual(CronScheduler._parse_interval("every 2h"), 7200.0)
        self.assertEqual(CronScheduler._parse_interval("every 1d"), 86400.0)

    def test_parse_interval_invalid(self):
        from aura_os.kernel.cron import CronScheduler
        self.assertIsNone(CronScheduler._parse_interval("not a schedule"))
        self.assertIsNone(CronScheduler._parse_interval("every xyz"))

    def test_persistence(self):
        """Jobs should persist to disk and reload."""
        self.cron.add_job("persist", "every 10m", "echo ok")
        from aura_os.kernel.cron import CronScheduler
        cron2 = CronScheduler(base_dir=self.tmpdir)
        jobs = cron2.list_jobs()
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]["name"], "persist")

    def test_start_stop(self):
        """Start and stop the scheduler loop without errors."""
        self.cron.start()
        time.sleep(0.3)
        self.assertTrue(self.cron._running)
        self.cron.stop()
        self.assertFalse(self.cron._running)


# ======================================================================
# Test ClipboardManager
# ======================================================================

class TestClipboardManager(unittest.TestCase):
    """Tests for aura_os.kernel.clipboard.ClipboardManager."""

    def setUp(self):
        from aura_os.kernel.clipboard import ClipboardManager
        self.clip = ClipboardManager(max_history=20)
        # Force memory backend for test portability
        self.clip._backend = "memory"

    def test_copy_and_paste(self):
        result = self.clip.copy("hello world")
        self.assertTrue(result["ok"])
        self.assertEqual(result["length"], 11)
        paste = self.clip.paste()
        self.assertTrue(paste["ok"])
        self.assertEqual(paste["text"], "hello world")

    def test_history(self):
        self.clip.copy("first")
        self.clip.copy("second")
        self.clip.copy("third")
        h = self.clip.history(limit=2)
        self.assertEqual(len(h), 2)
        self.assertEqual(h, ["second", "third"])

    def test_clear_history(self):
        self.clip.copy("data")
        self.clip.clear_history()
        self.assertEqual(self.clip.history(), [])

    def test_info(self):
        self.clip.copy("x")
        info = self.clip.info()
        self.assertEqual(info["backend"], "memory")
        self.assertEqual(info["history_size"], 1)
        self.assertEqual(info["max_history"], 20)

    def test_max_history_limit(self):
        for i in range(30):
            self.clip.copy(f"item-{i}")
        self.assertEqual(len(self.clip.history(limit=100)), 20)

    def test_empty_paste(self):
        """Paste from empty clipboard returns empty string."""
        paste = self.clip.paste()
        self.assertTrue(paste["ok"])
        self.assertEqual(paste["text"], "")


# ======================================================================
# Test PluginManager
# ======================================================================

class TestPluginManager(unittest.TestCase):
    """Tests for aura_os.kernel.plugins.PluginManager."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        from aura_os.kernel.plugins import PluginManager
        self.pm = PluginManager(plugin_dir=self.tmpdir)

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _make_plugin(self, name, code="def activate(ctx): pass",
                     version="1.0.0", enabled=True):
        """Helper to create a plugin in the temp directory."""
        pdir = os.path.join(self.tmpdir, name)
        os.makedirs(pdir, exist_ok=True)
        manifest = {"name": name, "version": version, "enabled": enabled,
                     "description": f"Test plugin {name}",
                     "entry_point": "main.py"}
        with open(os.path.join(pdir, "plugin.json"), "w") as f:
            json.dump(manifest, f)
        with open(os.path.join(pdir, "main.py"), "w") as f:
            f.write(code)

    def test_scan_empty(self):
        plugins = self.pm.scan()
        self.assertEqual(plugins, [])

    def test_scan_finds_plugins(self):
        self._make_plugin("alpha")
        self._make_plugin("beta")
        plugins = self.pm.scan()
        self.assertEqual(len(plugins), 2)
        names = {p.name for p in plugins}
        self.assertEqual(names, {"alpha", "beta"})

    def test_load_plugin(self):
        self._make_plugin("loader-test",
                          code="LOADED = True\ndef activate(ctx): pass")
        self.pm.scan()
        self.assertTrue(self.pm.load("loader-test"))
        self.assertTrue(self.pm.is_loaded("loader-test"))

    def test_load_nonexistent(self):
        self.assertFalse(self.pm.load("no-such-plugin"))

    def test_unload_plugin(self):
        self._make_plugin("unloader-test")
        self.pm.scan()
        self.pm.load("unloader-test")
        self.assertTrue(self.pm.unload("unloader-test"))
        self.assertFalse(self.pm.is_loaded("unloader-test"))

    def test_unload_not_loaded(self):
        self.assertFalse(self.pm.unload("nope"))

    def test_reload_plugin(self):
        self._make_plugin("reload-test")
        self.pm.scan()
        self.pm.load("reload-test")
        self.assertTrue(self.pm.reload("reload-test"))

    def test_list_plugins(self):
        self._make_plugin("list-a")
        self._make_plugin("list-b")
        self.pm.scan()
        self.pm.load("list-a")
        plugins = self.pm.list_plugins()
        loaded_names = [p["name"] for p in plugins if p["loaded"]]
        self.assertIn("list-a", loaded_names)

    def test_create_plugin_scaffold(self):
        path = self.pm.create_plugin("new-plug", description="My plugin")
        self.assertTrue(os.path.isfile(os.path.join(path, "plugin.json")))
        self.assertTrue(os.path.isfile(os.path.join(path, "main.py")))

    def test_disabled_plugin_not_loaded(self):
        self._make_plugin("disabled-plug", enabled=False)
        self.pm.scan()
        self.assertFalse(self.pm.load("disabled-plug"))

    def test_get_plugin_module(self):
        self._make_plugin("mod-test",
                          code="VALUE = 42\ndef activate(ctx): pass")
        self.pm.scan()
        self.pm.load("mod-test")
        mod = self.pm.get_plugin_module("mod-test")
        self.assertEqual(mod.VALUE, 42)

    def test_deactivate_called(self):
        code = (
            "deactivated = False\n"
            "def activate(ctx): pass\n"
            "def deactivate(ctx):\n"
            "    global deactivated\n"
            "    deactivated = True\n"
        )
        self._make_plugin("deact-test", code=code)
        self.pm.scan()
        self.pm.load("deact-test")
        mod = self.pm.get_plugin_module("deact-test")
        self.assertFalse(mod.deactivated)
        self.pm.unload("deact-test")
        # After unload the module ref still exists but deactivate was called
        self.assertTrue(mod.deactivated)


# ======================================================================
# Test SecretStore
# ======================================================================

class TestSecretStore(unittest.TestCase):
    """Tests for aura_os.kernel.secrets.SecretStore."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        from aura_os.kernel.secrets import SecretStore
        self.ss = SecretStore(base_dir=self.tmpdir, passphrase="test-key")

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_set_and_get(self):
        self.ss.set_secret("api_key", "sk-12345")
        val = self.ss.get_secret("api_key")
        self.assertEqual(val, "sk-12345")

    def test_get_nonexistent(self):
        self.assertIsNone(self.ss.get_secret("no-such-key"))

    def test_delete(self):
        self.ss.set_secret("to_delete", "value")
        self.assertTrue(self.ss.delete_secret("to_delete"))
        self.assertIsNone(self.ss.get_secret("to_delete"))

    def test_delete_nonexistent(self):
        self.assertFalse(self.ss.delete_secret("nope"))

    def test_list_secrets(self):
        self.ss.set_secret("key1", "v1")
        self.ss.set_secret("key2", "v2")
        keys = self.ss.list_secrets()
        self.assertEqual(len(keys), 2)
        key_names = {k["key"] for k in keys}
        self.assertEqual(key_names, {"key1", "key2"})

    def test_namespaces(self):
        self.ss.set_secret("a", "1", namespace="prod")
        self.ss.set_secret("b", "2", namespace="dev")
        ns = self.ss.list_namespaces()
        self.assertIn("prod", ns)
        self.assertIn("dev", ns)

    def test_namespace_isolation(self):
        self.ss.set_secret("key", "prod-val", namespace="prod")
        self.ss.set_secret("key", "dev-val", namespace="dev")
        self.assertEqual(self.ss.get_secret("key", namespace="prod"),
                         "prod-val")
        self.assertEqual(self.ss.get_secret("key", namespace="dev"),
                         "dev-val")

    def test_encryption_at_rest(self):
        """Stored value should be encrypted (not plaintext)."""
        self.ss.set_secret("secret", "my-password")
        store_path = os.path.join(self.tmpdir, "default.json")
        with open(store_path, "r") as f:
            data = json.load(f)
        stored_value = data["secret"]["value"]
        self.assertNotEqual(stored_value, "my-password")

    def test_update_secret(self):
        self.ss.set_secret("k", "old")
        self.ss.set_secret("k", "new")
        self.assertEqual(self.ss.get_secret("k"), "new")

    def test_unicode_secret(self):
        self.ss.set_secret("emoji", "🔑🔐🗝️")
        self.assertEqual(self.ss.get_secret("emoji"), "🔑🔐🗝️")

    def test_long_secret(self):
        long_val = "x" * 10000
        self.ss.set_secret("long", long_val)
        self.assertEqual(self.ss.get_secret("long"), long_val)

    def test_file_permissions(self):
        """Secret files should be owner-readable only (0o600)."""
        self.ss.set_secret("perm", "test")
        store_path = os.path.join(self.tmpdir, "default.json")
        stat = os.stat(store_path)
        mode = stat.st_mode & 0o777
        self.assertEqual(mode, 0o600)


# ======================================================================
# Test CLI Parser for new commands
# ======================================================================

class TestNewCLICommands(unittest.TestCase):
    """Verify that the new CLI subcommands parse correctly."""

    def setUp(self):
        self.parser = build_parser()

    def _parse(self, argv):
        return self.parser.parse_args(argv)

    # --- net ---
    def test_net_ping(self):
        args = self._parse(["net", "ping", "8.8.8.8"])
        self.assertEqual(args.command, "net")
        self.assertEqual(args.net_command, "ping")
        self.assertEqual(args.host, "8.8.8.8")

    def test_net_dns(self):
        args = self._parse(["net", "dns", "example.com"])
        self.assertEqual(args.net_command, "dns")
        self.assertEqual(args.hostname, "example.com")

    def test_net_download(self):
        args = self._parse(["net", "download", "http://x.com/f", "/tmp/f"])
        self.assertEqual(args.net_command, "download")

    def test_net_ifconfig(self):
        args = self._parse(["net", "ifconfig"])
        self.assertEqual(args.net_command, "ifconfig")

    # --- notify ---
    def test_notify_send(self):
        args = self._parse(["notify", "send", "Hello",
                            "--body", "World", "--level", "warn"])
        self.assertEqual(args.command, "notify")
        self.assertEqual(args.notify_command, "send")
        self.assertEqual(args.title, "Hello")
        self.assertEqual(args.body, "World")
        self.assertEqual(args.level, "warn")

    def test_notify_list_unread(self):
        args = self._parse(["notify", "list", "--unread"])
        self.assertTrue(args.unread)

    def test_notify_clear(self):
        args = self._parse(["notify", "clear"])
        self.assertEqual(args.notify_command, "clear")

    # --- cron ---
    def test_cron_add(self):
        args = self._parse(["cron", "add", "backup",
                            "--schedule", "every 1h", "--cmd", "tar czf"])
        self.assertEqual(args.command, "cron")
        self.assertEqual(args.cron_command, "add")
        self.assertEqual(args.name, "backup")

    def test_cron_list(self):
        args = self._parse(["cron", "list"])
        self.assertEqual(args.cron_command, "list")

    def test_cron_remove(self):
        args = self._parse(["cron", "remove", "cron-1"])
        self.assertEqual(args.cron_command, "remove")
        self.assertEqual(args.id, "cron-1")

    # --- clip ---
    def test_clip_copy(self):
        args = self._parse(["clip", "copy", "hello"])
        self.assertEqual(args.command, "clip")
        self.assertEqual(args.clip_command, "copy")
        self.assertEqual(args.text, "hello")

    def test_clip_paste(self):
        args = self._parse(["clip", "paste"])
        self.assertEqual(args.clip_command, "paste")

    def test_clip_history(self):
        args = self._parse(["clip", "history", "-n", "5"])
        self.assertEqual(args.limit, 5)

    # --- plugin ---
    def test_plugin_scan(self):
        args = self._parse(["plugin", "scan"])
        self.assertEqual(args.command, "plugin")
        self.assertEqual(args.plugin_command, "scan")

    def test_plugin_load(self):
        args = self._parse(["plugin", "load", "my-plugin"])
        self.assertEqual(args.plugin_command, "load")
        self.assertEqual(args.name, "my-plugin")

    def test_plugin_create(self):
        args = self._parse(["plugin", "create", "new-plug",
                            "--description", "test"])
        self.assertEqual(args.plugin_command, "create")
        self.assertEqual(args.description, "test")

    # --- secret ---
    def test_secret_set(self):
        args = self._parse(["secret", "set", "api_key", "sk-123",
                            "--namespace", "prod"])
        self.assertEqual(args.command, "secret")
        self.assertEqual(args.secret_command, "set")
        self.assertEqual(args.key, "api_key")
        self.assertEqual(args.value, "sk-123")
        self.assertEqual(args.namespace, "prod")

    def test_secret_get(self):
        args = self._parse(["secret", "get", "api_key"])
        self.assertEqual(args.secret_command, "get")
        self.assertEqual(args.namespace, "default")

    def test_secret_delete(self):
        args = self._parse(["secret", "delete", "old_key"])
        self.assertEqual(args.secret_command, "delete")

    def test_secret_list(self):
        args = self._parse(["secret", "list"])
        self.assertEqual(args.secret_command, "list")

    def test_secret_namespaces(self):
        args = self._parse(["secret", "namespaces"])
        self.assertEqual(args.secret_command, "namespaces")


# ======================================================================
# Test Router registration for new commands
# ======================================================================

class _StubEAL:
    platform = "linux"
    def get_env_info(self):
        return {"platform": "linux", "paths": {}, "binaries": {}, "system": {}}


class TestNewRouterRegistration(unittest.TestCase):
    """Verify all new commands are registered in the router."""

    def test_new_commands_registered(self):
        """Import main._build_router and check all new commands exist."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
        from aura_os.main import _build_router
        router = _build_router()
        new_commands = ["net", "notify", "cron", "clip", "plugin", "secret"]
        for cmd in new_commands:
            self.assertIn(cmd, router._handlers,
                          f"Command '{cmd}' not registered in router")


if __name__ == "__main__":
    unittest.main()
