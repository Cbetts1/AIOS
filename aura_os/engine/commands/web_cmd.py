"""``aura web`` command handler — web API / dashboard server."""


class WebCommand:
    """Start the AURA OS web API server."""

    def execute(self, args, eal) -> int:
        from aura_os.web import WebServer, DEFAULT_PORT

        host = getattr(args, "host", "127.0.0.1")
        port = getattr(args, "port", DEFAULT_PORT)

        server = WebServer(eal, host=host, port=port)
        try:
            server.start(background=False)
        except KeyboardInterrupt:
            print("\n[aura web] Server stopped.")
        return 0
