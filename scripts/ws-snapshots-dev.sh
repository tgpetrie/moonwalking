#!/usr/bin/env bash
set -euo pipefail

# Periodically trigger the local Worker to refresh market snapshots
# Defaults: URL=http://127.0.0.1:8787/refresh-snapshots INTERVAL=20s

URL=${URL:-http://127.0.0.1:8787/refresh-snapshots}
INTERVAL=${INTERVAL:-20}

echo "[ws-snapshots-dev] Hitting $URL every ${INTERVAL}s (Ctrl+C to stop)"

trap 'echo; echo "[ws-snapshots-dev] Stopping"; exit 0' INT TERM

while true; do
  ts=$(date +"%H:%M:%S")
  if curl -fsS "$URL" >/dev/null; then
    echo "[$ts] refreshed"
  else
    echo "[$ts] refresh failed" >&2
  fi
  sleep "$INTERVAL"
done

