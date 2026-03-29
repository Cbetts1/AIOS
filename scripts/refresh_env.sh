#!/usr/bin/env bash
# scripts/refresh_env.sh — Re-run environment detection and update env_map.json

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AURA_ROOT="$(dirname "$SCRIPT_DIR")"
export AURA_HOME="${AURA_HOME:-$HOME/.aura}"

python3 - <<'EOF'
import sys, os
sys.path.insert(0, os.environ.get("AURA_ROOT", "."))
from eal import load_env_map
env = load_env_map()
print(f"[aura] Environment refreshed: {env['env_type']}")
print(f"[aura] Capabilities: {', '.join(sorted(env['capabilities']))}")
EOF
