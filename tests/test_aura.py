"""
AURA OS Test Suite
Tests for EAL, core engine, and module functionality.
"""

import os
import sys
import json
import tempfile
import unittest
from pathlib import Path

# Ensure the project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault("AURA_HOME", str(Path(tempfile.gettempdir()) / "aura_test"))


# ──────────────────────────────────────────────────────────────────────────────
# EAL tests
# ──────────────────────────────────────────────────────────────────────────────

class TestEALDetection(unittest.TestCase):

    def test_detect_environment_returns_dict(self):
        from eal import detect_environment
        env = detect_environment()
        self.assertIsInstance(env, dict)

    def test_env_has_required_keys(self):
        from eal import detect_environment
        env = detect_environment()
        for key in ("env_type", "is_termux", "binaries", "capabilities", "storage_root"):
            self.assertIn(key, env, f"Missing key: {key}")

    def test_env_type_is_known(self):
        from eal import detect_environment
        env = detect_environment()
        self.assertIn(env["env_type"], {"android", "linux", "macos", "windows", "unknown"})

    def test_capabilities_is_list(self):
        from eal import detect_environment
        env = detect_environment()
        self.assertIsInstance(env["capabilities"], list)

    def test_python_key_present(self):
        from eal import detect_environment
        env = detect_environment()
        self.assertIn("python", env)
        self.assertIsNotNone(env["python"])

    def test_get_adapter_returns_adapter(self):
        from eal import detect_environment, get_adapter
        from eal.adapters import BaseAdapter
        env = detect_environment()
        adapter = get_adapter(env)
        self.assertIsInstance(adapter, BaseAdapter)

    def test_load_env_map_creates_cache(self):
        from eal import load_env_map
        with tempfile.TemporaryDirectory() as td:
            cache = Path(td) / "env_map.json"
            env = load_env_map(cache_path=cache)
            self.assertTrue(cache.exists())
            data = json.loads(cache.read_text())
            self.assertEqual(data["env_type"], env["env_type"])


# ──────────────────────────────────────────────────────────────────────────────
# Adapter tests
# ──────────────────────────────────────────────────────────────────────────────

class TestBaseAdapter(unittest.TestCase):

    def setUp(self):
        from eal import detect_environment, get_adapter
        self.env = detect_environment()
        self.adapter = get_adapter(self.env)
        self.tmpdir = tempfile.mkdtemp()

    def test_write_and_read_file(self):
        path = os.path.join(self.tmpdir, "hello.txt")
        self.adapter.write_file(path, "Hello AURA")
        content = self.adapter.read_file(path)
        self.assertEqual(content, "Hello AURA")

    def test_list_dir(self):
        import os
        os.makedirs(os.path.join(self.tmpdir, "subdir"), exist_ok=True)
        open(os.path.join(self.tmpdir, "file.txt"), "w").close()
        entries = self.adapter.list_dir(self.tmpdir)
        names = [e[0] for e in entries]
        self.assertIn("subdir", names)
        self.assertIn("file.txt", names)

    def test_exists(self):
        path = os.path.join(self.tmpdir, "exists.txt")
        self.assertFalse(self.adapter.exists(path))
        open(path, "w").close()
        self.assertTrue(self.adapter.exists(path))

    def test_delete_file(self):
        path = os.path.join(self.tmpdir, "del.txt")
        open(path, "w").close()
        self.adapter.delete(path)
        self.assertFalse(os.path.exists(path))

    def test_run_command_success(self):
        rc, out, err = self.adapter.run(["echo", "aura"], capture=True)
        self.assertEqual(rc, 0)
        self.assertIn("aura", out)

    def test_run_command_failure(self):
        rc, out, err = self.adapter.run(["false"], capture=True)
        self.assertNotEqual(rc, 0)

    def test_has_network_is_bool(self):
        result = self.adapter.has_network()
        self.assertIsInstance(result, bool)

    def test_which_python(self):
        result = self.adapter.which("python3") or self.adapter.which("python")
        self.assertIsNotNone(result)


# ──────────────────────────────────────────────────────────────────────────────
# Command Engine tests
# ──────────────────────────────────────────────────────────────────────────────

