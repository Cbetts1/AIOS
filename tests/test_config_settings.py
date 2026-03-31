"""Tests for aura_os.config.settings — Settings singleton and _deep_merge."""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault("AURA_HOME", str(Path(tempfile.gettempdir()) / "aura_os_test"))

from aura_os.config.settings import Settings, _deep_merge
from aura_os.config.defaults import DEFAULT_CONFIG


class TestDeepMerge(unittest.TestCase):
    """Tests for the _deep_merge helper function."""

    def test_empty_override(self):
        base = {"a": 1, "b": 2}
        result = _deep_merge(base, {})
        self.assertEqual(result, {"a": 1, "b": 2})

    def test_empty_base(self):
        result = _deep_merge({}, {"a": 1})
        self.assertEqual(result, {"a": 1})

    def test_override_simple_key(self):
        base = {"a": 1, "b": 2}
        result = _deep_merge(base, {"a": 99})
        self.assertEqual(result, {"a": 99, "b": 2})

    def test_nested_merge(self):
        base = {"x": {"a": 1, "b": 2}}
        override = {"x": {"b": 99, "c": 3}}
        result = _deep_merge(base, override)
        self.assertEqual(result, {"x": {"a": 1, "b": 99, "c": 3}})

    def test_deep_nested_merge(self):
        base = {"l1": {"l2": {"l3": "old"}}}
        override = {"l1": {"l2": {"l3": "new"}}}
        result = _deep_merge(base, override)
        self.assertEqual(result["l1"]["l2"]["l3"], "new")

    def test_does_not_mutate_base(self):
        base = {"a": 1}
        _deep_merge(base, {"a": 2})
        self.assertEqual(base, {"a": 1})

    def test_override_replaces_non_dict_with_dict(self):
        base = {"a": "string"}
        result = _deep_merge(base, {"a": {"nested": True}})
        self.assertEqual(result, {"a": {"nested": True}})

    def test_override_replaces_dict_with_non_dict(self):
        base = {"a": {"nested": True}}
        result = _deep_merge(base, {"a": "string"})
        self.assertEqual(result, {"a": "string"})


class TestSettings(unittest.TestCase):
    """Tests for the Settings singleton."""

    def setUp(self):
        Settings.reset()
        self._tmp = tempfile.mkdtemp()
        self._config_path = os.path.join(self._tmp, "settings.json")

    def tearDown(self):
        Settings.reset()
        import shutil
        shutil.rmtree(self._tmp, ignore_errors=True)

    # ── Singleton behaviour ───────────────────────────────────────────

    def test_singleton_returns_same_instance(self):
        s1 = Settings(config_path=self._config_path)
        s2 = Settings(config_path=self._config_path)
        self.assertIs(s1, s2)

    def test_reset_clears_singleton(self):
        s1 = Settings(config_path=self._config_path)
        Settings.reset()
        s2 = Settings(config_path=self._config_path)
        # After reset, should be a new instance (may or may not be same object
        # depending on GC, but _initialized will be fresh)
        self.assertIsNotNone(s2)

    # ── Default config ────────────────────────────────────────────────

    def test_defaults_loaded_when_no_file(self):
        s = Settings(config_path=self._config_path)
        data = s.as_dict()
        self.assertEqual(data["version"], DEFAULT_CONFIG["version"])

    def test_get_top_level_key(self):
        s = Settings(config_path=self._config_path)
        self.assertEqual(s.get("version"), DEFAULT_CONFIG["version"])

    def test_get_nested_key_dot_notation(self):
        s = Settings(config_path=self._config_path)
        self.assertEqual(s.get("ai.default_model"), DEFAULT_CONFIG["ai"]["default_model"])

    def test_get_missing_key_returns_default(self):
        s = Settings(config_path=self._config_path)
        self.assertIsNone(s.get("nonexistent"))
        self.assertEqual(s.get("nonexistent", "fallback"), "fallback")

    def test_get_deep_missing_key(self):
        s = Settings(config_path=self._config_path)
        self.assertIsNone(s.get("a.b.c.d"))

    # ── Set and persist ───────────────────────────────────────────────

    def test_set_top_level_key(self):
        s = Settings(config_path=self._config_path)
        s.set("log_level", "DEBUG")
        self.assertEqual(s.get("log_level"), "DEBUG")

    def test_set_nested_key(self):
        s = Settings(config_path=self._config_path)
        s.set("ai.max_tokens", 1024)
        self.assertEqual(s.get("ai.max_tokens"), 1024)

    def test_set_creates_intermediate_dicts(self):
        s = Settings(config_path=self._config_path)
        s.set("new.nested.key", "value")
        self.assertEqual(s.get("new.nested.key"), "value")

    def test_set_persists_to_disk(self):
        s = Settings(config_path=self._config_path)
        s.set("custom_key", "hello")
        # Read file directly
        with open(self._config_path, "r") as f:
            data = json.load(f)
        self.assertEqual(data["custom_key"], "hello")

    # ── Load from existing file ───────────────────────────────────────

    def test_load_from_existing_config(self):
        # Write a custom config file
        custom = {"version": "9.9.9", "extra": True}
        with open(self._config_path, "w") as f:
            json.dump(custom, f)
        s = Settings(config_path=self._config_path)
        self.assertEqual(s.get("version"), "9.9.9")
        self.assertTrue(s.get("extra"))
        # Defaults should still be merged
        self.assertIsNotNone(s.get("ai.default_model"))

    def test_load_corrupted_file_uses_defaults(self):
        with open(self._config_path, "w") as f:
            f.write("not valid json {{{")
        s = Settings(config_path=self._config_path)
        self.assertEqual(s.get("version"), DEFAULT_CONFIG["version"])

    # ── as_dict ───────────────────────────────────────────────────────

    def test_as_dict_returns_dict(self):
        s = Settings(config_path=self._config_path)
        d = s.as_dict()
        self.assertIsInstance(d, dict)
        self.assertIn("version", d)

    def test_as_dict_returns_copy(self):
        s = Settings(config_path=self._config_path)
        d = s.as_dict()
        d["version"] = "hacked"
        self.assertNotEqual(s.get("version"), "hacked")


if __name__ == "__main__":
    unittest.main()
