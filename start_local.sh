#!/usr/bin/env bash
set -euo pipefail

# -------------------------------------------------------------------
# Local dev runner: Flask backend on :5001 + Vite frontend on :5173
# - Kills existing processes on those ports
# - Exports PYTHONPATH so Flask can import backend modules
# - Starts backend (non-fatal if it can't bind) and always starts frontend
# - Binds to 127.0.0.1 by default
# -------------------------------------------------------------------

BACKEND_PORT=5001
FRONTEND_PORT=5173
HOST="${HOST:-127.0.0.1}"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ "${SKIP_KILL:-0}" != "1" ]; then
  echo "[start.local] killing anything on :$BACKEND_PORT and :$FRONTEND_PORT ..."
  if command -v lsof >/dev/null 2>&1; then
    BK_PIDS="$(lsof -ti tcp:$BACKEND_PORT || true)"
    [ -n "${BK_PIDS}" ] && kill ${BK_PIDS} || true
    FE_PIDS="$(lsof -ti tcp:$FRONTEND_PORT || true)"
    [ -n "${FE_PIDS}" ] && kill ${FE_PIDS} || true
  else
    echo "[start.local] lsof not available; skip pre-kill"
  fi
  sleep 0.4
fi

echo "[start.local] launching services (backend :$BACKEND_PORT, frontend :$FRONTEND_PORT)"

# Backend (non-fatal if bind fails) — write logs to /tmp
(
  cd "$ROOT_DIR"
  export PYTHONPATH="$ROOT_DIR/backend"
  export FLASK_APP=backend.app
  export FLASK_ENV=development
  flask run --host "$HOST" --port "$BACKEND_PORT"
) > /tmp/mw_backend.log 2>&1 &
BACKEND_PID=$!

# Frontend — ensure deps then start Vite dev server
(
  cd "$ROOT_DIR/frontend"
  if [ ! -d node_modules ]; then
    echo "[start.local] installing frontend dependencies..."
    npm install
  fi
  npm run dev -- --host "$HOST" --port "$FRONTEND_PORT"
) > /tmp/mw_frontend.log 2>&1 &
FRONTEND_PID=$!

echo "[start.local] → frontend: http://$HOST:$FRONTEND_PORT"
echo "[start.local] → backend : http://$HOST:$BACKEND_PORT/data"
echo "[start.local] tail logs: tail -f /tmp/mw_backend.log /tmp/mw_frontend.log"

cleanup() {
  echo "\n[start.local] shutting down..."
  kill "$BACKEND_PID" 2>/dev/null || true
  kill "$FRONTEND_PID" 2>/dev/null || true
}
trap cleanup EXIT

wait
