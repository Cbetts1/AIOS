"""Command Center — lightweight web API for remote / cloud access.

Provides a JSON REST API and a minimal HTML dashboard so Aura and the
Command Center can be accessed from a web browser, a cloud VM, or any
HTTP client.  The user can later host this on a server to access their
OS remotely.

Endpoints
---------
GET  /                  HTML dashboard
GET  /api/status        System status JSON
GET  /api/aura          Aura persona JSON
POST /api/aura/chat     Send a message to Aura  {"prompt": "..."}
GET  /api/services      Services list JSON
GET  /api/processes     Process list JSON
GET  /api/logs          Recent logs JSON
GET  /api/sessions      List saved sessions
GET  /api/sessions/<id> Get a session by ID

The server is intentionally simple (standard-library ``http.server``)
so it works without Flask.  If Flask is available it will be preferred.
"""

from __future__ import annotations

import json
import os
import platform
import shutil
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Any, Dict, Optional

# ── HTML template (self-contained) ──────────────────────────────────
_HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>AURA OS — Command Center</title>
<style>
  :root { --bg: #0d1117; --card: #161b22; --border: #30363d;
          --text: #c9d1d9; --accent: #58a6ff; --green: #3fb950;
          --red: #f85149; --purple: #bc8cff; }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: 'Segoe UI', system-ui, sans-serif;
         background: var(--bg); color: var(--text); }
  header { background: linear-gradient(135deg, #1a1028, #0d1117);
           padding: 1.5rem 2rem; border-bottom: 1px solid var(--border); }
  header h1 { color: var(--purple); font-size: 1.5rem; }
  header p  { color: var(--text); opacity: .7; font-size: .85rem; }
  .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(340px, 1fr));
          gap: 1rem; padding: 1.5rem 2rem; }
  .card { background: var(--card); border: 1px solid var(--border);
          border-radius: 8px; padding: 1rem; }
  .card h2 { font-size: 1rem; color: var(--accent); margin-bottom: .75rem;
             border-bottom: 1px solid var(--border); padding-bottom: .4rem; }
  .card pre { white-space: pre-wrap; font-size: .82rem; line-height: 1.6; }
  .status-ok { color: var(--green); } .status-err { color: var(--red); }
  #chat-box { max-height: 220px; overflow-y: auto; margin-bottom: .5rem; }
  #chat-box .msg { padding: 4px 0; font-size: .85rem; }
  #chat-box .user { color: var(--accent); }
  #chat-box .aura { color: var(--purple); }
  #chat-input { width: 100%; padding: .5rem; border-radius: 6px;
                border: 1px solid var(--border); background: var(--bg);
                color: var(--text); font-size: .85rem; }
</style>
</head>
<body>
<header>
  <h1>✦ AURA OS — Command Center</h1>
  <p>Manage your OS and talk to Aura from anywhere.</p>
</header>
<div class="grid">
  <div class="card" id="sys-card">
    <h2>⚙ System Status</h2><pre id="sys-pre">Loading…</pre>
  </div>
  <div class="card" id="aura-card">
    <h2>🤖 Aura AI</h2><pre id="aura-pre">Loading…</pre>
    <div id="chat-box"></div>
    <input id="chat-input" placeholder="Ask Aura anything…" autocomplete="off"/>
  </div>
  <div class="card" id="svc-card">
    <h2>🔧 Services</h2><pre id="svc-pre">Loading…</pre>
  </div>
  <div class="card" id="log-card">
    <h2>📋 Logs</h2><pre id="log-pre">Loading…</pre>
  </div>
</div>
<script>
async function load(url, el) {
  try {
    const r = await fetch(url);
    const d = await r.json();
    document.getElementById(el).textContent = JSON.stringify(d, null, 2);
  } catch(e) { document.getElementById(el).textContent = 'Error: ' + e; }
}
function refresh() {
  load('/api/status', 'sys-pre');
  load('/api/aura', 'aura-pre');
  load('/api/services', 'svc-pre');
  load('/api/logs', 'log-pre');
}
refresh();
setInterval(refresh, 10000);

