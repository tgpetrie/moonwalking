#!/usr/bin/env bash
set -euo pipefail

# Usage: scripts/smoke/watchlist.sh <base-url>
# Example: scripts/smoke/watchlist.sh "https://moonwalking-worker.tgpetrie.workers.dev"

BASE=${1:-}

if [[ -z "$BASE" ]]; then
  echo "Usage: $0 <base-url>"
  exit 2
fi

mkdir -p dev-evidence/logs dev-evidence/headers
TS=$(date -u +%Y%m%dT%H%M%SZ)

echo "POST add watchlist item"
curl -sS -D dev-evidence/headers/watchlist-add-headers-$TS.txt -H "Content-Type: application/json" -X POST -d '{"symbol":"TESTSYM_SMOKE_'$TS'"}' "$BASE/api/watchlist" -o dev-evidence/logs/watchlist-add-$TS.json || true

echo "GET list"
curl -sS -D dev-evidence/headers/watchlist-list-headers-$TS.txt "$BASE/api/watchlist" -o dev-evidence/logs/watchlist-list-$TS.json || true

echo "POST remove watchlist item"
curl -sS -D dev-evidence/headers/watchlist-remove-headers-$TS.txt -H "Content-Type: application/json" -X POST -d '{"symbol":"TESTSYM_SMOKE_'$TS'"}' "$BASE/api/watchlist/remove" -o dev-evidence/logs/watchlist-remove-$TS.json || true

echo "Wrote watchlist logs to dev-evidence/logs/ and headers to dev-evidence/headers/"
