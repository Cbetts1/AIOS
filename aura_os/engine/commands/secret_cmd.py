"""``aura secret`` command handler — secret/credential management."""


class SecretCommand:
    """Secret store management: set, get, delete, list."""

    def execute(self, args, eal) -> int:
        from aura_os.kernel.secrets import SecretStore

        ss = SecretStore()
        sub = getattr(args, "secret_command", None)

        if sub == "set":
            key = getattr(args, "key", "")
            value = getattr(args, "value", "")
            ns = getattr(args, "namespace", "default")
            result = ss.set_secret(key, value, namespace=ns)
            if result["ok"]:
                print(f"  ✓ Secret '{key}' stored in [{ns}]")
            return 0

        if sub == "get":
            key = getattr(args, "key", "")
            ns = getattr(args, "namespace", "default")
            value = ss.get_secret(key, namespace=ns)
            if value is not None:
                print(value)
            else:
                print(f"  ✗ Secret '{key}' not found in [{ns}]")
                return 1
            return 0

        if sub == "delete":
            key = getattr(args, "key", "")
            ns = getattr(args, "namespace", "default")
            if ss.delete_secret(key, namespace=ns):
                print(f"  ✓ Secret '{key}' deleted from [{ns}]")
            else:
                print(f"  ✗ Secret '{key}' not found in [{ns}]")
            return 0

        if sub == "list":
            ns = getattr(args, "namespace", "default")
            secrets = ss.list_secrets(namespace=ns)
            if not secrets:
                print(f"  No secrets in [{ns}]")
                return 0
            print(f"  Secrets in [{ns}]:")
            for s in secrets:
                print(f"    • {s['key']}")
            return 0

        if sub == "namespaces":
            nss = ss.list_namespaces()
            if not nss:
                print("  No namespaces")
                return 0
            for ns in nss:
                print(f"    • {ns}")
            return 0

        # Default: show namespace summary
        nss = ss.list_namespaces()
        print(f"  {len(nss)} namespace(s)")
        for ns in nss:
            count = len(ss.list_secrets(namespace=ns))
            print(f"    {ns}: {count} secret(s)")
        return 0
