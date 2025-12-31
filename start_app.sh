#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

# Ports (override via env)
BACKEND_PORT="${BACKEND_PORT:-5001}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"
HOST="${HOST:-127.0.0.1}"

SENTIMENT_HOST="${SENTIMENT_HOST:-$HOST}"
SENTIMENT_PORT="${SENTIMENT_PORT:-8002}"
export SENTIMENT_HOST SENTIMENT_PORT
SENTIMENT_PIPELINE_URL="http://${SENTIMENT_HOST}:${SENTIMENT_PORT}"
export SENTIMENT_PIPELINE_URL

echo "[start_app] backend:  http://${HOST}:${BACKEND_PORT}"
echo "[start_app] frontend: http://${HOST}:${FRONTEND_PORT}"

# Start sentiment pipeline (background)
(
  # Run the pipeline on its default port (8002) unless overridden
  echo "[start_app] sentiment pipeline: http://${SENTIMENT_HOST}:${SENTIMENT_PORT} (starting in background)"
  # Prefer project virtualenv if available
  if [ -f .venv/bin/activate ]; then
    echo "[start_app] activating .venv for pipeline"
    # shellcheck disable=SC1091
    . .venv/bin/activate
  fi
  # Use the repo helper script which honors env vars
  SENTIMENT_PORT="$SENTIMENT_PORT" SENTIMENT_HOST="$SENTIMENT_HOST" ./scripts/start_sentiment.sh > /tmp/mw_pipeline_${SENTIMENT_PORT}.log 2>&1 &
  echo $! > /tmp/mw_sentiment.pid

  # Wait for pipeline health from inside the pipeline starter (best-effort)
  echo "[start_app] waiting for sentiment pipeline health (inside starter)..."
  max_wait=30
  waited=0
  until curl -sS http://${SENTIMENT_HOST}:${SENTIMENT_PORT}/health >/dev/null 2>&1 || [ $waited -ge $max_wait ]; do
    sleep 1
    waited=$((waited+1))
  done
  if [ $waited -ge $max_wait ]; then
    echo "[start_app] WARNING: pipeline did not respond within ${max_wait}s"
  else
    echo "[start_app] pipeline healthy after ${waited}s"
  fi
) &

# Start backend
(
  cd backend
  export PORT="$BACKEND_PORT"
  export HOST="$HOST"
  export SENTIMENT_HOST="$SENTIMENT_HOST"
  export SENTIMENT_PORT="$SENTIMENT_PORT"
  export SENTIMENT_PIPELINE_URL="$SENTIMENT_PIPELINE_URL"
  # If you use .env in backend, load it here (optional):
  # [ -f .env ] && set -a && source .env && set +a
  ./start_backend_strict.sh
) &

# Wait for pipeline health (best-effort) before starting frontend
echo "[start_app] waiting up to 30s for sentiment pipeline before starting frontend..."
max_wait=30
waited=0
while ! curl -sS http://${SENTIMENT_HOST}:${SENTIMENT_PORT}/health >/dev/null 2>&1 && [ $waited -lt $max_wait ]; do
  sleep 1
  waited=$((waited+1))
done
if [ $waited -ge $max_wait ]; then
  echo "[start_app] pipeline health timeout (${max_wait}s); starting frontend anyway"
else
  echo "[start_app] pipeline healthy; starting frontend"
fi

# Start frontend
(
  cd frontend
  # Ensure frontend hits the same backend
  if [ -f .env.local ]; then
    echo "[start_app] using frontend/.env.local"
  fi
  if lsof -nP -iTCP:${FRONTEND_PORT} -sTCP:LISTEN >/dev/null 2>&1; then
    echo "[start_app] WARNING: port ${FRONTEND_PORT} appears in use. Frontend dev server may fail to start."
  fi
  npm run dev -- --host "$HOST" --port "$FRONTEND_PORT"
) &

wait
