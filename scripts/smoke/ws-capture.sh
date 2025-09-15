#!/usr/bin/env bash
set -euo pipefail

# Usage: scripts/smoke/ws-capture.sh <wss-url> <seconds>
# Example: scripts/smoke/ws-capture.sh "wss://moonwalking-worker.tgpetrie.workers.dev/ws" 30

WSS=${1:-}
# shorter default capture to reduce load on CF account
SECONDS=${2:-10}

if [[ -z "$WSS" ]]; then
  echo "Usage: $0 <wss-url> [seconds]"
  exit 2
fi

mkdir -p dev-evidence/logs
OUT="dev-evidence/logs/ws-capture-$(date -u +%Y%m%dT%H%M%SZ).log"

echo "Starting websocket capture to $WSS for $SECONDS seconds -> $OUT"

# Try using npx wscat if available; fall back to node+ws if not
if command -v npx >/dev/null 2>&1; then
  # run wscat in background
  npx --yes wscat -c "$WSS" > "$OUT" 2>&1 &
  WS_PID=$!
  sleep "$SECONDS"
  kill "$WS_PID" || true
else
  echo "npx not found; attempting node inline ws client" > "$OUT"
  node -e "const WebSocket=require('ws');const ws=new WebSocket(process.argv[1]);ws.on('message',m=>console.log('MSG',m));ws.on('open',()=>console.log('OPEN'));ws.on('close',()=>console.log('CLOSE'))" "$WSS" > "$OUT" 2>&1 &
  WS_PID=$!
  sleep "$SECONDS"
  kill "$WS_PID" || true
fi

echo "Finished websocket capture: $OUT"