const chatInput = document.getElementById('chat-input');
const chatBox = document.getElementById('chat-box');
chatInput.addEventListener('keydown', async (e) => {
  if (e.key !== 'Enter' || !chatInput.value.trim()) return;
  const msg = chatInput.value.trim();
  chatInput.value = '';
  chatBox.innerHTML += '<div class="msg user">You: ' + msg + '</div>';
  try {
    const r = await fetch('/api/aura/chat', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({prompt: msg})
    });
    const d = await r.json();
    chatBox.innerHTML += '<div class="msg aura">Aura: ' + (d.response || d.error) + '</div>';
  } catch(err) {
    chatBox.innerHTML += '<div class="msg aura">Aura: (error: ' + err + ')</div>';
  }
  chatBox.scrollTop = chatBox.scrollHeight;
});
</script>
</body>
</html>
"""


def _json_response(handler: BaseHTTPRequestHandler, data: Any, status: int = 200) -> None:
    body = json.dumps(data, indent=2, default=str).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _html_response(handler: BaseHTTPRequestHandler, html: str) -> None:
    body = html.encode("utf-8")
    handler.send_response(200)
    handler.send_header("Content-Type", "text/html; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _read_body(handler: BaseHTTPRequestHandler) -> dict:
    length = int(handler.headers.get("Content-Length", 0))
    raw = handler.rfile.read(length) if length else b"{}"
    return json.loads(raw)


# ── request handler ─────────────────────────────────────────────────

def _make_handler(eal):
    """Create a request-handler class closed over *eal*."""

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            """Suppress default stderr logging."""
            pass

        def do_GET(self):
            path = self.path.rstrip("/") or "/"

            if path == "/":
                _html_response(self, _HTML_TEMPLATE)
                return

            if path == "/api/status":
                _json_response(self, _get_status())
                return

            if path == "/api/aura":
                _json_response(self, _get_aura_info())
                return

            if path == "/api/services":
                _json_response(self, _get_services())
                return

            if path == "/api/processes":
                _json_response(self, _get_processes())
                return

            if path == "/api/logs":
                _json_response(self, _get_logs())
                return

            if path == "/api/sessions":
                _json_response(self, _get_sessions())
                return

            if path.startswith("/api/sessions/"):
                sid = path.split("/")[-1]
                _json_response(self, _get_session(sid))
                return

            self.send_error(404, "Not Found")

        def do_POST(self):
            if self.path.rstrip("/") == "/api/aura/chat":
                body = _read_body(self)
                prompt = body.get("prompt", "")
                resp = _chat(prompt)
                _json_response(self, resp)
                return
            self.send_error(404, "Not Found")

    return Handler


# ── data helpers (used by both TUI and web) ─────────────────────────

def _get_status() -> dict:
    uname = platform.uname()
    info: Dict[str, Any] = {
        "os": uname.system,
        "release": uname.release,
        "host": uname.node,
        "arch": uname.machine,
        "python": platform.python_version(),
    }
    try:
        from aura_os.kernel.memory import MemoryTracker
        info["memory"] = MemoryTracker().get_system_memory()
    except Exception:
        info["memory"] = None
    try:
        usage = shutil.disk_usage("/")
        info["disk"] = {
            "total_gb": round(usage.total / (1024 ** 3), 2),
            "used_gb": round(usage.used / (1024 ** 3), 2),
            "free_gb": round(usage.free / (1024 ** 3), 2),
        }
    except Exception:
        info["disk"] = None
    return info


def _get_aura_info() -> dict:
    from aura_os.ai.aura import AuraPersona
    persona = AuraPersona.load()
    info = persona.to_dict()
    try:
        from aura_os.ai.model_manager import ModelManager
        mm = ModelManager()
        info["active_runtime"] = mm.get_active_runtime()
        info["local_models"] = len(mm.list_models())
    except Exception:
        info["active_runtime"] = None
        info["local_models"] = 0
    return info


def _get_services() -> list:
    try:
        from aura_os.kernel.service import ServiceManager
        sm = ServiceManager()
        return [
            {"name": s.name, "status": s.status, "pid": s.pid}
            for s in sm.list()
        ]
    except Exception:
        return []


def _get_processes() -> list:
    try:
        from aura_os.kernel.process import ProcessManager
        pm = ProcessManager()
        return [
            {"pid": p.pid, "name": p.name, "status": p.status}
            for p in pm.list()
        ]
    except Exception:
        return []


def _get_logs() -> list:
    try:
        from aura_os.kernel.syslog import Syslog
        return Syslog().get_entries(limit=20)
    except Exception:
        return []


def _get_sessions() -> list:
    try:
        from aura_os.ai.session import SessionManager
        return SessionManager().list_sessions()
    except Exception:
        return []


def _get_session(session_id: str) -> dict:
    try:
        from aura_os.ai.session import SessionManager
        sm = SessionManager()
        data = sm.export_session(session_id)
        return data if data else {"error": "session not found"}
    except Exception as exc:
        return {"error": str(exc)}


def _chat(prompt: str) -> dict:
    """Process a chat prompt through Aura."""
    if not prompt:
        return {"error": "empty prompt"}
    try:
        from aura_os.ai.aura import AuraPersona
        from aura_os.ai.inference import LocalInference
        from aura_os.ai.model_manager import ModelManager
        persona = AuraPersona.load()
        mm = ModelManager()
        inference = LocalInference(model_manager=mm)
        full = f"[System: {persona.build_system_prompt()}]\nUser: {prompt}\nAura:"
        response = inference.query(full)
        return {"response": response}
    except Exception as exc:
        return {"response": (
            "I'm not connected to an AI backend right now.  "
            "Install ollama to unlock my full potential."
        )}


# ── public API ──────────────────────────────────────────────────────

def create_app(eal, host: str = "127.0.0.1", port: int = 7070) -> HTTPServer:
    """Create and return an HTTPServer (not yet started)."""
    handler_cls = _make_handler(eal)
    server = HTTPServer((host, port), handler_cls)
    return server


def serve(eal, host: str = "127.0.0.1", port: int = 7070) -> None:
    """Start the Command Center web server (blocking)."""
    server = create_app(eal, host, port)
    print(f"[aura] Command Center web UI: http://{host}:{port}")
    print("[aura] Press Ctrl-C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[aura] Web server stopped.")
    finally:
        server.server_close()
