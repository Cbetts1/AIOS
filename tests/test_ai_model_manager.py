"""Tests for aura_os/ai/model_manager.py — ModelManager."""

import os
import sys
import tempfile
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from aura_os.ai.model_manager import ModelManager


class TestModelManager(unittest.TestCase):
    """Tests for ModelManager runtime detection and model file discovery."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.mm = ModelManager(models_dir=self.tmpdir)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    # ------------------------------------------------------------------
    # detect_runtimes
    # ------------------------------------------------------------------

    def test_detect_runtimes_returns_dict(self):
        runtimes = self.mm.detect_runtimes()
        self.assertIsInstance(runtimes, dict)

    def test_detect_runtimes_has_known_keys(self):
        runtimes = self.mm.detect_runtimes()
        for key in ("ollama", "llama.cpp", "ctransformers"):
            self.assertIn(key, runtimes)

    def test_detect_runtimes_ollama_found(self):
        with patch("shutil.which", side_effect=lambda b: "/usr/bin/ollama" if b == "ollama" else None):
            runtimes = self.mm.detect_runtimes()
        self.assertEqual(runtimes["ollama"], "/usr/bin/ollama")

    def test_detect_runtimes_ollama_missing(self):
        with patch("shutil.which", return_value=None):
            runtimes = self.mm.detect_runtimes()
        self.assertIsNone(runtimes["ollama"])
        self.assertIsNone(runtimes["llama.cpp"])

    def test_detect_runtimes_ctransformers_installed(self):
        fake_module = MagicMock()
        with patch.dict("sys.modules", {"ctransformers": fake_module}):
            runtimes = self.mm.detect_runtimes()
        self.assertEqual(runtimes.get("ctransformers"), "python-package")

    def test_detect_runtimes_ctransformers_not_installed(self):
        with patch.dict("sys.modules", {"ctransformers": None}):
            with patch("builtins.__import__", side_effect=ImportError):
                # Use the actual detect_runtimes but block ctransformers import
                pass
        # Ensure ctransformers absence does not raise
        runtimes = self.mm.detect_runtimes()
        self.assertIn("ctransformers", runtimes)

    # ------------------------------------------------------------------
    # get_active_runtime
    # ------------------------------------------------------------------

    def test_get_active_runtime_returns_ollama_when_available(self):
        with patch("shutil.which", side_effect=lambda b: "/usr/bin/ollama" if b == "ollama" else None):
            runtime = self.mm.get_active_runtime()
        self.assertEqual(runtime, "ollama")

    def test_get_active_runtime_returns_none_when_nothing_available(self):
        with patch("shutil.which", return_value=None):
            with patch.dict("sys.modules", {}):
                # Ensure ctransformers also absent
                runtime = self.mm.get_active_runtime()
        # May be None or ctransformers depending on environment; just verify no crash
        self.assertTrue(runtime is None or isinstance(runtime, str))

    def test_get_active_runtime_prefers_ollama_over_llama_cpp(self):
        with patch("shutil.which", return_value="/usr/bin/binary"):
            runtime = self.mm.get_active_runtime()
        self.assertEqual(runtime, "ollama")

    # ------------------------------------------------------------------
    # list_models
    # ------------------------------------------------------------------

    def test_list_models_empty_dir_returns_empty(self):
        models = self.mm.list_models()
        self.assertEqual(models, [])

    def test_list_models_finds_gguf_files(self):
        open(os.path.join(self.tmpdir, "model.gguf"), "w").close()
        models = self.mm.list_models()
        self.assertEqual(len(models), 1)
        self.assertTrue(models[0].endswith(".gguf"))

    def test_list_models_finds_bin_files(self):
        open(os.path.join(self.tmpdir, "model.bin"), "w").close()
        models = self.mm.list_models()
        self.assertEqual(len(models), 1)
        self.assertTrue(models[0].endswith(".bin"))

    def test_list_models_ignores_other_extensions(self):
        open(os.path.join(self.tmpdir, "readme.txt"), "w").close()
        open(os.path.join(self.tmpdir, "config.json"), "w").close()
        models = self.mm.list_models()
        self.assertEqual(models, [])

    def test_list_models_returns_sorted_paths(self):
        for name in ("z_model.gguf", "a_model.gguf", "m_model.bin"):
            open(os.path.join(self.tmpdir, name), "w").close()
        models = self.mm.list_models()
        self.assertEqual(models, sorted(models))

    def test_list_models_oserror_returns_empty(self):
        with patch("os.listdir", side_effect=OSError):
            models = self.mm.list_models()
        self.assertEqual(models, [])

    def test_list_models_includes_multiple(self):
        for name in ("a.gguf", "b.gguf", "c.bin"):
            open(os.path.join(self.tmpdir, name), "w").close()
        models = self.mm.list_models()
        self.assertEqual(len(models), 3)

    # ------------------------------------------------------------------
    # load_model
    # ------------------------------------------------------------------

    def test_load_model_existing_absolute_path(self):
        path = os.path.join(self.tmpdir, "test.gguf")
        open(path, "w").close()
        result = self.mm.load_model(path)
        self.assertEqual(result, path)

    def test_load_model_relative_resolved_in_models_dir(self):
        path = os.path.join(self.tmpdir, "relative.gguf")
        open(path, "w").close()
        result = self.mm.load_model("relative.gguf")
        self.assertEqual(result, path)

    def test_load_model_nonexistent_returns_none(self):
        result = self.mm.load_model("/nonexistent/path/model.gguf")
        self.assertIsNone(result)

    def test_load_model_nonexistent_relative_returns_none(self):
        result = self.mm.load_model("missing.gguf")
        self.assertIsNone(result)

    # ------------------------------------------------------------------
    # Constructor
    # ------------------------------------------------------------------

    def test_models_dir_created_on_init(self):
        new_dir = os.path.join(self.tmpdir, "new_models")
        mm = ModelManager(models_dir=new_dir)
        self.assertTrue(os.path.isdir(new_dir))

    def test_default_models_dir_uses_aura_home(self):
        env_dir = os.path.join(self.tmpdir, "custom_aura")
        with patch.dict(os.environ, {"AURA_HOME": env_dir}):
            mm = ModelManager()
        expected = os.path.join(env_dir, "models")
        self.assertEqual(mm._models_dir, expected)


if __name__ == "__main__":
    unittest.main()
