#!/bin/zsh
set -euo pipefail

# Use absolute curl in case PATH is minimal in non-interactive shells
CURL=${CURL:-/usr/bin/curl}
[[ -x "$CURL" ]] || CURL="$(command -v curl)"

BASE="http://127.0.0.1:5001"

echo "=== Try health endpoints ==="
for path in /api/health /health /status /api/status; do
  echo "-- $path"
  $CURL -sS "$BASE$path" || true
  echo
done

echo "=== Metrics (known path) ==="
$CURL -sS "$BASE/api/metrics" || true
echo

echo "=== Prices (probing common paths) ==="
for path in /api/prices /api/spot /api/market/prices /api/markets/prices /prices /api/coins; do
  echo "-- $path"
  resp="$($CURL -sS "$BASE$path" || true)"
  if [[ -n "$resp" && "$resp" != "<!"* ]]; then
    print -r -- "$resp"
    break
  fi
done
