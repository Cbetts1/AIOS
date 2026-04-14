"""Web API / dashboard server for AURA OS.

Provides an HTTP REST API *and* a mobile-friendly HTML dashboard for
inspecting and interacting with AURA OS remotely.  Uses Flask when
available; falls back to the Python stdlib ``http.server`` when Flask
is not installed.

REST endpoints:
  GET  /            — Mobile-friendly HTML dashboard
  GET  /api/status  — EAL environment info (JSON)
  GET  /api/ps      — running processes (JSON)
  GET  /api/log     — recent syslog entries (JSON)
  GET  /api/health  — system health summary (JSON)
  POST /api/ai      — query the local AI (JSON body: {"prompt": "..."})
  POST /api/shell   — run a built-in shell command (JSON body: {"cmd": "..."})
"""

import json
import os
import threading
from typing import Optional


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 7070

# ---------------------------------------------------------------------------
# Mobile-friendly dashboard HTML
# ---------------------------------------------------------------------------

_DASHBOARD_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1">
<title>AURA OS Dashboard</title>
<style>
  :root {
    --bg: #0d1117; --card: #161b22; --border: #30363d;
    --text: #c9d1d9; --muted: #8b949e; --accent: #58a6ff;
    --ok: #3fb950; --warn: #d29922; --err: #f85149;
    --radius: 8px; --font: 'Segoe UI', system-ui, -apple-system, sans-serif;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: var(--bg); color: var(--text); font-family: var(--font);
         font-size: 14px; padding: 12px; }
  h1 { font-size: 1.2rem; color: var(--accent); margin-bottom: 4px; }
  .subtitle { color: var(--muted); font-size: 0.8rem; margin-bottom: 16px; }
  .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
          gap: 12px; }
  .card { background: var(--card); border: 1px solid var(--border);
          border-radius: var(--radius); padding: 14px; }
  .card-title { font-weight: 600; font-size: 0.85rem; color: var(--muted);
                text-transform: uppercase; letter-spacing: .05em; margin-bottom: 10px;
                display: flex; justify-content: space-between; align-items: center; }
  .badge { font-size: 0.7rem; padding: 2px 7px; border-radius: 20px; font-weight: 500; }
  .badge-ok   { background: #1a4023; color: var(--ok); }
  .badge-warn { background: #3d2c00; color: var(--warn); }
  .badge-err  { background: #3d0c0c; color: var(--err); }
  .metric { display: flex; justify-content: space-between; align-items: center;
            padding: 5px 0; border-bottom: 1px solid var(--border); }
  .metric:last-child { border-bottom: none; }
  .metric-label { color: var(--muted); }
  .metric-value { font-family: monospace; font-size: 0.9rem; }
  .bar-wrap { width: 100px; height: 8px; background: var(--border);
              border-radius: 4px; overflow: hidden; }
  .bar-fill { height: 100%; background: var(--accent); border-radius: 4px;
              transition: width .4s; }
  .bar-fill.warn { background: var(--warn); }
  .bar-fill.err  { background: var(--err); }
  pre.log { background: #0a0e14; border: 1px solid var(--border); border-radius: 4px;
            padding: 8px; font-size: 0.75rem; max-height: 200px; overflow-y: auto;
            white-space: pre-wrap; word-break: break-all; color: var(--text); }
  .proc-row { display: flex; justify-content: space-between; padding: 4px 0;
              border-bottom: 1px solid var(--border); font-size: 0.82rem; }
  .proc-row:last-child { border-bottom: none; }
  .proc-pid { color: var(--muted); min-width: 40px; }
  .proc-cmd { flex: 1; padding: 0 8px; overflow: hidden;
              text-overflow: ellipsis; white-space: nowrap; }
  .proc-cpu { color: var(--accent); min-width: 40px; text-align: right; }
  #ai-box { display: flex; gap: 8px; margin-bottom: 8px; flex-wrap: wrap; }
  #ai-input { flex: 1; min-width: 180px; background: var(--bg); border: 1px solid var(--border);
              border-radius: 4px; padding: 8px 10px; color: var(--text); font-size: 0.85rem; }
  #ai-input:focus { outline: none; border-color: var(--accent); }
  button { background: var(--accent); color: #0d1117; border: none; border-radius: 4px;
           padding: 8px 16px; cursor: pointer; font-weight: 600; font-size: 0.85rem; }
  button:hover { opacity: .85; }
  button.secondary { background: var(--card); color: var(--text);
                     border: 1px solid var(--border); }
  #ai-response { background: #0a0e14; border: 1px solid var(--border); border-radius: 4px;
                 padding: 10px; min-height: 60px; font-size: 0.82rem;
                 white-space: pre-wrap; word-break: break-all; }
  .status-dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; margin-right: 5px; }
  .dot-ok   { background: var(--ok); }
  .dot-warn { background: var(--warn); }
  .dot-err  { background: var(--err); }
  .refresh-row { display: flex; align-items: center; gap: 8px; margin-bottom: 12px; flex-wrap: wrap; }
  .last-updated { font-size: 0.75rem; color: var(--muted); }
  @media (max-width: 400px) {
    body { padding: 8px; }
    .grid { grid-template-columns: 1fr; }
  }
