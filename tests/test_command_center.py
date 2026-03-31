"""Tests for the Command Center, Aura persona, and session manager."""

import json
import os
import shutil
import tempfile
import unittest
from unittest.mock import patch, MagicMock


class TestAuraPersona(unittest.TestCase):
    """Tests for aura_os.ai.aura.AuraPersona."""

    def setUp(self):
        self._tmpdir = tempfile.mkdtemp()
        os.environ["AURA_HOME"] = self._tmpdir
        os.makedirs(os.path.join(self._tmpdir, "data"), exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def test_default_persona(self):
        from aura_os.ai.aura import AuraPersona
        p = AuraPersona()
        self.assertEqual(p.name, "Aura")
        self.assertEqual(p.mood, "ready")
        self.assertIn("system_status", p.capabilities)

    def test_greet(self):
        from aura_os.ai.aura import AuraPersona
        p = AuraPersona()
        greeting = p.greet()
        self.assertIn("Aura", greeting)

    def test_status_line(self):
        from aura_os.ai.aura import AuraPersona
        p = AuraPersona()
        line = p.status_line()
        self.assertIn("Aura", line)
        self.assertIn("ready", line)

    def test_build_system_prompt(self):
        from aura_os.ai.aura import AuraPersona
        p = AuraPersona()
        prompt = p.build_system_prompt()
        self.assertIn("Aura", prompt)
        self.assertIn("system_status", prompt)

    def test_build_system_prompt_extra_context(self):
        from aura_os.ai.aura import AuraPersona
        p = AuraPersona()
        prompt = p.build_system_prompt(extra_context="The user is on Linux.")
        self.assertIn("Linux", prompt)

    def test_save_and_load(self):
        from aura_os.ai.aura import AuraPersona
        p = AuraPersona(mood="happy")
        path = p.save()
        self.assertTrue(os.path.isfile(path))

        loaded = AuraPersona.load(path)
        self.assertEqual(loaded.name, "Aura")
        self.assertEqual(loaded.mood, "happy")

    def test_load_missing_returns_defaults(self):
        from aura_os.ai.aura import AuraPersona
        loaded = AuraPersona.load("/nonexistent/path.json")
        self.assertEqual(loaded.name, "Aura")

    def test_to_dict(self):
        from aura_os.ai.aura import AuraPersona
        p = AuraPersona()
        d = p.to_dict()
        self.assertIsInstance(d, dict)
        self.assertEqual(d["name"], "Aura")
        self.assertIn("capabilities", d)

    def test_save_creates_directory(self):
        from aura_os.ai.aura import AuraPersona
        p = AuraPersona()
        path = os.path.join(self._tmpdir, "nested", "deep", "persona.json")
        p.save(path)
        self.assertTrue(os.path.isfile(path))


class TestSession(unittest.TestCase):
    """Tests for aura_os.ai.session.Session."""

    def setUp(self):
        self._tmpdir = tempfile.mkdtemp()
        os.environ["AURA_HOME"] = self._tmpdir

    def tearDown(self):
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def test_create_session(self):
        from aura_os.ai.session import Session
        s = Session()
        self.assertIsNotNone(s.session_id)
        self.assertEqual(len(s.messages), 0)

    def test_add_messages(self):
        from aura_os.ai.session import Session
        s = Session()
        s.add_user_message("Hello")
        s.add_aura_message("Hi there!")
        self.assertEqual(len(s.messages), 2)
        self.assertEqual(s.messages[0].role, "user")
        self.assertEqual(s.messages[1].role, "aura")

    def test_get_history(self):
        from aura_os.ai.session import Session
        s = Session()
        for i in range(10):
            s.add_user_message(f"msg {i}")
        history = s.get_history(last_n=3)
        self.assertEqual(len(history), 3)
        self.assertEqual(history[0].content, "msg 7")

    def test_get_history_all(self):
        from aura_os.ai.session import Session
        s = Session()
        s.add_user_message("a")
        s.add_user_message("b")
        self.assertEqual(len(s.get_history()), 2)

    def test_clear(self):
        from aura_os.ai.session import Session
        s = Session()
        s.add_user_message("test")
        s.clear()
        self.assertEqual(len(s.messages), 0)

    def test_save_and_load(self):
        from aura_os.ai.session import Session
        s = Session()
        s.add_user_message("Hello Aura")
        s.add_aura_message("Hello!")
        path = s.save()

        loaded = Session.load(path)
        self.assertEqual(loaded.session_id, s.session_id)
        self.assertEqual(len(loaded.messages), 2)
        self.assertEqual(loaded.messages[0].content, "Hello Aura")

    def test_to_dict(self):
        from aura_os.ai.session import Session
        s = Session()
        s.add_user_message("test")
        d = s.to_dict()
        self.assertIn("session_id", d)
        self.assertIn("messages", d)
        self.assertEqual(len(d["messages"]), 1)

    def test_from_dict(self):
        from aura_os.ai.session import Session
        data = {
            "session_id": "abc123",
            "created_at": 1000.0,
            "messages": [
                {"role": "user", "content": "hi", "timestamp": 1000.0},
                {"role": "aura", "content": "hello", "timestamp": 1001.0},
            ],
            "metadata": {},
        }
        s = Session.from_dict(data)
        self.assertEqual(s.session_id, "abc123")
        self.assertEqual(len(s.messages), 2)


class TestSessionManager(unittest.TestCase):
    """Tests for aura_os.ai.session.SessionManager."""

    def setUp(self):
        self._tmpdir = tempfile.mkdtemp()
        os.environ["AURA_HOME"] = self._tmpdir

    def tearDown(self):
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def test_new_session(self):
        from aura_os.ai.session import SessionManager
        sm = SessionManager(os.path.join(self._tmpdir, "sessions"))
        session = sm.new_session()
        self.assertIsNotNone(session.session_id)

    def test_list_sessions(self):
        from aura_os.ai.session import SessionManager
        sm = SessionManager(os.path.join(self._tmpdir, "sessions"))
        sm.new_session()
        sm.new_session()
        ids = sm.list_sessions()
        self.assertEqual(len(ids), 2)

    def test_get_session(self):
        from aura_os.ai.session import SessionManager
        sm = SessionManager(os.path.join(self._tmpdir, "sessions"))
        s = sm.new_session()
        loaded = sm.get_session(s.session_id)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.session_id, s.session_id)

    def test_get_nonexistent_session(self):
        from aura_os.ai.session import SessionManager
        sm = SessionManager(os.path.join(self._tmpdir, "sessions"))
        self.assertIsNone(sm.get_session("nonexistent"))

    def test_delete_session(self):
        from aura_os.ai.session import SessionManager
        sm = SessionManager(os.path.join(self._tmpdir, "sessions"))
        s = sm.new_session()
        self.assertTrue(sm.delete_session(s.session_id))
        self.assertEqual(len(sm.list_sessions()), 0)

    def test_delete_nonexistent(self):
        from aura_os.ai.session import SessionManager
        sm = SessionManager(os.path.join(self._tmpdir, "sessions"))
        self.assertFalse(sm.delete_session("nope"))

    def test_export_session(self):
        from aura_os.ai.session import SessionManager
        sm = SessionManager(os.path.join(self._tmpdir, "sessions"))
        s = sm.new_session()
        s.add_user_message("test export")
        s.save()
        data = sm.export_session(s.session_id)
        self.assertIsNotNone(data)
        self.assertIn("messages", data)

    def test_export_nonexistent(self):
        from aura_os.ai.session import SessionManager
        sm = SessionManager(os.path.join(self._tmpdir, "sessions"))
        self.assertIsNone(sm.export_session("missing"))


