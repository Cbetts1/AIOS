"""Tests for security hardening, web API, plugin hot-reload, and shell script mode.

Covers:
- IPC channel name sanitisation
- Secret namespace sanitisation
- Web command (no-Flask fallback path)
- Plugin reload CLI subcommand
- Shell --script flag
"""

import io
import json
import os
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ============================================================
# IPC channel name sanitisation
# ============================================================

class TestIPCChannelSanitisation(unittest.TestCase):
    """IPC channel names must be safe filesystem names."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        from aura_os.kernel.ipc import IPCChannel
        self.ipc = IPCChannel(base_dir=self.tmpdir)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_empty_channel_raises(self):
        with self.assertRaises(ValueError):
            self.ipc._channel_path("")

    def test_null_byte_raises(self):
        with self.assertRaises(ValueError):
            self.ipc._channel_path("chan\x00el")

    def test_dot_only_raises(self):
        with self.assertRaises(ValueError):
            self.ipc._channel_path(".")

    def test_dotdot_raises(self):
        with self.assertRaises(ValueError):
            self.ipc._channel_path("..")

    def test_leading_dot_raises(self):
        with self.assertRaises(ValueError):
            self.ipc._channel_path(".hidden")

    def test_control_char_raises(self):
        with self.assertRaises(ValueError):
            self.ipc._channel_path("chan\x01el")

    def test_valid_channel_name_accepted(self):
        path = self.ipc._channel_path("my_channel")
        self.assertTrue(path.endswith("my_channel.jsonl"))

    def test_send_receive_valid_channel(self):
        self.ipc.send("valid_ch", {"msg": "hello"})
        messages = self.ipc.receive("valid_ch")
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0]["data"]["msg"], "hello")


# ============================================================
# Secret namespace sanitisation
# ============================================================

class TestSecretNamespaceSanitisation(unittest.TestCase):
    """Secret namespaces must be sanitised to safe filenames."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        from aura_os.kernel.secrets import SecretStore
        self.store = SecretStore(base_dir=self.tmpdir, passphrase="testpass")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_empty_namespace_raises(self):
        with self.assertRaises(ValueError):
            self.store._store_path("")

    def test_null_byte_namespace_raises(self):
        with self.assertRaises(ValueError):
            self.store._store_path("ns\x00pace")

    def test_slash_is_sanitised_not_raises(self):
        # Slashes are replaced by underscores — must not raise
        path = self.store._store_path("my/namespace")
        self.assertTrue(path.endswith(".json"))
        self.assertNotIn("/my/namespace", path)

    def test_dotdot_sanitised(self):
        path = self.store._store_path("../../etc")
        self.assertTrue(path.endswith(".json"))
        # Must not escape the secrets dir
        self.assertTrue(path.startswith(self.tmpdir))

    def test_valid_namespace_accepted(self):
        path = self.store._store_path("my-namespace_1")
        self.assertTrue(path.endswith("my-namespace_1.json"))

    def test_set_and_get_with_special_namespace(self):
        # Verify the sanitised namespace round-trips correctly
        self.store.set_secret("key1", "val1", namespace="my/app")
        # The same sanitised namespace must be used for retrieval
        val = self.store.get_secret("key1", namespace="my/app")
        self.assertEqual(val, "val1")


# ============================================================
# Web command
# ============================================================