class TestCommandEngine(unittest.TestCase):

    def setUp(self):
        from core.engine import CommandEngine
        self.engine = CommandEngine()

    def test_engine_initializes(self):
        self.assertIsNotNone(self.engine.env_map)
        self.assertIsNotNone(self.engine.adapter)
        self.assertIsNotNone(self.engine.registry)

    def test_registry_has_builtin_commands(self):
        names = self.engine.registry.names()
        for cmd in ("help", "sys", "run", "ai", "repo", "fs", "auto", "ui", "env", "reload"):
            self.assertIn(cmd, names)

    def test_run_empty_shows_help(self):
        # Should not raise
        self.engine.run([])

    def test_run_help(self):
        # Should not raise
        self.engine.run(["help"])

    def test_run_unknown_command_graceful(self):
        # Should not raise
        self.engine.run(["__nonexistent__"])

    def test_run_sys_info(self):
        # Should not raise
        self.engine.run(["sys", "info"])

    def test_run_sys_caps(self):
        self.engine.run(["sys", "caps"])

    def test_run_env(self):
        self.engine.run(["env"])

    def test_run_reload(self):
        self.engine.run(["reload"])


# ──────────────────────────────────────────────────────────────────────────────
# AI Module tests
# ──────────────────────────────────────────────────────────────────────────────

class TestAIModule(unittest.TestCase):

    def setUp(self):
        from eal import detect_environment, get_adapter
        from modules.ai import AIModule
        env = detect_environment()
        adapter = get_adapter(env)
        self.ai = AIModule(env, adapter)

    def test_backend_is_string(self):
        self.assertIsInstance(self.ai.backend(), str)

    def test_query_returns_string(self):
        result = self.ai.query("hello")
        self.assertIsInstance(result, str)
        self.assertTrue(len(result) > 0)

    def test_query_help(self):
        result = self.ai.query("help")
        self.assertIsInstance(result, str)

    def test_query_run_script(self):
        result = self.ai.query("how do I run a script")
        self.assertIn("aura run", result)

    def test_query_git(self):
        result = self.ai.query("how do I use git")
        self.assertIsInstance(result, str)

    def test_query_unknown_returns_fallback(self):
        result = self.ai.query("xyzzy plugh")
        self.assertIsInstance(result, str)


# ──────────────────────────────────────────────────────────────────────────────
# FileSystem Manager tests
# ──────────────────────────────────────────────────────────────────────────────

class TestFileSystemManager(unittest.TestCase):

    def setUp(self):
        from eal import detect_environment, get_adapter
        from core.filesystem import FileSystemManager
        env = detect_environment()
        adapter = get_adapter(env)
        self.fsm = FileSystemManager(adapter)
        self.tmpdir = tempfile.mkdtemp()

    def test_ls_directory(self):
        # Should not raise
        self.fsm.ls(self.tmpdir)

    def test_ls_nonexistent(self):
        self.fsm.ls("/nonexistent_path_xyz")

    def test_cat_file(self):
        path = os.path.join(self.tmpdir, "test.txt")
        Path(path).write_text("test content")
        self.fsm.cat(path)

    def test_cat_nonexistent(self):
        self.fsm.cat("/nonexistent/file.txt")

    def test_find_with_pattern(self):
        Path(os.path.join(self.tmpdir, "foo.py")).write_text("pass")
        Path(os.path.join(self.tmpdir, "bar.txt")).write_text("hello")
        self.fsm.find(self.tmpdir, ".py")

    def test_mkdir(self):
        new_dir = os.path.join(self.tmpdir, "newsubdir")
        self.fsm.mkdir(new_dir)
        self.assertTrue(os.path.isdir(new_dir))

    def test_rm_file(self):
        path = os.path.join(self.tmpdir, "todelete.txt")
        Path(path).write_text("bye")
        self.fsm.rm(path)
        self.assertFalse(os.path.exists(path))


# ──────────────────────────────────────────────────────────────────────────────
# Repo Module tests
# ──────────────────────────────────────────────────────────────────────────────

class TestRepoModule(unittest.TestCase):

    def setUp(self):
        from eal import detect_environment, get_adapter
        from modules.repo import RepoModule
        self.tmpdir = tempfile.mkdtemp()
        env = detect_environment()
        env["storage_root"] = self.tmpdir
        adapter = get_adapter(env)
        self.repo = RepoModule(env, adapter)

    def test_list_repos_empty(self):
        # Should not raise
        self.repo.list_repos()

    def test_create_repo(self):
        git = self.repo._git
        if not git:
            self.skipTest("git not installed")
        self.repo.create("myrepo")
        repo_path = Path(self.tmpdir) / "repos" / "myrepo"
        self.assertTrue(repo_path.is_dir())
        self.assertTrue((repo_path / ".git").is_dir())

    def test_create_duplicate_repo(self):
        git = self.repo._git
        if not git:
            self.skipTest("git not installed")
        self.repo.create("duperepo")
        # Second create should not raise
        self.repo.create("duperepo")

    def test_status_nonexistent(self):
        # Should not raise
        self.repo.status("/nonexistent_path_xyz")