class TestMessage(unittest.TestCase):
    """Tests for aura_os.ai.session.Message."""

    def test_to_dict(self):
        from aura_os.ai.session import Message
        m = Message(role="user", content="hello")
        d = m.to_dict()
        self.assertEqual(d["role"], "user")
        self.assertEqual(d["content"], "hello")

    def test_from_dict(self):
        from aura_os.ai.session import Message
        m = Message.from_dict({"role": "aura", "content": "hi", "timestamp": 42.0})
        self.assertEqual(m.role, "aura")
        self.assertEqual(m.timestamp, 42.0)


class TestCommandCenterDashboard(unittest.TestCase):
    """Tests for aura_os.command_center.dashboard.CommandCenter."""

    def setUp(self):
        self._tmpdir = tempfile.mkdtemp()
        os.environ["AURA_HOME"] = self._tmpdir
        os.makedirs(os.path.join(self._tmpdir, "data"), exist_ok=True)
        os.makedirs(os.path.join(self._tmpdir, "models"), exist_ok=True)
        os.makedirs(os.path.join(self._tmpdir, "services"), exist_ok=True)
        os.makedirs(os.path.join(self._tmpdir, "logs"), exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def test_render_returns_string(self):
        from aura_os.command_center.dashboard import CommandCenter
        eal = MagicMock()
        cc = CommandCenter(eal)
        result = cc.render()
        self.assertIsInstance(result, str)
        self.assertIn("Command Center", result)

    def test_render_contains_panels(self):
        from aura_os.command_center.dashboard import CommandCenter
        eal = MagicMock()
        cc = CommandCenter(eal)
        result = cc.render()
        self.assertIn("System Status", result)
        self.assertIn("Aura AI", result)
        self.assertIn("Services", result)
        self.assertIn("Processes", result)
        self.assertIn("Recent Logs", result)

    def test_box_function(self):
        from aura_os.command_center.dashboard import _box
        result = _box("Title", ["line 1", "line 2"], 40)
        self.assertIn("Title", result)
        self.assertIn("line 1", result)


class TestCommandCenterWebAPI(unittest.TestCase):
    """Tests for aura_os.command_center.web data helpers."""

    def setUp(self):
        self._tmpdir = tempfile.mkdtemp()
        os.environ["AURA_HOME"] = self._tmpdir
        os.makedirs(os.path.join(self._tmpdir, "data"), exist_ok=True)
        os.makedirs(os.path.join(self._tmpdir, "models"), exist_ok=True)
        os.makedirs(os.path.join(self._tmpdir, "services"), exist_ok=True)
        os.makedirs(os.path.join(self._tmpdir, "logs"), exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def test_get_status(self):
        from aura_os.command_center.web import _get_status
        status = _get_status()
        self.assertIn("os", status)
        self.assertIn("host", status)
        self.assertIn("python", status)

    def test_get_aura_info(self):
        from aura_os.command_center.web import _get_aura_info
        info = _get_aura_info()
        self.assertEqual(info["name"], "Aura")
        self.assertIn("capabilities", info)

    def test_get_services_empty(self):
        from aura_os.command_center.web import _get_services
        services = _get_services()
        self.assertIsInstance(services, list)

    def test_get_processes_empty(self):
        from aura_os.command_center.web import _get_processes
        processes = _get_processes()
        self.assertIsInstance(processes, list)

    def test_get_logs(self):
        from aura_os.command_center.web import _get_logs
        logs = _get_logs()
        self.assertIsInstance(logs, list)

    def test_get_sessions_empty(self):
        from aura_os.command_center.web import _get_sessions
        sessions = _get_sessions()
        self.assertIsInstance(sessions, list)

    def test_chat_empty_prompt(self):
        from aura_os.command_center.web import _chat
        result = _chat("")
        self.assertIn("error", result)

    def test_chat_with_prompt(self):
        from aura_os.command_center.web import _chat
        result = _chat("hello")
        self.assertIn("response", result)

    def test_create_app(self):
        from aura_os.command_center.web import create_app
        eal = MagicMock()
        server = create_app(eal, host="127.0.0.1", port=0)
        self.assertIsNotNone(server)
        server.server_close()

    def test_html_template_content(self):
        from aura_os.command_center.web import _HTML_TEMPLATE
        self.assertIn("AURA OS", _HTML_TEMPLATE)
        self.assertIn("Command Center", _HTML_TEMPLATE)


class TestCLINewCommands(unittest.TestCase):
    """Tests for the new CLI subcommands (center, start, web)."""

    def test_parse_center(self):
        from aura_os.engine.cli import build_parser
        parser = build_parser()
        args = parser.parse_args(["center"])
        self.assertEqual(args.command, "center")

    def test_parse_start(self):
        from aura_os.engine.cli import build_parser
        parser = build_parser()
        args = parser.parse_args(["start"])
        self.assertEqual(args.command, "start")

    def test_parse_web(self):
        from aura_os.engine.cli import build_parser
        parser = build_parser()
        args = parser.parse_args(["web"])
        self.assertEqual(args.command, "web")

    def test_parse_web_with_options(self):
        from aura_os.engine.cli import build_parser
        parser = build_parser()
        args = parser.parse_args(["web", "--host", "0.0.0.0", "--port", "8080"])
        self.assertEqual(args.host, "0.0.0.0")
        self.assertEqual(args.port, 8080)

    def test_parse_shell_still_works(self):
        from aura_os.engine.cli import build_parser
        parser = build_parser()
        args = parser.parse_args(["shell"])
        self.assertEqual(args.command, "shell")


class TestRouterNewCommands(unittest.TestCase):
    """Tests for new command registration in the router."""

    def setUp(self):
        self._tmpdir = tempfile.mkdtemp()
        os.environ["AURA_HOME"] = self._tmpdir
        os.makedirs(os.path.join(self._tmpdir, "data"), exist_ok=True)
        os.makedirs(os.path.join(self._tmpdir, "models"), exist_ok=True)
        os.makedirs(os.path.join(self._tmpdir, "services"), exist_ok=True)
        os.makedirs(os.path.join(self._tmpdir, "logs"), exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def test_router_has_center(self):
        from aura_os.main import _build_router
        router = _build_router()
        self.assertIn("center", router._handlers)

    def test_router_has_web(self):
        from aura_os.main import _build_router
        router = _build_router()
        self.assertIn("web", router._handlers)

    def test_router_has_start(self):
        from aura_os.main import _build_router
        router = _build_router()
        self.assertIn("start", router._handlers)


class TestConfigDefaults(unittest.TestCase):
    """Tests for updated config defaults."""

    def test_config_has_aura_section(self):
        from aura_os.config.defaults import DEFAULT_CONFIG
        self.assertIn("aura", DEFAULT_CONFIG)
        self.assertEqual(DEFAULT_CONFIG["aura"]["name"], "Aura")

    def test_config_has_command_center_section(self):
        from aura_os.config.defaults import DEFAULT_CONFIG
        self.assertIn("command_center", DEFAULT_CONFIG)
        self.assertEqual(DEFAULT_CONFIG["command_center"]["web_port"], 7070)

    def test_config_version_updated(self):
        from aura_os.config.defaults import DEFAULT_CONFIG
        self.assertEqual(DEFAULT_CONFIG["version"], "0.2.0")


if __name__ == "__main__":
    unittest.main()