class TestWebCommand(unittest.TestCase):
    """WebCommand registers and starts a server."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_web_command_is_in_cli(self):
        from aura_os.engine.cli import build_parser
        parser = build_parser()
        args = parser.parse_args(["web"])
        self.assertEqual(args.command, "web")

    def test_web_command_default_port(self):
        from aura_os.engine.cli import build_parser
        args = build_parser().parse_args(["web"])
        self.assertEqual(args.port, 7070)

    def test_web_command_custom_port(self):
        from aura_os.engine.cli import build_parser
        args = build_parser().parse_args(["web", "--port", "8080"])
        self.assertEqual(args.port, 8080)

    def test_web_server_stdlib_starts_in_background(self):
        """WebServer starts without Flask on a random port."""
        from aura_os.web import WebServer

        eal = MagicMock()
        eal.get_env_info.return_value = {"platform": "test"}

        # Find a free port
        import socket
        s = socket.socket()
        s.bind(("127.0.0.1", 0))
        free_port = s.getsockname()[1]
        s.close()

        server = WebServer(eal, host="127.0.0.1", port=free_port)
        t = server.start(background=True)
        self.assertIsNotNone(t)  # thread was created
        time.sleep(0.3)
        self.assertTrue(t.is_alive(), "Server thread should be running")

    def test_web_server_get_status_helper(self):
        from aura_os.web import _get_status

        eal = MagicMock()
        eal.get_env_info.return_value = {"platform": "test", "foo": "bar"}
        result = _get_status(eal)
        self.assertEqual(result.get("platform"), "test")

    def test_web_server_get_log_returns_list(self):
        from aura_os.web import _get_log
        result = _get_log(lines=10)
        self.assertIsInstance(result, list)

    def test_web_server_get_ps_returns_list(self):
        from aura_os.web import _get_ps
        result = _get_ps()
        self.assertIsInstance(result, list)


# ============================================================
# Plugin hot-reload CLI
# ============================================================

class TestPluginReloadCLI(unittest.TestCase):
    """Plugin reload subcommand is registered in the CLI."""

    def test_reload_subcommand_parses(self):
        from aura_os.engine.cli import build_parser
        parser = build_parser()
        args = parser.parse_args(["plugin", "reload", "my_plugin"])
        self.assertEqual(args.command, "plugin")
        self.assertEqual(args.plugin_command, "reload")
        self.assertEqual(args.name, "my_plugin")

    def test_plugin_manager_reload_method_exists(self):
        from aura_os.kernel.plugins import PluginManager
        pm = PluginManager.__dict__
        self.assertIn("reload", pm)

    def test_plugin_reload_returns_false_for_missing(self):
        tmpdir = tempfile.mkdtemp()
        try:
            from aura_os.kernel.plugins import PluginManager
            pm = PluginManager(plugin_dir=tmpdir)
            pm.scan()
            result = pm.reload("nonexistent_plugin")
            self.assertFalse(result)
        finally:
            import shutil
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_plugin_reload_loads_newly_created_plugin(self):
        tmpdir = tempfile.mkdtemp()
        try:
            from aura_os.kernel.plugins import PluginManager
            pm = PluginManager(plugin_dir=tmpdir)

            # Scaffold a plugin
            plug_dir = pm.create_plugin("test_hot_reload", description="Test hot-reload")
            pm.scan()
            loaded = pm.load("test_hot_reload")
            self.assertTrue(loaded)

            # Unload it first then reload
            pm.unload("test_hot_reload")
            self.assertFalse(pm.is_loaded("test_hot_reload"))
            # Reload should re-load it
            result = pm.reload("test_hot_reload")
            self.assertTrue(result)
            self.assertTrue(pm.is_loaded("test_hot_reload"))
        finally:
            import shutil
            shutil.rmtree(tmpdir, ignore_errors=True)


# ============================================================
# Shell --script flag
# ============================================================

class TestShellScriptMode(unittest.TestCase):
    """Shell can execute commands from a script file."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_shell_subparser_has_script_option(self):
        from aura_os.engine.cli import build_parser
        parser = build_parser()
        args = parser.parse_args(["shell", "--script", "/tmp/test.aura"])
        self.assertEqual(args.command, "shell")
        self.assertEqual(args.script, "/tmp/test.aura")

    def test_shell_script_missing_file_returns_error(self):
        from aura_os.main import _run_shell

        eal = MagicMock()
        result = _run_shell(eal, script_file="/nonexistent/path/script.aura")
        self.assertEqual(result, 1)

    def test_shell_script_executes_echo_command(self):
        """Script file with echo commands executes without raising."""
        script_path = os.path.join(self.tmpdir, "test.aura")
        with open(script_path, "w") as fh:
            fh.write("# A comment\n")
            fh.write("echo hello from script\n")
            fh.write("echo world\n")

        from aura_os.main import _run_shell

        eal = MagicMock()
        eal.platform = "linux"

        # Should execute without error
        try:
            _run_shell(eal, script_file=script_path)
        except SystemExit:
            pass  # Some commands may exit; that's acceptable

    def test_shell_script_empty_file_ok(self):
        script_path = os.path.join(self.tmpdir, "empty.aura")
        with open(script_path, "w") as fh:
            fh.write("")

        from aura_os.main import _run_shell

        eal = MagicMock()
        result = _run_shell(eal, script_file=script_path)
        self.assertIsNone(result)  # function completes without returning an error code


if __name__ == "__main__":
    unittest.main()
