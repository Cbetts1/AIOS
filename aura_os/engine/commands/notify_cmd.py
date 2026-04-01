"""``aura notify`` command handler — notifications and events."""


class NotifyCommand:
    """Notification management: send, list, read, clear."""

    def execute(self, args, eal) -> int:
        from aura_os.kernel.events import NotificationManager

        nm = NotificationManager()
        sub = getattr(args, "notify_command", None)

        if sub == "send":
            title = getattr(args, "title", "")
            body = getattr(args, "body", "")
            level = getattr(args, "level", "info")
            notif = nm.send(title, body, level)
            print(f"  ✓ Notification sent: {notif['id']}")
            return 0

        if sub == "list":
            unread = getattr(args, "unread", False)
            items = nm.list_all(unread_only=unread)
            if not items:
                print("  No notifications")
                return 0
            for n in items:
                marker = "●" if not n["read"] else "○"
                lvl = n["level"].upper()
                print(f"  {marker} [{lvl:>7}] {n['title']}")
                if n["body"]:
                    print(f"             {n['body']}")
                print(f"             id={n['id']}")
            return 0

        if sub == "read":
            nid = getattr(args, "id", "")
            if nm.mark_read(nid):
                print(f"  ✓ Marked {nid} as read")
            else:
                print(f"  ✗ Notification {nid} not found")
            return 0

        if sub == "clear":
            nm.clear()
            print("  ✓ All notifications cleared")
            return 0

        # Default: show unread count
        count = nm.unread_count()
        print(f"  {count} unread notification(s)")
        return 0
