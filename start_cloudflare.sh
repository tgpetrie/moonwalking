#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

: "${PAGES_PORT:=8789}"   # avoid 8788 conflict
: "${DO_PORT:=8787}"

echo "[orchestrator] Stopping any prior local dev…"
pkill -f "wrangler .* dev .*wrangler.worker.toml" 2>/dev/null || true
pkill -f "@cloudflare/cli pages dev" 2>/dev/null || true
pkill -f "wrangler pages dev" 2>/dev/null || true
if command -v lsof >/dev/null 2>&1; then
  for p in "$DO_PORT" "$PAGES_PORT"; do
    PIDS=$(lsof -tiTCP:"$p" -sTCP:LISTEN 2>/dev/null || true)
    if [ -n "$PIDS" ]; then
      echo "[orchestrator] Freeing port :$p (pids: $PIDS)…"
      kill $PIDS 2>/dev/null || true
      sleep 0.5
      PIDS2=$(lsof -tiTCP:"$p" -sTCP:LISTEN 2>/dev/null || true)
      [ -n "$PIDS2" ] && kill -9 $PIDS2 2>/dev/null || true
    fi
  done
fi

echo "[orchestrator] Starting Durable Object locally on :${DO_PORT}…"
npx -y wrangler dev -c wrangler.worker.toml --local --port "${DO_PORT}" --persist-to .wrangler/state > .dev-do.log 2>&1 & echo $! > .dev-do.pid
sleep 1

echo "[orchestrator] Starting Pages dev on :${PAGES_PORT} with BACKEND_ORIGIN → DO …"
npx -y wrangler pages dev ./frontend -c wrangler.pages.toml \
  --port "${PAGES_PORT}" \
  --functions "./functions" \
  --binding BACKEND_ORIGIN="http://127.0.0.1:${DO_PORT}" \
  --binding VITE_API_URL="/api" \
  --compatibility-date=2025-08-23 \
  > .dev-pages.log 2>&1 & echo $! > .dev-pages.pid

echo "[orchestrator] Local dev up."
echo " - DO:      http://127.0.0.1:${DO_PORT}"
echo " - Pages:   http://127.0.0.1:${PAGES_PORT}"
echo "Smoke tests:"
echo "  curl -s http://127.0.0.1:${PAGES_PORT}/api/server-info | jq ."
echo "  curl -s \"http://127.0.0.1:${PAGES_PORT}/api/alerts/recent?limit=25\" | jq ."