</style>
</head>
<body>
<h1>⬡ AURA OS</h1>
<div class="subtitle" id="platform-line">Adaptive User-space Runtime Architecture</div>

<div class="refresh-row">
  <button onclick="refreshAll()">⟳ Refresh</button>
  <button class="secondary" id="auto-btn" onclick="toggleAuto()">Auto: OFF</button>
  <span class="last-updated" id="last-updated"></span>
</div>

<div class="grid">

  <!-- Status card -->
  <div class="card">
    <div class="card-title">System Status <span id="health-badge" class="badge badge-ok">—</span></div>
    <div id="status-metrics"></div>
  </div>

  <!-- Processes card -->
  <div class="card">
    <div class="card-title">Processes <span id="proc-count" class="badge badge-ok">—</span></div>
    <div id="proc-list"></div>
  </div>

  <!-- Log card -->
  <div class="card">
    <div class="card-title">System Log</div>
    <pre class="log" id="log-view">Loading…</pre>
  </div>

  <!-- AI assistant card -->
  <div class="card">
    <div class="card-title">AI Assistant</div>
    <div id="ai-box">
      <input id="ai-input" type="text" placeholder="Ask AURA something…"
             onkeydown="if(event.key==='Enter')askAI()">
      <button onclick="askAI()">Ask</button>
    </div>
    <div id="ai-response" class="muted">Ask anything about your system…</div>
  </div>

</div>

<script>
'use strict';

let _autoInterval = null;

function toggleAuto() {
  const btn = document.getElementById('auto-btn');
  if (_autoInterval) {
    clearInterval(_autoInterval);
    _autoInterval = null;
    btn.textContent = 'Auto: OFF';
  } else {
    _autoInterval = setInterval(refreshAll, 5000);
    btn.textContent = 'Auto: ON';
    btn.style.background = 'var(--ok)';
  }
}

async function apiFetch(url, opts) {
  try {
    const r = await fetch(url, opts);
    return await r.json();
  } catch(e) { return null; }
}

async function loadStatus() {
  const data = await apiFetch('/api/status');
  if (!data) return;
  const sys = data.system || {};
  const plat = data.platform || 'unknown';
  document.getElementById('platform-line').textContent =
    'Platform: ' + plat + (sys.hostname ? '  |  Host: ' + sys.hostname : '');
  const metrics = document.getElementById('status-metrics');
  const rows = [];

  // CPU
  if (sys.cpu_percent !== undefined) {
    const pct = sys.cpu_percent;
    const cls = pct > 90 ? 'err' : pct > 70 ? 'warn' : '';
    rows.push(metricBar('CPU', pct.toFixed(1) + '%', pct, cls));
  }
  // Memory
  if (sys.memory_percent !== undefined) {
    const pct = sys.memory_percent;
    const cls = pct > 90 ? 'err' : pct > 70 ? 'warn' : '';
    rows.push(metricBar('Memory', pct.toFixed(1) + '%', pct, cls));
  }
  // Disk
  if (sys.disk_percent !== undefined) {
    const pct = sys.disk_percent;
    const cls = pct > 90 ? 'err' : pct > 70 ? 'warn' : '';
    rows.push(metricBar('Disk', pct.toFixed(1) + '%', pct, cls));
  }
  // Uptime
  if (sys.uptime_human) rows.push(metricText('Uptime', sys.uptime_human));
  // Python
  if (data.system && data.system.python) rows.push(metricText('Python', data.system.python));
  // pkg manager
  if (data.pkg_manager) rows.push(metricText('Pkg manager', data.pkg_manager));

  metrics.innerHTML = rows.join('') || '<div class="metric"><span class="metric-label muted">No data</span></div>';
}

