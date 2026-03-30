"""Tests for the AI knowledge base module."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from aura_os.ai.knowledge import (
    AURA_COMMANDS,
    LINUX_COMMANDS,
    CODEBASE_ARCHITECTURE,
    build_system_prompt,
    lookup,
)


class TestKnowledgeData(unittest.TestCase):
    """Verify the knowledge base data structures are complete."""

    def test_aura_commands_not_empty(self):
        self.assertGreater(len(AURA_COMMANDS), 0)

    def test_aura_commands_have_required_keys(self):
        for name, info in AURA_COMMANDS.items():
            for key in ("syntax", "description", "details", "examples"):
                self.assertIn(key, info, f"Command '{name}' missing key '{key}'")

    def test_aura_commands_examples_are_lists(self):
        for name, info in AURA_COMMANDS.items():
            self.assertIsInstance(info["examples"], list)
            self.assertGreater(len(info["examples"]), 0, f"'{name}' has no examples")

    def test_all_registered_commands_present(self):
        expected = {"run", "ai", "env", "pkg", "sys", "shell"}
        self.assertEqual(set(AURA_COMMANDS.keys()), expected)

    def test_linux_commands_not_empty(self):
        self.assertGreater(len(LINUX_COMMANDS), 0)

    def test_linux_categories_have_commands(self):
        for category, data in LINUX_COMMANDS.items():
            self.assertIn("description", data)
            self.assertIn("commands", data)
            self.assertGreater(
                len(data["commands"]), 0,
                f"Category '{category}' has no commands"
            )

    def test_linux_commands_have_required_keys(self):
        for category, data in LINUX_COMMANDS.items():
            for cmd in data["commands"]:
                for key in ("name", "syntax", "description", "examples"):
                    self.assertIn(
                        key, cmd,
                        f"Command in '{category}' missing key '{key}'"
                    )

    def test_codebase_architecture_not_empty(self):
        self.assertGreater(len(CODEBASE_ARCHITECTURE), 0)

    def test_codebase_modules_have_required_keys(self):
        for module, info in CODEBASE_ARCHITECTURE.items():
            self.assertIn("purpose", info, f"Module '{module}' missing 'purpose'")
            self.assertIn("key_functions", info, f"Module '{module}' missing 'key_functions'")
            self.assertIsInstance(info["key_functions"], list)


class TestBuildSystemPrompt(unittest.TestCase):
    """Verify the system prompt builder."""

    def test_returns_string(self):
        prompt = build_system_prompt()
        self.assertIsInstance(prompt, str)

    def test_contains_aura_identity(self):
        prompt = build_system_prompt()
        self.assertIn("AURA", prompt)

    def test_contains_aura_commands(self):
        prompt = build_system_prompt()
        for name in AURA_COMMANDS:
            self.assertIn(name, prompt)

    def test_contains_linux_categories(self):
        prompt = build_system_prompt()
        for category in LINUX_COMMANDS:
            self.assertIn(category, prompt)

    def test_contains_codebase_info(self):
        prompt = build_system_prompt()
        self.assertIn("Codebase", prompt)

    def test_prompt_length_reasonable(self):
        prompt = build_system_prompt()
        # Should be substantial but not excessively long
        self.assertGreater(len(prompt), 500)


class TestLookup(unittest.TestCase):
    """Verify the knowledge base lookup function."""

    # --- AURA command lookups ---

    def test_lookup_aura_run(self):
        result = lookup("how do I use the run command")
        self.assertIsNotNone(result)
        self.assertIn("run", result.lower())

    def test_lookup_aura_ai(self):
        result = lookup("tell me about aura ai")
        self.assertIsNotNone(result)
        self.assertIn("ai", result.lower())

    def test_lookup_aura_env(self):
        result = lookup("what does the env command do")
        self.assertIsNotNone(result)
        self.assertIn("env", result.lower())

    def test_lookup_aura_pkg(self):
        result = lookup("how do I use pkg")
        self.assertIsNotNone(result)
        self.assertIn("pkg", result.lower())

    def test_lookup_aura_sys(self):
        result = lookup("tell me about sys")
        self.assertIsNotNone(result)
        self.assertIn("sys", result.lower())

    def test_lookup_aura_shell(self):
        result = lookup("how do I use the shell")
        self.assertIsNotNone(result)
        self.assertIn("shell", result.lower())

    # --- List requests ---

    def test_lookup_list_all_commands(self):
        result = lookup("list all commands")
        self.assertIsNotNone(result)
        self.assertIn("run", result.lower())
        self.assertIn("ai", result.lower())

    def test_lookup_all_aura_commands(self):
        result = lookup("what commands are available")
        self.assertIsNotNone(result)

    def test_lookup_linux_commands_overview(self):
        result = lookup("list linux commands")
        self.assertIsNotNone(result)
        self.assertIn("Category", result)

    # --- Linux command lookups ---

    def test_lookup_grep(self):
        result = lookup("how do I use grep")
        self.assertIsNotNone(result)
        self.assertIn("grep", result.lower())

    def test_lookup_chmod(self):
        result = lookup("how do I use chmod")
        self.assertIsNotNone(result)
        self.assertIn("chmod", result.lower())

    def test_lookup_git_commit(self):
        result = lookup("what is git commit")
        self.assertIsNotNone(result)
        self.assertIn("git", result.lower())

    def test_lookup_curl(self):
        result = lookup("how to use curl")
        self.assertIsNotNone(result)
        self.assertIn("curl", result.lower())

    def test_lookup_tar(self):
        result = lookup("how to use tar")
        self.assertIsNotNone(result)
        self.assertIn("tar", result.lower())

    # --- Category lookups ---

    def test_lookup_networking_category(self):
        result = lookup("tell me about networking commands")
        self.assertIsNotNone(result)
        self.assertIn("Networking", result)

    def test_lookup_process_category(self):
        result = lookup("process management commands")
        self.assertIsNotNone(result)

    # --- Codebase lookups ---

    def test_lookup_codebase(self):
        result = lookup("tell me about the codebase architecture")
        self.assertIsNotNone(result)

    def test_lookup_modules(self):
        result = lookup("what modules are available")
        self.assertIsNotNone(result)

    def test_lookup_eal(self):
        result = lookup("what is the eal")
        self.assertIsNotNone(result)
        self.assertIn("EAL", result)

    def test_lookup_kernel(self):
        result = lookup("tell me about the kernel")
        self.assertIsNotNone(result)

    # --- No match ---

    def test_lookup_no_match_returns_none(self):
        result = lookup("xyzzy plugh")
        self.assertIsNone(result)

    def test_lookup_empty_returns_none(self):
        result = lookup("")
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