# ──────────────────────────────────────────────────────────────────────────────
# Automation Module tests
# ──────────────────────────────────────────────────────────────────────────────

class TestAutomationModule(unittest.TestCase):

    def setUp(self):
        from eal import detect_environment, get_adapter
        from modules.automation import AutomationModule
        self.tmpdir = tempfile.mkdtemp()
        env = detect_environment()
        env["storage_root"] = self.tmpdir
        adapter = get_adapter(env)
        self.auto = AutomationModule(env, adapter)

    def test_list_tasks_empty(self):
        self.auto.list_tasks()

    def test_create_task(self):
        self.auto.create_task("unit-test-task")
        task_file = Path(self.tmpdir) / "tasks" / "unit-test-task.json"
        self.assertTrue(task_file.exists())
        data = json.loads(task_file.read_text())
        self.assertEqual(data["name"], "unit-test-task")
        self.assertIn("steps", data)

    def test_create_duplicate_task(self):
        self.auto.create_task("dup-task")
        # Should not raise
        self.auto.create_task("dup-task")

    def test_run_nonexistent_task(self):
        # Should not raise
        self.auto.run_task("does-not-exist")

    def test_run_task(self):
        self.auto.create_task("run-test")
        # Should not raise
        self.auto.run_task("run-test")
        # Log file should be created
        logs = list((Path(self.tmpdir) / "logs").glob("auto_run-test_*.log"))
        self.assertTrue(len(logs) > 0)

    def test_run_task_no_name(self):
        self.auto.run_task(None)


# ──────────────────────────────────────────────────────────────────────────────
# Browser Module tests
# ──────────────────────────────────────────────────────────────────────────────

class TestBrowserModule(unittest.TestCase):

    def setUp(self):
        from eal import detect_environment, get_adapter
        from modules.browser import BrowserModule
        self.tmpdir = tempfile.mkdtemp()
        env = detect_environment()
        env["storage_root"] = self.tmpdir
        self.adapter = get_adapter(env)
        self.bm = BrowserModule(env, self.adapter)

    def test_terminal_dashboard_runs(self):
        # Should not raise
        self.bm.start_terminal()

    def test_web_ui_html_contains_aura(self):
        html = self.bm._get_html_dashboard()
        self.assertIn("AURA OS", html)
        self.assertIn("Capabilities", html)


# ──────────────────────────────────────────────────────────────────────────────
# Boot / Bootstrap tests
# ──────────────────────────────────────────────────────────────────────────────

class TestBootstrap(unittest.TestCase):

    def test_bootstrap_creates_dirs(self):
        from boot.startup import run_bootstrap
        with tempfile.TemporaryDirectory() as td:
            aura_home = Path(td) / "aura"
            env, adapter = run_bootstrap(aura_home)
            self.assertTrue((aura_home / "configs").is_dir())
            self.assertTrue((aura_home / "logs").is_dir())
            self.assertTrue((aura_home / "tasks").is_dir())
            self.assertTrue((aura_home / "repos").is_dir())

    def test_bootstrap_writes_config(self):
        from boot.startup import run_bootstrap
        with tempfile.TemporaryDirectory() as td:
            aura_home = Path(td) / "aura"
            run_bootstrap(aura_home)
            cfg = aura_home / "configs" / "system.json"
            self.assertTrue(cfg.exists())
            data = json.loads(cfg.read_text())
            self.assertEqual(data["version"], "1.0.0")

    def test_bootstrap_returns_env_and_adapter(self):
        from boot.startup import run_bootstrap
        from eal.adapters import BaseAdapter
        with tempfile.TemporaryDirectory() as td:
            env, adapter = run_bootstrap(Path(td) / "aura")
            self.assertIsInstance(env, dict)
            self.assertIsInstance(adapter, BaseAdapter)


if __name__ == "__main__":
    unittest.main(verbosity=2)
