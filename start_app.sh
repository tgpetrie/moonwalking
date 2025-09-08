#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

: "${PAGES_PORT:=8789}"   # avoid 8788 conflict
: "${DO_PORT:=8787}"

echo "[orchestrator] Stopping any prior local dev..."
pkill -f "wrangler .* dev .*wrangler.worker.toml" 2>/dev/null || true
pkill -f "@cloudflare/cli pages dev" 2>/dev/null || true
pkill -f "wrangler pages dev" 2>/dev/null || true

echo "[orchestrator] Starting Durable Object locally on :$DO_PORT..."

npx wrangler dev -c wrangler.worker.toml --local --port "$DO_PORT" --persist-to .wrangler/state > .dev-do.log 2>&1 & echo $! > .dev-do.pid
sleep 1
# wait until DO port is accepting connections (max ~5s)
for i in 1 2 3 4 5; do
  if nc -z 127.0.0.1 "$DO_PORT" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

echo "[orchestrator] Building frontend (VITE_API_URL=/api)…"
(cd frontend && VITE_API_URL=/api npm run build) > .dev-build.log 2>&1

# ensure functions are visible to Pages dev when serving ./frontend/dist
rm -f frontend/dist/functions
ln -s "../functions" "frontend/dist/functions"

echo "[orchestrator] Serving built frontend via Pages dev on :$PAGES_PORT (dist)…"
npx wrangler pages dev ./frontend/dist \
  --port "$PAGES_PORT" \
  -b LOCAL_DO_URL="http://127.0.0.1:${DO_PORT}" \
  -b VITE_API_URL="/api" \
  --compatibility-date=2025-08-23 > .dev-pages.log 2>&1 & echo $! > .dev-pages.pid

echo "[orchestrator] Local dev up."
echo " - DO:      http://127.0.0.1:${DO_PORT}"
echo " - Pages:   http://127.0.0.1:${PAGES_PORT}"
echo "Smoke tests:"
echo "  curl -s http://127.0.0.1:${PAGES_PORT}/api/server-info | jq ."
echo "  curl -s \"http://127.0.0.1:${PAGES_PORT}/api/sentiment?symbols=BTC,ETH\" | jq ."

