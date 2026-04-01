"""User management command handler for AURA OS."""

import getpass


class UserCommand:
    """Handles the ``user`` sub-command."""

    def execute(self, args, eal) -> int:
        from aura_os.users import UserManager

        um = UserManager()
        sub = args.user_command

        if sub == "list":
            return self._list(um)
        if sub == "add":
            return self._add(um, args)
        if sub == "del":
            return self._del(um, args)
        if sub == "whoami":
            return self._whoami(um)
        if sub == "passwd":
            return self._passwd(um, args)
        if sub == "info":
            return self._info(um, args)
        print(f"user: unknown sub-command '{sub}'")
        return 1

    # ------------------------------------------------------------------

    def _list(self, um) -> int:
        users = um.list_users()
        if not users:
            print("  (no users)")
            return 0
        fmt = "  {:<20} {:<10} {}"
        print(fmt.format("USERNAME", "ROLE", "CREATED"))
        print("  " + "-" * 50)
        for u in users:
            print(fmt.format(u.get("username", ""), u.get("role", ""), u.get("created_at", "")))
        return 0

    def _add(self, um, args) -> int:
        username = args.username
        password = args.password
        if password is None:
            try:
                password = getpass.getpass(f"Password for '{username}': ")
            except (EOFError, KeyboardInterrupt):
                print("\nAborted.")
                return 1
        role = getattr(args, "role", "user")
        try:
            um.add_user(username, password, role=role)
            print(f"User '{username}' created with role '{role}'.")
            return 0
        except Exception as exc:
            print(f"user add: {exc}")
            return 1

    def _del(self, um, args) -> int:
        try:
            um.remove_user(args.username)
            print(f"User '{args.username}' deleted.")
            return 0
        except Exception as exc:
            print(f"user del: {exc}")
            return 1

    def _whoami(self, um) -> int:
        print(um.get_current_user())
        return 0

    def _passwd(self, um, args) -> int:
        username = args.username
        try:
            old_pw = getpass.getpass(f"Current password for '{username}': ")
            new_pw = getpass.getpass(f"New password for '{username}': ")
            confirm = getpass.getpass("Confirm new password: ")
        except (EOFError, KeyboardInterrupt):
            print("\nAborted.")
            return 1
        if new_pw != confirm:
            print("user passwd: passwords do not match.")
            return 1
        try:
            ok = um.set_password(username, old_pw, new_pw)
        except Exception as exc:
            print(f"user passwd: {exc}")
            return 1
        if ok:
            print(f"Password for '{username}' updated.")
            return 0
        print("user passwd: incorrect current password.")
        return 1

    def _info(self, um, args) -> int:
        record = um.get_user(args.username)
        if record is None:
            print(f"user info: user '{args.username}' not found.")
            return 1
        for key, value in record.items():
            if key == "password_hash":
                continue
            print(f"  {key:<15} {value}")
        return 0