function metricBar(label, valText, pct, cls) {
  return '<div class="metric"><span class="metric-label">' + label + '</span>'
    + '<div style="display:flex;align-items:center;gap:8px">'
    + '<span class="metric-value">' + valText + '</span>'
    + '<div class="bar-wrap"><div class="bar-fill ' + cls + '" style="width:' + Math.min(pct,100) + '%"></div></div>'
    + '</div></div>';
}
function metricText(label, val) {
  return '<div class="metric"><span class="metric-label">' + label + '</span>'
    + '<span class="metric-value">' + val + '</span></div>';
}

async function loadProcesses() {
  const data = await apiFetch('/api/ps');
  const el = document.getElementById('proc-list');
  const cnt = document.getElementById('proc-count');
  if (!data || !Array.isArray(data)) { el.innerHTML = '<div class="muted">No data</div>'; return; }
  cnt.textContent = data.length;
  if (!data.length) { el.innerHTML = '<div class="metric"><span class="metric-label muted">No processes tracked</span></div>'; return; }
  el.innerHTML = data.slice(0, 20).map(p =>
    '<div class="proc-row">'
    + '<span class="proc-pid">' + (p.pid || '?') + '</span>'
    + '<span class="proc-cmd">' + esc(p.name || p.cmd || 'unknown') + '</span>'
    + '<span class="proc-cpu">' + (p.cpu_percent !== undefined ? p.cpu_percent.toFixed(1) + '%' : '') + '</span>'
    + '</div>'
  ).join('');
}

async function loadLog() {
  const data = await apiFetch('/api/log?n=30');
  const el = document.getElementById('log-view');
  if (!data || !Array.isArray(data)) { el.textContent = 'No log data'; return; }
  if (!data.length) { el.textContent = '(empty)'; return; }
  el.textContent = data.slice(-30).map(e => {
    const ts = e.timestamp || '';
    const lvl = (e.level || 'info').toUpperCase().padEnd(5);
    const src = e.source || '';
    const msg = e.message || JSON.stringify(e);
    return '[' + ts.slice(11,19) + '] ' + lvl + ' ' + src + ' ' + msg;
  }).join('\\n');
  el.scrollTop = el.scrollHeight;
}

async function loadHealth() {
  const data = await apiFetch('/api/health');
  const badge = document.getElementById('health-badge');
  if (!data) return;
  const score = data.score !== undefined ? data.score : 100;
  if (score >= 80) { badge.className = 'badge badge-ok'; badge.textContent = score + '/100'; }
  else if (score >= 50) { badge.className = 'badge badge-warn'; badge.textContent = score + '/100'; }
  else { badge.className = 'badge badge-err'; badge.textContent = score + '/100'; }
}

async function askAI() {
  const input = document.getElementById('ai-input');
  const resp = document.getElementById('ai-response');
  const prompt = input.value.trim();
  if (!prompt) return;
  resp.textContent = '⏳ Thinking…';
  const data = await apiFetch('/api/ai', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({prompt})
  });
  if (data && data.response) {
    resp.textContent = data.response;
  } else if (data && data.error) {
    resp.textContent = '⚠ ' + data.error;
  } else {
    resp.textContent = '⚠ No response';
  }
}

