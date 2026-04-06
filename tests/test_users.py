"""Tests for aura_os.users.manager.UserManager."""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from aura_os.users.manager import UserManager


class TestUserManagerAddRemove(unittest.TestCase):
    """Create and delete users."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        os.environ["AURA_HOME"] = self.tmpdir
        self.um = UserManager(base_dir=os.path.join(self.tmpdir, "users"))

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_add_user_creates_record(self):
        self.um.add_user("alice", "secret123")
        self.assertTrue(self.um.user_exists("alice"))

    def test_add_user_record_has_required_fields(self):
        self.um.add_user("alice", "secret123")
        record = self.um.get_user("alice")
        self.assertIsNotNone(record)
        for field in ("username", "password_hash", "role", "created_at", "home"):
            self.assertIn(field, record)

    def test_add_user_default_role_is_user(self):
        self.um.add_user("alice", "secret123")
        self.assertEqual(self.um.get_user("alice")["role"], "user")

    def test_add_user_custom_role(self):
        self.um.add_user("admin", "adminpass", role="root")
        self.assertEqual(self.um.get_user("admin")["role"], "root")

    def test_add_user_guest_role(self):
        self.um.add_user("guestuser", "pass", role="guest")
        self.assertEqual(self.um.get_user("guestuser")["role"], "guest")

    def test_add_duplicate_user_raises(self):
        self.um.add_user("alice", "secret123")
        with self.assertRaises(ValueError):
            self.um.add_user("alice", "otherpass")

    def test_remove_user(self):
        self.um.add_user("bob", "bobpass")
        self.um.remove_user("bob")
        self.assertFalse(self.um.user_exists("bob"))

    def test_remove_nonexistent_user_raises(self):
        with self.assertRaises(KeyError):
            self.um.remove_user("nobody")

    def test_list_users_empty(self):
        self.assertEqual(self.um.list_users(), [])

    def test_list_users_excludes_password_hash(self):
        self.um.add_user("alice", "secret")
        self.um.add_user("bob", "secret")
        users = self.um.list_users()
        self.assertEqual(len(users), 2)
        for u in users:
            self.assertNotIn("password_hash", u)

    def test_list_users_sorted(self):
        self.um.add_user("charlie", "c")
        self.um.add_user("alice", "a")
        self.um.add_user("bob", "b")
        names = [u["username"] for u in self.um.list_users()]
        self.assertEqual(names, sorted(names))


class TestUserManagerAuthentication(unittest.TestCase):
    """Password hashing and authentication."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        os.environ["AURA_HOME"] = self.tmpdir
        self.um = UserManager(base_dir=os.path.join(self.tmpdir, "users"))
        self.um.add_user("alice", "correct_password")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_correct_password_authenticates(self):
        self.assertTrue(self.um.authenticate("alice", "correct_password"))

    def test_wrong_password_rejected(self):
        self.assertFalse(self.um.authenticate("alice", "wrong_password"))

    def test_nonexistent_user_returns_false(self):
        self.assertFalse(self.um.authenticate("nobody", "any_password"))

    def test_password_hash_not_plain_text(self):
        record = self.um.get_user("alice")
        self.assertNotEqual(record["password_hash"], "correct_password")

    def test_password_hash_has_salt_separator(self):
        record = self.um.get_user("alice")
        # format is salt_hex:hash_hex
        self.assertIn(":", record["password_hash"])

    def test_two_users_different_hashes(self):
        self.um.add_user("bob", "correct_password")
        alice_hash = self.um.get_user("alice")["password_hash"]
        bob_hash = self.um.get_user("bob")["password_hash"]
        # Same password must produce different hashes due to unique salts
        self.assertNotEqual(alice_hash, bob_hash)

    def test_set_password_success(self):
        result = self.um.set_password("alice", "correct_password", "new_password")
        self.assertTrue(result)
        self.assertTrue(self.um.authenticate("alice", "new_password"))
        self.assertFalse(self.um.authenticate("alice", "correct_password"))

    def test_set_password_wrong_old_fails(self):
        result = self.um.set_password("alice", "wrong_old", "new_password")
        self.assertFalse(result)
        # Password unchanged
        self.assertTrue(self.um.authenticate("alice", "correct_password"))

    def test_set_password_nonexistent_user_raises(self):
        with self.assertRaises(KeyError):
            self.um.set_password("nobody", "old", "new")


class TestUserManagerValidation(unittest.TestCase):
    """Username and role validation."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        os.environ["AURA_HOME"] = self.tmpdir
        self.um = UserManager(base_dir=os.path.join(self.tmpdir, "users"))

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_invalid_username_empty(self):
        with self.assertRaises(ValueError):
            self.um.add_user("", "pass")

    def test_invalid_username_too_long(self):
        with self.assertRaises(ValueError):
            self.um.add_user("a" * 33, "pass")

    def test_invalid_username_spaces(self):
        with self.assertRaises(ValueError):
            self.um.add_user("alice bob", "pass")

    def test_invalid_username_special_chars(self):
        with self.assertRaises(ValueError):
            self.um.add_user("alice@domain", "pass")

    def test_valid_username_with_dash_and_underscore(self):
        self.um.add_user("alice_bob-1", "pass")
        self.assertTrue(self.um.user_exists("alice_bob-1"))

    def test_invalid_role_raises(self):
        with self.assertRaises(ValueError):
            self.um.add_user("alice", "pass", role="superuser")

    def test_all_valid_roles_accepted(self):
        for role in ("root", "user", "guest"):
            username = f"user_{role}"
            self.um.add_user(username, "pass", role=role)
            self.assertEqual(self.um.get_user(username)["role"], role)


class TestUserManagerGetCurrentUser(unittest.TestCase):
    """get_current_user returns a string."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.um = UserManager(base_dir=self.tmpdir)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_get_current_user_returns_string(self):
        user = self.um.get_current_user()
        self.assertIsInstance(user, str)
        self.assertTrue(len(user) > 0)

    def test_aura_user_env_overrides(self):
        os.environ["AURA_USER"] = "test_user"
        try:
            user = self.um.get_current_user()
            self.assertEqual(user, "test_user")
        finally:
            del os.environ["AURA_USER"]


if __name__ == "__main__":
    unittest.main()
