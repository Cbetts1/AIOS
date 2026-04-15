"""
Capability Forge OS — Flask HTTP API (v1 prototype).

Endpoints:
  POST /route        — route an intent and return the result
  GET  /capabilities — list all registered capabilities
  GET  /status       — registry / generated / log counts
  GET  /logs         — recent log entries
  POST /generate     — force-generate a capability from an intent
"""

import sys
import os

# Allow running from the repo root: python3 api.py
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask, jsonify, request

from core.executor import CapabilityExecutor
from core.generator import CapabilityGenerator
from core.logger import CapabilityLogger
from core.registry import CapabilityRegistry
from core.router import CapabilityRouter

app = Flask(__name__)

# Shared singletons
registry = CapabilityRegistry()
registry.load()

router = CapabilityRouter()
executor = CapabilityExecutor()
generator = CapabilityGenerator()
logger = CapabilityLogger()


# ---------------------------------------------------------------------------
# POST /route
# ---------------------------------------------------------------------------

@app.route("/route", methods=["POST"])
def route_intent():
    body = request.get_json(silent=True) or {}
    intent = (body.get("intent") or "").strip()
    if not intent:
        return jsonify({"error": "intent is required"}), 400

    capability, needs_generation = router.route(intent, registry.all())

    if needs_generation:
        capability = generator.generate(intent, existing_ids=set(registry.ids()))
        registry.add(capability)
        logger.log_generated(intent, capability.id)
        was_generated = True
    else:
        logger.log_matched(intent, capability.id)
        was_generated = False

    result = executor.execute(capability, intent)
    return jsonify({**result.to_dict(), "was_generated": was_generated})


# ---------------------------------------------------------------------------
# GET /capabilities
# ---------------------------------------------------------------------------

@app.route("/capabilities", methods=["GET"])
def list_capabilities():
    caps = [c.to_dict() for c in registry.all()]
    return jsonify({"count": len(caps), "capabilities": caps})


# ---------------------------------------------------------------------------
# GET /status
# ---------------------------------------------------------------------------

@app.route("/status", methods=["GET"])
def status():
    total = registry.count()
    generated = sum(1 for c in registry.all() if c.type == "generated")
    log_entries = logger.recent(n=10000)
    return jsonify({
        "registry_count": total,
        "generated_count": generated,
        "log_count": len(log_entries),
    })


# ---------------------------------------------------------------------------
# GET /logs
# ---------------------------------------------------------------------------

@app.route("/logs", methods=["GET"])
def get_logs():
    n = request.args.get("n", 50, type=int)
    entries = logger.recent(n=n)
    return jsonify({"count": len(entries), "logs": entries})


# ---------------------------------------------------------------------------
# POST /generate
# ---------------------------------------------------------------------------

@app.route("/generate", methods=["POST"])
def force_generate():
    body = request.get_json(silent=True) or {}
    intent = (body.get("intent") or "").strip()
    if not intent:
        return jsonify({"error": "intent is required"}), 400

    capability = generator.generate(intent, existing_ids=set(registry.ids()))
    registry.add(capability)
    logger.log_generated(intent, capability.id)
    return jsonify({"generated": True, "capability": capability.to_dict()})


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"Capability Forge OS API starting on http://localhost:{port}")
    app.run(host="0.0.0.0", port=port, debug=False)
