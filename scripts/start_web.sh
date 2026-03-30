#!/usr/bin/env bash
# scripts/start_web.sh — Launch the AURA web UI

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AURA_ROOT="$(dirname "$SCRIPT_DIR")"
export AURA_HOME="${AURA_HOME:-$HOME/.aura}"
export PATH="$AURA_ROOT:$PATH"

echo "[aura] Starting web UI …"
python3 "$AURA_ROOT/aura" ui web
