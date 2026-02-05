#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"
BACKEND_PORT="${BACKEND_PORT:-5001}"

source "$ROOT/scripts/ports_strict.sh"

kill_port "$FRONTEND_PORT"

echo "[strict] starting frontend on :$FRONTEND_PORT (proxy -> :$BACKEND_PORT)"
cd "$ROOT/frontend"

# feed vite config via env so proxy can’t drift
export VITE_PROXY_TARGET="http://127.0.0.1:${BACKEND_PORT}"
export VITE_API_BASE_URL="http://127.0.0.1:${BACKEND_PORT}"

# --strictPort makes it fail if it can’t bind (good in strict mode)
npm run dev -- --port "$FRONTEND_PORT" --strictPort
