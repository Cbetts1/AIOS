"""Web API / dashboard server for AURA OS.

Provides a minimal HTTP REST API for inspecting and interacting with AURA OS
remotely.  Uses Flask when available; falls back to the Python stdlib
``http.server`` when Flask is not installed.

REST endpoints:
  GET  /api/status   — EAL environment info
  GET  /api/ps       — running processes
  GET  /api/log      — recent syslog entries
  POST /api/ai       — query the local AI (JSON body: {"prompt": "..."})
"""

import json
import os
import sys
import threading
from typing import Optional


DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 7070


# ---------------------------------------------------------------------------
# Helpers shared by both backends
# ---------------------------------------------------------------------------

def _get_status(eal) -> dict:
    """Return the EAL environment info dict."""
    try:
        return eal.get_env_info()
    except Exception:
        return {"error": "Failed to retrieve environment info"}


def _get_ps() -> list:
    """Return a list of tracked AURA processes."""
    try:
        from aura_os.kernel.process import ProcessManager
        pm = ProcessManager()
        return pm.list_processes()
    except Exception:
        return []


def _get_log(lines: int = 50) -> list:
    """Return recent syslog entries."""
    try:
        from aura_os.kernel.syslog import Syslog
        return Syslog().tail(lines)
    except Exception:
        return []


def _query_ai(prompt: str, model: Optional[str] = None) -> str:
    """Query the local AI and return the response string."""
    try:
        from aura_os.ai.inference import LocalInference
        return LocalInference().query(prompt, model=model)
    except Exception:
        return "[aura ai] Error: inference failed"


# ---------------------------------------------------------------------------
# Flask backend (preferred)
# ---------------------------------------------------------------------------

def _try_flask(eal, host: str, port: int):
    """Start a Flask development server.  Returns True if Flask is available."""
    try:
        from flask import Flask, jsonify, request  # type: ignore
    except ImportError:
        return False

    app = Flask("aura_os_web")

    @app.route("/api/status")
    def api_status():
        return jsonify(_get_status(eal))

    @app.route("/api/ps")
    def api_ps():
        return jsonify(_get_ps())

    @app.route("/api/log")
    def api_log():
        n = int(request.args.get("n", 50))
        return jsonify(_get_log(n))

    @app.route("/api/ai", methods=["POST"])
    def api_ai():
        body = request.get_json(force=True, silent=True) or {}
        prompt = body.get("prompt", "")
        model = body.get("model", None)
        if not prompt:
            return jsonify({"error": "Missing 'prompt' field"}), 400
        return jsonify({"response": _query_ai(prompt, model)})

    print(f"[aura web] Flask server starting on http://{host}:{port}")
    app.run(host=host, port=port, debug=False, use_reloader=False)
    return True


# ---------------------------------------------------------------------------
# stdlib HTTP fallback
# ---------------------------------------------------------------------------

class _StdlibHandler:
    """Minimal HTTP/1.1 handler backed by Python's http.server."""

    def __init__(self, eal):
        self._eal = eal

    def build_handler(self):
        eal = self._eal

        from http.server import BaseHTTPRequestHandler

        class _Handler(BaseHTTPRequestHandler):
            def log_message(self, format, *args):  # noqa: A002
                pass  # suppress default access log

            def _send_json(self, data, status: int = 200):
                body = json.dumps(data).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):  # noqa: N802
                path = self.path.split("?")[0]
                if path == "/api/status":
                    self._send_json(_get_status(eal))
                elif path == "/api/ps":
                    self._send_json(_get_ps())
                elif path == "/api/log":
                    self._send_json(_get_log())
                else:
                    self._send_json({"error": "Not found"}, 404)

            def do_POST(self):  # noqa: N802
                if self.path == "/api/ai":
                    length = int(self.headers.get("Content-Length", 0))
                    raw = self.rfile.read(length)
                    try:
                        body = json.loads(raw)
                    except Exception:
                        body = {}
                    prompt = body.get("prompt", "")
                    model = body.get("model", None)
                    if not prompt:
                        self._send_json({"error": "Missing 'prompt' field"}, 400)
                        return
                    self._send_json({"response": _query_ai(prompt, model)})
                else:
                    self._send_json({"error": "Not found"}, 404)

        return _Handler


def _start_stdlib(eal, host: str, port: int):
    """Start a stdlib HTTP server."""
    from http.server import HTTPServer

    handler = _StdlibHandler(eal).build_handler()
    server = HTTPServer((host, port), handler)
    print(f"[aura web] stdlib HTTP server starting on http://{host}:{port}")
    server.serve_forever()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

class WebServer:
    """AURA OS web API server.

    Tries Flask first; falls back to stdlib ``http.server``.
    """

    def __init__(self, eal, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT):
        self._eal = eal
        self._host = host
        self._port = port

    def start(self, background: bool = False):
        """Start the server.

        Args:
            background: If True, run in a daemon thread and return immediately.
        """
        if background:
            t = threading.Thread(target=self._serve, daemon=True)
            t.start()
            return t
        self._serve()

    def _serve(self):
        if not _try_flask(self._eal, self._host, self._port):
            _start_stdlib(self._eal, self._host, self._port)
