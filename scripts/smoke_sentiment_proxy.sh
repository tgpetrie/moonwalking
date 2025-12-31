#!/usr/bin/env bash
set -euo pipefail

SYMBOL="${1:-BTC}"
HOST="${HOST:-127.0.0.1}"
BACKEND_PORT="${BACKEND_PORT:-5001}"

BASE="http://${HOST}:${BACKEND_PORT}/api/sentiment"

echo "=== Sentiment proxy smoke ==="
echo "Host: ${HOST}"
echo "Port: ${BACKEND_PORT}"
echo "Symbol: ${SYMBOL}"
echo

check() {
  local label="$1"
  local url="$2"
  echo "-- ${label}"
  curl -fSs "$url" | head -c 800 && echo
  echo
}

check "pipeline health" "${BASE}/pipeline-health"
check "sources" "${BASE}/sources"
check "latest (${SYMBOL})" "${BASE}/latest?symbol=${SYMBOL}"
check "tiered" "${BASE}/tiered"
check "divergence (${SYMBOL})" "${BASE}/divergence?symbol=${SYMBOL}"

# Optional: quick scan for hardcoded pipeline URLs in built assets
if command -v rg >/dev/null 2>&1; then
  if rg -q "127\\.0\\.0\\.1:8002|:8002" frontend; then
    echo "WARN: Found references to :8002 in frontend sources (check DevTools for leaks)"
  fi
fi

echo "All sentiment proxy checks completed."
