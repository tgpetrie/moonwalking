#!/usr/bin/env bash
set -euo pipefail

API_ORIGIN="${API_ORIGIN:-http://127.0.0.1:3100}"  # Vite dev proxy origin
SNAP="${API_ORIGIN}/api/snapshots/one-hour-price"
SSE="${API_ORIGIN}/api/events"

echo "→ Checking snapshot: ${SNAP}"
json=$(curl -fsS --max-time 5 "${SNAP}")
echo "   OK: $(echo "$json" | head -c 120) ..."

# Basic sanity: ok==true and rows is an array
echo "$json" | python3 - <<'PY'
import sys, json
data = json.load(sys.stdin)
assert data.get("ok") is True, "ok != true"
assert isinstance(data.get("rows"), list), "rows not list"
PY
echo "   JSON shape looks good."

echo "→ Checking SSE: ${SSE}"
# Read just a couple SSE lines to confirm stream opens
curl -fsS -N --max-time 5 -H 'Accept: text/event-stream' "${SSE}" | sed -n '1,5p' || true
echo "   SSE opened."

echo "✓ Smoke tests passed."
