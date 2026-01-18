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

echo "[sanity] running 1m health check"
ONE_MIN_HEALTH_MIN_GAINERS="${ONE_MIN_HEALTH_MIN_GAINERS:-8}"
ONE_MIN_HEALTH_MAX_STALE="${ONE_MIN_HEALTH_MAX_STALE:-5}"
ONE_MIN_HEALTH_REQUIRE_RATE_LIMITED_ZERO="${ONE_MIN_HEALTH_REQUIRE_RATE_LIMITED_ZERO:-1}"
export BASE ONE_MIN_HEALTH_MIN_GAINERS ONE_MIN_HEALTH_MAX_STALE ONE_MIN_HEALTH_REQUIRE_RATE_LIMITED_ZERO
python3 - <<'PY'
import json
import os
import sys
import urllib.request

base = os.environ.get("BASE")
min_gainers = int(os.environ.get("ONE_MIN_HEALTH_MIN_GAINERS", "8"))
max_stale = int(os.environ.get("ONE_MIN_HEALTH_MAX_STALE", "5"))
require_rl_zero = int(os.environ.get("ONE_MIN_HEALTH_REQUIRE_RATE_LIMITED_ZERO", "1"))

if not base:
  print("[sanity] 1m health: missing BASE", file=sys.stderr)
  sys.exit(1)

try:
  with urllib.request.urlopen(f"{base}/api/data", timeout=8) as resp:
    data = json.load(resp)
except Exception as exc:
  print(f"[sanity] 1m health: fetch failed: {exc}", file=sys.stderr)
  sys.exit(1)

coverage = data.get("coverage") or {}
funnel = coverage.get("one_min_funnel") or {}
gainers_1m = coverage.get("gainers_1m")
if gainers_1m is None:
  rows = data.get("gainers_1m") or []
  gainers_1m = len(rows)
try:
  gainers_1m = int(gainers_1m)
except Exception:
  gainers_1m = 0

stale_price = int(funnel.get("stale_price") or 0)
rate_limited = int(funnel.get("rate_limited") or 0)
print(f"[sanity] 1m health: gainers_1m={gainers_1m} stale_price={stale_price} rate_limited={rate_limited}")

if gainers_1m < min_gainers:
  print(f"[sanity] 1m health: gainers_1m < {min_gainers}", file=sys.stderr)
  sys.exit(2)
if stale_price > max_stale:
  print(f"[sanity] 1m health: stale_price > {max_stale}", file=sys.stderr)
  sys.exit(3)
if require_rl_zero and rate_limited != 0:
  print("[sanity] 1m health: rate_limited != 0", file=sys.stderr)
  sys.exit(4)
PY

echo "[sanity] ALL OK"
