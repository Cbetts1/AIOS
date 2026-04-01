"""Tests for aura_os/config/settings.py and aura_os/config/defaults.py."""

import json
import os
import sys
import tempfile
import threading
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from aura_os.config.defaults import DEFAULT_CONFIG
from aura_os.config.settings import Settings, _deep_merge


class TestDeepMerge(unittest.TestCase):
    """Unit tests for _deep_merge helper."""

    def test_simple_override(self):
        base = {"a": 1, "b": 2}
        override = {"b": 99}
        result = _deep_merge(base, override)
        self.assertEqual(result, {"a": 1, "b": 99})

    def test_deep_merge_nested(self):
        base = {"ai": {"default_model": "auto", "max_tokens": 512}}
        override = {"ai": {"max_tokens": 1024}}
        result = _deep_merge(base, override)
        self.assertEqual(result["ai"]["default_model"], "auto")
        self.assertEqual(result["ai"]["max_tokens"], 1024)

    def test_new_key_added(self):
        base = {"x": 1}
        override = {"y": 2}
        result = _deep_merge(base, override)
        self.assertIn("x", result)
        self.assertIn("y", result)

    def test_base_not_mutated(self):
        base = {"a": {"b": 1}}
        override = {"a": {"b": 2}}
        _deep_merge(base, override)
        self.assertEqual(base["a"]["b"], 1)

    def test_override_scalar_over_dict(self):
        base = {"a": {"nested": 1}}
        override = {"a": "scalar"}
        result = _deep_merge(base, override)
        self.assertEqual(result["a"], "scalar")

    def test_empty_override(self):
        base = {"a": 1}
        result = _deep_merge(base, {})
        self.assertEqual(result, {"a": 1})

    def test_empty_base(self):
        override = {"a": 1}
        result = _deep_merge({}, override)
        self.assertEqual(result, {"a": 1})


class TestDefaultConfig(unittest.TestCase):
    """Tests for the DEFAULT_CONFIG constant."""

    def test_has_required_keys(self):
        for key in ("version", "log_level", "ai", "shell", "pkg", "fs"):
            self.assertIn(key, DEFAULT_CONFIG)

    def test_ai_section(self):
        ai = DEFAULT_CONFIG["ai"]
        self.assertIn("default_model", ai)
        self.assertIn("max_tokens", ai)
        self.assertIn("runtime", ai)

    def test_fs_section(self):
        fs = DEFAULT_CONFIG["fs"]
        self.assertIn("data_dir", fs)
        self.assertIn("max_vfs_size_mb", fs)


class TestSettings(unittest.TestCase):
    """Tests for the Settings singleton."""

    def setUp(self):
        Settings.reset()
        self.tmpdir = tempfile.mkdtemp()
        self.config_path = os.path.join(self.tmpdir, "settings.json")

    def tearDown(self):
        Settings.reset()
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _make_settings(self, initial_data=None):
        if initial_data is not None:
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            with open(self.config_path, "w") as fh:
                json.dump(initial_data, fh)
        return Settings(config_path=self.config_path)

    def test_singleton_returns_same_instance(self):
        s1 = Settings(config_path=self.config_path)
        s2 = Settings(config_path=self.config_path)
        self.assertIs(s1, s2)

    def test_reset_allows_new_instance(self):
        s1 = Settings(config_path=self.config_path)
        Settings.reset()
        s2 = Settings(config_path=self.config_path)
        self.assertIsNot(s1, s2)

    def test_get_returns_default_when_no_file(self):
        s = self._make_settings()
        self.assertEqual(s.get("ai.default_model"), "auto")

    def test_get_nested_key(self):
        s = self._make_settings({"ai": {"default_model": "mistral"}})
        self.assertEqual(s.get("ai.default_model"), "mistral")

    def test_get_missing_key_returns_default(self):
        s = self._make_settings()
        self.assertIsNone(s.get("nonexistent.key"))
        self.assertEqual(s.get("nonexistent.key", "fallback"), "fallback")

    def test_get_top_level_key(self):
        s = self._make_settings()
        self.assertEqual(s.get("log_level"), "INFO")

    def test_set_creates_and_persists(self):
        s = self._make_settings()
        s.set("log_level", "DEBUG")
        self.assertEqual(s.get("log_level"), "DEBUG")
        # Verify persisted to disk
        with open(self.config_path) as fh:
            data = json.load(fh)
        self.assertEqual(data["log_level"], "DEBUG")

    def test_set_nested_key(self):
        s = self._make_settings()
        s.set("ai.max_tokens", 256)
        self.assertEqual(s.get("ai.max_tokens"), 256)

    def test_set_creates_intermediate_dicts(self):
        s = self._make_settings()
        s.set("new.deep.key", "value")
        self.assertEqual(s.get("new.deep.key"), "value")

    def test_as_dict_returns_dict(self):
        s = self._make_settings()
        d = s.as_dict()
        self.assertIsInstance(d, dict)
        self.assertIn("ai", d)

    def test_as_dict_is_shallow_copy(self):
        s = self._make_settings()
        d1 = s.as_dict()
        d2 = s.as_dict()
        self.assertIsNot(d1, d2)

    def test_load_merges_with_defaults(self):
        # Disk has partial override; defaults should fill the rest
        s = self._make_settings({"log_level": "WARNING"})
        self.assertEqual(s.get("log_level"), "WARNING")
        # Default ai.default_model should still be present
        self.assertEqual(s.get("ai.default_model"), "auto")

    def test_corrupted_json_falls_back_to_defaults(self):
        with open(self.config_path, "w") as fh:
            fh.write("NOT VALID JSON {{{")
        s = Settings(config_path=self.config_path)
        # Should not raise; falls back to defaults
        self.assertEqual(s.get("log_level"), "INFO")

    def test_get_partial_path_returns_dict(self):
        s = self._make_settings()
        ai_section = s.get("ai")
        self.assertIsInstance(ai_section, dict)
        self.assertIn("default_model", ai_section)

    def test_thread_safety_singleton(self):
        instances = []

        def create():
            instances.append(Settings(config_path=self.config_path))

        threads = [threading.Thread(target=create) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        first = instances[0]
        for inst in instances[1:]:
            self.assertIs(inst, first)


if __name__ == "__main__":
    unittest.main()