function esc(s) {
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

function refreshAll() {
  loadStatus();
  loadProcesses();
  loadLog();
  loadHealth();
  document.getElementById('last-updated').textContent =
    'Updated ' + new Date().toLocaleTimeString();
}

refreshAll();
</script>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Helpers shared by both backends
# ---------------------------------------------------------------------------

def _get_status(eal) -> dict:
    """Return the EAL environment info dict, enriched with live metrics."""
    try:
        info = eal.get_env_info()
    except Exception:
        info = {"error": "Failed to retrieve environment info"}

    # Enrich with live psutil metrics when available
    sys_data = info.setdefault("system", {})
    try:
        import psutil
        import time
        sys_data["cpu_percent"] = psutil.cpu_percent(interval=0.1)
        mem = psutil.virtual_memory()
        sys_data["memory_percent"] = mem.percent
        disk = psutil.disk_usage("/")
        sys_data["disk_percent"] = disk.percent
        boot = psutil.boot_time()
        secs = time.time() - boot
        h = int(secs // 3600)
        m = int((secs % 3600) // 60)
        sys_data["uptime_human"] = f"{h}h {m}m"
        sys_data["python"] = f"{__import__('sys').version.split()[0]}"
    except ImportError:
        pass
    except Exception:
        pass

    return info


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


def _get_health() -> dict:
    """Return a simple health score dict."""
    try:
        import psutil
        cpu = psutil.cpu_percent(interval=0.1)
        mem = psutil.virtual_memory().percent
        disk = psutil.disk_usage("/").percent
        worst = max(cpu, mem, disk)
        if worst < 70:
            score = 100
        elif worst < 85:
            score = 75
        elif worst < 95:
            score = 50
        else:
            score = 25
        return {"score": score, "cpu": cpu, "memory": mem, "disk": disk}
    except ImportError:
        return {"score": 100, "note": "psutil not installed"}
    except Exception:
        return {"score": 100}


def _query_ai(prompt: str, model: Optional[str] = None) -> str:
    """Query the local AI and return the response string."""
    try:
        from aura_os.ai.inference import LocalInference  # noqa: PLC0415
        return LocalInference().query(prompt, model=model)
    except Exception:  # noqa: BLE001
        return "[aura ai] Error: inference failed"


# ---------------------------------------------------------------------------
# Flask backend (preferred)
# ---------------------------------------------------------------------------

def _try_flask(eal, host: str, port: int):
    """Start a Flask development server.  Returns True if Flask is available."""
    try:
        from flask import Flask, jsonify, request, Response  # type: ignore
    except ImportError:
        return False

    app = Flask("aura_os_web")

    @app.route("/")
    def index():
        return Response(_DASHBOARD_HTML, mimetype="text/html")

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

    @app.route("/api/health")
    def api_health():
        return jsonify(_get_health())

    @app.route("/api/ai", methods=["POST"])
    def api_ai():
        body = request.get_json(force=True, silent=True) or {}
        prompt = body.get("prompt", "")
        model = body.get("model", None)
        if not prompt:
            return jsonify({"error": "Missing 'prompt' field"}), 400
        return jsonify({"response": _query_ai(prompt, model)})

    print(f"[aura web] Flask dashboard → http://{host}:{port}")
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

            def _send_html(self, html: str):
                body = html.encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):  # noqa: N802
                path = self.path.split("?")[0]
                query = self.path[len(path):]
                if path in ("/", "/index.html"):
                    self._send_html(_DASHBOARD_HTML)
                elif path == "/api/status":
                    self._send_json(_get_status(eal))
                elif path == "/api/ps":
                    self._send_json(_get_ps())
                elif path == "/api/log":
                    n = 50
                    if "n=" in query:
                        try:
                            n = int(query.split("n=")[1].split("&")[0])
                        except (ValueError, IndexError):
                            pass
                    self._send_json(_get_log(n))
                elif path == "/api/health":
                    self._send_json(_get_health())
                else:
                    self._send_json({"error": "Not found"}, 404)

            def do_POST(self):  # noqa: N802
                if self.path == "/api/ai":
                    length = int(self.headers.get("Content-Length", 0))
                    raw = self.rfile.read(length)
                    try:
                        body = json.loads(raw)
                    except (json.JSONDecodeError, ValueError):
                        self._send_json({"error": "Invalid JSON body"}, 400)
                        return
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
    print(f"[aura web] Dashboard → http://{host}:{port}")
    server.serve_forever()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

class WebServer:
    """AURA OS web API server.

    Tries Flask first; falls back to stdlib ``http.server``.
    Opens a mobile-friendly dashboard at ``/`` in addition to the REST API.
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
