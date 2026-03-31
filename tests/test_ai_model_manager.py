"""Tests for aura_os.ai.model_manager — ModelManager."""

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault("AURA_HOME", str(Path(tempfile.gettempdir()) / "aura_os_test"))

from aura_os.ai.model_manager import ModelManager


class TestModelManagerInit(unittest.TestCase):
    """Tests for ModelManager initialization."""

    def test_creates_models_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            models_dir = os.path.join(tmp, "models")
            mm = ModelManager(models_dir=models_dir)
            self.assertTrue(os.path.isdir(models_dir))

    def test_default_models_dir(self):
        mm = ModelManager()
        self.assertTrue(mm._models_dir.endswith("models"))


class TestModelManagerDetectRuntimes(unittest.TestCase):
    """Tests for detect_runtimes()."""

    def test_returns_dict(self):
        mm = ModelManager()
        result = mm.detect_runtimes()
        self.assertIsInstance(result, dict)

    def test_contains_expected_keys(self):
        mm = ModelManager()
        result = mm.detect_runtimes()
        self.assertIn("ollama", result)
        self.assertIn("llama.cpp", result)
        self.assertIn("ctransformers", result)

    def test_values_are_string_or_none(self):
        mm = ModelManager()
        for name, path in mm.detect_runtimes().items():
            self.assertTrue(path is None or isinstance(path, str),
                            f"{name} has invalid type: {type(path)}")

    @mock.patch("shutil.which", return_value="/usr/bin/ollama")
    def test_detects_ollama_when_available(self, mock_which):
        mm = ModelManager()
        result = mm.detect_runtimes()
        self.assertEqual(result["ollama"], "/usr/bin/ollama")


class TestModelManagerGetActiveRuntime(unittest.TestCase):
    """Tests for get_active_runtime()."""

    @mock.patch.object(ModelManager, "detect_runtimes",
                       return_value={"ollama": "/usr/bin/ollama",
                                     "llama.cpp": None,
                                     "ctransformers": None})
    def test_returns_ollama_when_available(self, _):
        mm = ModelManager()
        self.assertEqual(mm.get_active_runtime(), "ollama")

    @mock.patch.object(ModelManager, "detect_runtimes",
                       return_value={"ollama": None,
                                     "llama.cpp": "/usr/bin/llama-cli",
                                     "ctransformers": None})
    def test_returns_llama_cpp_as_fallback(self, _):
        mm = ModelManager()
        self.assertEqual(mm.get_active_runtime(), "llama.cpp")

    @mock.patch.object(ModelManager, "detect_runtimes",
                       return_value={"ollama": None,
                                     "llama.cpp": None,
                                     "ctransformers": "python-package"})
    def test_returns_ctransformers_as_last_fallback(self, _):
        mm = ModelManager()
        self.assertEqual(mm.get_active_runtime(), "ctransformers")

    @mock.patch.object(ModelManager, "detect_runtimes",
                       return_value={"ollama": None,
                                     "llama.cpp": None,
                                     "ctransformers": None})
    def test_returns_none_when_nothing_available(self, _):
        mm = ModelManager()
        self.assertIsNone(mm.get_active_runtime())


class TestModelManagerListModels(unittest.TestCase):
    """Tests for list_models()."""

    def test_empty_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            mm = ModelManager(models_dir=tmp)
            self.assertEqual(mm.list_models(), [])

    def test_finds_gguf_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "model.gguf").touch()
            (Path(tmp) / "other.txt").touch()
            mm = ModelManager(models_dir=tmp)
            models = mm.list_models()
            self.assertEqual(len(models), 1)
            self.assertTrue(models[0].endswith("model.gguf"))

    def test_finds_bin_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "model.bin").touch()
            mm = ModelManager(models_dir=tmp)
            self.assertEqual(len(mm.list_models()), 1)

    def test_returns_sorted_list(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "b_model.gguf").touch()
            (Path(tmp) / "a_model.gguf").touch()
            mm = ModelManager(models_dir=tmp)
            models = mm.list_models()
            basenames = [os.path.basename(m) for m in models]
            self.assertEqual(basenames, ["a_model.gguf", "b_model.gguf"])

    def test_ignores_non_model_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "readme.md").touch()
            (Path(tmp) / "config.json").touch()
            mm = ModelManager(models_dir=tmp)
            self.assertEqual(mm.list_models(), [])


class TestModelManagerLoadModel(unittest.TestCase):
    """Tests for load_model()."""

    def test_load_existing_absolute_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            model_file = os.path.join(tmp, "test.gguf")
            Path(model_file).touch()
            mm = ModelManager(models_dir=tmp)
            result = mm.load_model(model_file)
            self.assertEqual(result, model_file)

    def test_load_relative_name_in_models_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "my_model.gguf").touch()
            mm = ModelManager(models_dir=tmp)
            result = mm.load_model("my_model.gguf")
            self.assertIsNotNone(result)
            self.assertTrue(result.endswith("my_model.gguf"))

    def test_load_nonexistent_returns_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            mm = ModelManager(models_dir=tmp)
            result = mm.load_model("nonexistent.gguf")
            self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
