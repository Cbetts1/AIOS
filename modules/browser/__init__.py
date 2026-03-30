"""
Browser / UI Module
Starts a local Flask web server if available, or renders a terminal dashboard.
"""

import os
import sys
import json
from pathlib import Path


class BrowserModule:
    """
    Provides both a web UI (Flask) and a terminal dashboard fallback.
    Automatically selects the appropriate mode based on environment capabilities.
    """

    def __init__(self, env_map: dict, adapter):
        self.env = env_map
        self.adapter = adapter
        self._aura_home = Path(env_map.get("storage_root", Path.home() / ".aura"))

    # ------------------------------------------------------------------ #
    # Web UI
    # ------------------------------------------------------------------ #

    def start_web(self, host="127.0.0.1", port=7070):
        """Launch a local Flask web server."""
        try:
            from flask import Flask, render_template_string, jsonify, request
        except ImportError:
            raise ImportError("Flask is not installed. Run: pip install flask")

        app = Flask(__name__, template_folder=str(self._aura_home / "ui" / "templates"))

        @app.route("/")
        def index():
            return render_template_string(self._get_html_dashboard())

        @app.route("/api/env")
        def api_env():
            return jsonify(self.env)

        @app.route("/api/files")
        def api_files():
            path = request.args.get("path", str(self._aura_home))
            try:
                entries = self.adapter.list_dir(path)
                return jsonify([{"name": n, "is_dir": d} for n, d in entries])
            except Exception as e:
                return jsonify({"error": str(e)}), 400

        @app.route("/api/run", methods=["POST"])
        def api_run():
            data = request.get_json(force=True) or {}
            cmd = data.get("cmd", "")
            if not cmd:
                return jsonify({"error": "No command provided"}), 400
            rc, out, err = self.adapter.run(cmd, capture=True)
            return jsonify({"returncode": rc, "stdout": out, "stderr": err})

        print(f"\n  AURA Web UI starting at http://{host}:{port}")
        print("  Press Ctrl+C to stop.\n")
        app.run(host=host, port=port, debug=False, use_reloader=False)

    def _get_html_dashboard(self):
        env = self.env
        caps = ", ".join(sorted(env.get("capabilities", [])))
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>AURA OS</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: 'Courier New', monospace; background: #0d1117; color: #c9d1d9; min-height: 100vh; }}
    header {{ background: #161b22; border-bottom: 1px solid #30363d; padding: 1rem 2rem; }}
    header h1 {{ color: #58a6ff; font-size: 1.4rem; }}
    header p {{ color: #8b949e; font-size: .85rem; margin-top: .2rem; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 1rem; padding: 1.5rem; }}
    .card {{ background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 1rem; }}
    .card h2 {{ color: #58a6ff; font-size: .95rem; margin-bottom: .6rem; border-bottom: 1px solid #30363d; padding-bottom: .4rem; }}
    .card p, .card li {{ font-size: .85rem; color: #8b949e; line-height: 1.6; }}
    .card ul {{ padding-left: 1rem; }}
    .badge {{ display: inline-block; background: #21262d; border: 1px solid #30363d; border-radius: 4px;
              padding: 2px 6px; font-size: .75rem; margin: 2px; color: #58a6ff; }}
    .cmd-input {{ width: 100%; background: #0d1117; border: 1px solid #30363d; color: #c9d1d9;
                  padding: .5rem; border-radius: 4px; font-family: inherit; margin-top: .5rem; }}
    .cmd-output {{ margin-top: .5rem; background: #0d1117; border: 1px solid #30363d;
                   border-radius: 4px; padding: .5rem; min-height: 3rem; font-size: .8rem;
                   white-space: pre-wrap; word-break: break-all; }}
    button {{ background: #21262d; border: 1px solid #30363d; color: #c9d1d9; padding: .3rem .8rem;
              border-radius: 4px; cursor: pointer; font-family: inherit; }}
    button:hover {{ background: #30363d; }}
  </style>
</head>
<body>
  <header>
    <h1>⬡ AURA OS</h1>
    <p>Adaptive User-space Runtime Architecture &mdash; {env.get("env_type", "unknown")} environment</p>
  </header>
  <div class="grid">
    <div class="card">
      <h2>System</h2>
      <p>Platform: <strong>{env.get("env_type","?")}</strong></p>
      <p>Termux: <strong>{"yes" if env.get("is_termux") else "no"}</strong></p>
      <p>RAM: <strong>{env.get("ram_mb", 0) or "unknown"} MB</strong></p>
      <p>Network: <strong>{"yes" if env.get("has_network") else "no"}</strong></p>
      <p>Python: <strong>{env.get("python","?")}</strong></p>
    </div>
    <div class="card">
      <h2>Capabilities</h2>
      {''.join(f'<span class="badge">{c}</span>' for c in sorted(env.get("capabilities", [])))}
    </div>
    <div class="card">
      <h2>Quick Commands</h2>
      <ul>
        <li>aura sys info</li>
        <li>aura ai "your question"</li>
        <li>aura fs ls /</li>
        <li>aura repo create myapp</li>
        <li>aura auto list</li>
      </ul>
    </div>
    <div class="card">
      <h2>Run Command</h2>
      <input class="cmd-input" id="cmd" type="text" placeholder='e.g. echo "Hello AURA"'>
      <button onclick="runCmd()" style="margin-top:.4rem">Run</button>
      <div class="cmd-output" id="out">Output will appear here…</div>
    </div>
  </div>
  <script>
    async function runCmd() {{
      const cmd = document.getElementById("cmd").value;
      const out = document.getElementById("out");
      out.textContent = "Running…";
      try {{
        const r = await fetch("/api/run", {{
          method: "POST",
          headers: {{"Content-Type": "application/json"}},
          body: JSON.stringify({{cmd}})
        }});
        const d = await r.json();
        out.textContent = d.stdout + (d.stderr ? "\\nSTDERR: " + d.stderr : "") || "(no output)";
      }} catch(e) {{
        out.textContent = "Error: " + e;
      }}
    }}
    document.getElementById("cmd").addEventListener("keydown", e => {{ if(e.key==="Enter") runCmd(); }});
  </script>
</body>
</html>"""

    # ------------------------------------------------------------------ #
    # Terminal dashboard
    # ------------------------------------------------------------------ #

    def start_terminal(self):
        """Render a colourful terminal-based status dashboard."""
        from aura_os.shell.colors import (
            bold, bright_cyan, cyan, dim, green, header, yellow,
            progress_bar,
        )

        env = self.env
        width = 60

        def line(char="─"):
            return "  " + dim(char * width)

        def row(lbl, value):
            return f"  {bold(lbl):<28} {value}"

        print()
        print(f"  ╔{dim('═' * width)}╗")
        print(f"  ║{header('  ⬡ AURA OS  —  Terminal Dashboard').center(width + 20)}║")
        print(f"  ╚{dim('═' * width)}╝")
        print(line())
        print(row("Platform:", cyan(env.get("env_type", "unknown"))))
        print(row("Termux:", green("yes") if env.get("is_termux") else dim("no")))
        ram = env.get("ram_mb", 0)
        print(row("RAM:", f"{ram} MB" if ram else dim("unknown")))
        print(row("Network:", green("yes") if env.get("has_network") else dim("no")))
        print(row("Storage root:", env.get("storage_root", "?")))
        print(row("Python:", cyan(env.get("python", "?"))))
        print(line())
        caps = sorted(env.get("capabilities", []))
        print(f"  {bold('Capabilities:')}")
        for chunk in [caps[i:i+4] for i in range(0, len(caps), 4)]:
            print("    " + "  ".join(cyan(f"[{c}]") for c in chunk))
        print(line())

        # Available binaries
        binaries = {k: v for k, v in env.get("binaries", {}).items() if v}
        if binaries:
            print(f"  {bold('Available binaries:')}")
            items = sorted(binaries.items())
            for i, (b, _) in enumerate(items):
                end = "\n" if (i + 1) % 4 == 0 else ""
                print(f"    {green(b):<22}", end=end)
            if len(items) % 4 != 0:
                print()
        print(line())
        print(f"  {bold('Quick start:')}")
        print(f"    {cyan('aura help')}              — show all commands")
        print(f"    {cyan('aura ai')} {dim('\"your question\"')} — offline AI assistant")
        print(f"    {cyan('aura sys info')}          — detailed system info")
        print(f"    {cyan('aura fs ls')}             — file browser")
        print(line())
        print()
