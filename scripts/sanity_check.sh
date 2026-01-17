#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOST="${HOST:-127.0.0.1}"
BACKEND_PORT_FILE="${BACKEND_PORT_FILE:-/tmp/mw_backend.port}"

if [ -f "$BACKEND_PORT_FILE" ]; then
  BACKEND_PORT="$(cat "$BACKEND_PORT_FILE")"
else
  BACKEND_PORT="${BACKEND_PORT:-5003}"
fi

BASE="http://$HOST:$BACKEND_PORT"

echo "[sanity] base: $BASE"

fail() {
  echo "[sanity] FAIL: $*" >&2
  exit 1
}

# 1) API base responsive (use /api/data as canonical; /api/health can be slower)
curl -sS --max-time 8 "$BASE/api/data" >/dev/null 2>&1 || fail "/api/data not responding"

# 2) Optional: health endpoint (non-fatal)
curl -sS --max-time 3 "$BASE/api/health" >/dev/null 2>&1 || echo "[sanity] WARN: /api/health not responding"

# 3) Must have /data alias (legacy compatibility)
curl -sS --max-time 8 "$BASE/data" >/dev/null 2>&1 || fail "/data not responding"

# 3) No dead-port references in runtime trees
#    Use word-boundary matching so we don't false-positive on unrelated
#    numeric substrings (e.g., timestamps or SVG path decimals).
#    (Exclude common generated/vendor dirs so this stays meaningful.)
if grep -R -n -E "\\b8001\\b" "$ROOT_DIR/frontend" "$ROOT_DIR/backend" \
  --exclude-dir node_modules \
  --exclude-dir .history \
  --exclude-dir .vite \
  --exclude-dir dist \
  --exclude-dir build \
  --exclude-dir __pycache__ \
  --exclude-dir htmlcov \
  --exclude-dir .venv \
  --exclude-dir venv \
  --exclude "*.log" \
  --exclude "*.lock" \
  --exclude "*.min.js" \
  --exclude "*.map" \
  >/dev/null 2>&1; then
  fail "found '8001' under frontend/ or backend/"
fi

echo "[sanity] OK"

echo "[sanity] running guardrails"
bash scripts/validate_mw_guardrails.sh

echo "[sanity] running alerts oracle"
BACKEND_BASE="$BASE" bash scripts/verify_alerts.sh

echo "[sanity] running coverage oracle"
BACKEND_BASE="$BASE" bash scripts/verify_coverage.sh

echo "[sanity] ALL OK"
