"""Tests for aura_os.ai.inference — LocalInference."""

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault("AURA_HOME", str(Path(tempfile.gettempdir()) / "aura_os_test"))

from aura_os.ai.inference import LocalInference, _INSTALL_HINT
from aura_os.ai.model_manager import ModelManager


class TestLocalInferenceInit(unittest.TestCase):
    """Tests for LocalInference initialization."""

    def test_creates_default_model_manager(self):
        li = LocalInference()
        self.assertIsInstance(li._mm, ModelManager)

    def test_accepts_custom_model_manager(self):
        mm = ModelManager()
        li = LocalInference(model_manager=mm)
        self.assertIs(li._mm, mm)


class TestLocalInferenceQuery(unittest.TestCase):
    """Tests for LocalInference.query() routing."""

    def test_returns_install_hint_when_no_runtime(self):
        mm = mock.MagicMock()
        mm.get_active_runtime.return_value = None
        li = LocalInference(model_manager=mm)
        result = li.query("hello")
        self.assertEqual(result, _INSTALL_HINT)

    @mock.patch.object(LocalInference, "_query_ollama", return_value="ollama response")
    def test_routes_to_ollama(self, mock_ollama):
        mm = mock.MagicMock()
        mm.get_active_runtime.return_value = "ollama"
        li = LocalInference(model_manager=mm)
        result = li.query("test prompt")
        self.assertEqual(result, "ollama response")
        mock_ollama.assert_called_once_with("test prompt", None, 512)

    @mock.patch.object(LocalInference, "_query_llama_cpp", return_value="llama response")
    def test_routes_to_llama_cpp(self, mock_llama):
        mm = mock.MagicMock()
        mm.get_active_runtime.return_value = "llama.cpp"
        li = LocalInference(model_manager=mm)
        result = li.query("test prompt", model="mymodel", max_tokens=100)
        self.assertEqual(result, "llama response")
        mock_llama.assert_called_once_with("test prompt", "mymodel", 100)


class TestLocalInferenceOllama(unittest.TestCase):
    """Tests for _query_ollama with mocked subprocess."""

    @mock.patch("shutil.which", return_value=None)
    def test_returns_hint_when_ollama_not_found(self, _):
        li = LocalInference()
        result = li._query_ollama("prompt", None, 512)
        self.assertEqual(result, _INSTALL_HINT)

    @mock.patch("shutil.which", return_value="/usr/bin/ollama")
    @mock.patch("subprocess.run")
    @mock.patch.object(LocalInference, "_default_ollama_model", return_value="mistral")
    def test_successful_query(self, _, mock_run, __):
        mock_run.return_value = mock.MagicMock(returncode=0, stdout="Hello world\n")
        li = LocalInference()
        result = li._query_ollama("prompt", None, 512)
        self.assertEqual(result, "Hello world")

    @mock.patch("shutil.which", return_value="/usr/bin/ollama")
    @mock.patch("subprocess.run")
    @mock.patch.object(LocalInference, "_default_ollama_model", return_value="mistral")
    def test_error_response(self, _, mock_run, __):
        mock_run.return_value = mock.MagicMock(returncode=1, stderr="model not found")
        li = LocalInference()
        result = li._query_ollama("prompt", None, 512)
        self.assertIn("error", result.lower())

    @mock.patch("shutil.which", return_value="/usr/bin/ollama")
    @mock.patch("subprocess.run", side_effect=TimeoutError)
    @mock.patch.object(LocalInference, "_default_ollama_model", return_value="mistral")
    def test_uses_specified_model(self, _, mock_run, __):
        mock_run.return_value = mock.MagicMock(returncode=0, stdout="output")
        li = LocalInference()
        li._query_ollama("prompt", "custom-model", 512)
        # The model param should be "custom-model", not the default
        call_args = mock_run.call_args[0][0]
        self.assertIn("custom-model", call_args)

    @mock.patch("shutil.which", return_value="/usr/bin/ollama")
    @mock.patch.object(LocalInference, "_default_ollama_model", return_value=None)
    def test_no_models_available(self, _, __):
        li = LocalInference()
        result = li._query_ollama("prompt", None, 512)
        self.assertIn("no models", result.lower())


class TestLocalInferenceLlamaCpp(unittest.TestCase):
    """Tests for _query_llama_cpp with mocked subprocess."""

    @mock.patch("shutil.which", return_value=None)
    def test_returns_hint_when_llama_cli_not_found(self, _):
        li = LocalInference()
        result = li._query_llama_cpp("prompt", None, 512)
        self.assertEqual(result, _INSTALL_HINT)

    @mock.patch("shutil.which", return_value="/usr/bin/llama-cli")
    @mock.patch("subprocess.run")
    def test_successful_query(self, mock_run, _):
        mock_run.return_value = mock.MagicMock(returncode=0, stdout="Generated text\n")
        li = LocalInference()
        result = li._query_llama_cpp("prompt", "/path/to/model.gguf", 512)
        self.assertEqual(result, "Generated text")

    @mock.patch("shutil.which", return_value="/usr/bin/llama-cli")
    @mock.patch.object(LocalInference, "_first_local_model", return_value=None)
    def test_no_model_file(self, _, __):
        li = LocalInference()
        result = li._query_llama_cpp("prompt", None, 512)
        self.assertIn("no model files", result.lower())


class TestLocalInferenceFirstLocalModel(unittest.TestCase):
    """Tests for _first_local_model helper."""

    def test_returns_first_model(self):
        mm = mock.MagicMock()
        mm.list_models.return_value = ["/a/model1.gguf", "/a/model2.gguf"]
        li = LocalInference(model_manager=mm)
        self.assertEqual(li._first_local_model(), "/a/model1.gguf")

    def test_returns_none_when_no_models(self):
        mm = mock.MagicMock()
        mm.list_models.return_value = []
        li = LocalInference(model_manager=mm)
        self.assertIsNone(li._first_local_model())


if __name__ == "__main__":
    unittest.main()
