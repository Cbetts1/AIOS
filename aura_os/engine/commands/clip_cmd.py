"""``aura clip`` command handler — clipboard operations."""


class ClipCommand:
    """Clipboard management: copy, paste, history, clear."""

    def execute(self, args, eal) -> int:
        from aura_os.kernel.clipboard import ClipboardManager

        clip = ClipboardManager()
        sub = getattr(args, "clip_command", None)

        if sub == "copy":
            text = getattr(args, "text", "")
            result = clip.copy(text)
            if result["ok"]:
                print(f"  ✓ Copied {result['length']} chars "
                      f"(backend: {result['backend']})")
            else:
                print(f"  ✗ Copy failed: {result.get('error', 'unknown')}")
            return 0

        if sub == "paste":
            result = clip.paste()
            if result["ok"]:
                print(result["text"])
            else:
                print(f"  ✗ Paste failed: {result.get('error', 'unknown')}")
            return 0

        if sub == "history":
            limit = getattr(args, "limit", 10)
            items = clip.history(limit)
            if not items:
                print("  Clipboard history is empty")
                return 0
            for i, item in enumerate(items, 1):
                preview = item[:60] + ("..." if len(item) > 60 else "")
                print(f"  {i:>3}. {preview}")
            return 0

        if sub == "clear":
            clip.clear_history()
            print("  ✓ Clipboard history cleared")
            return 0

        # Default: show clipboard info
        info = clip.info()
        print(f"  Backend      : {info['backend']}")
        print(f"  History size : {info['history_size']}/{info['max_history']}")
        return 0
