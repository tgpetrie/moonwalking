#!/usr/bin/env bash
set -euo pipefail

# Usage: scripts/smoke/price-loop.sh <endpoint> <count> <interval>
# Example: scripts/smoke/price-loop.sh "https://moonwalking-worker.tgpetrie.workers.dev/api/price?symbol=BTC" 15 2

ENDPOINT=${1:-}
# safer defaults: fewer requests and longer interval to avoid hitting rate limits
COUNT=${2:-6}
INTERVAL=${3:-5}

if [[ -z "$ENDPOINT" ]]; then
  echo "Usage: $0 <endpoint> [count] [interval]"
  exit 2
fi

mkdir -p dev-evidence/logs
OUT="dev-evidence/logs/price-loop-$(date -u +%Y%m%dT%H%M%SZ).log"
echo "Price loop start: $(date -u)" > "$OUT"

for i in $(seq 1 "$COUNT"); do
  echo "--- $(date -u) request $i ---" >> "$OUT"
  # save body and status
  curl -sS -w "\nHTTP_STATUS:%{http_code}\n" "$ENDPOINT" >> "$OUT" || true
  echo >> "$OUT"
  sleep "$INTERVAL"
done

echo "Price loop end: $(date -u)" >> "$OUT"
echo "Wrote $OUT"
