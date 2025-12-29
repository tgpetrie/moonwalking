#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

# Ports (override via env)
BACKEND_PORT="${BACKEND_PORT:-5001}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"
HOST="${HOST:-127.0.0.1}"

echo "[start_app] backend:  http://${HOST}:${BACKEND_PORT}"
echo "[start_app] frontend: http://${HOST}:${FRONTEND_PORT}"

# Start sentiment pipeline (background)
(
  # Run the pipeline on its default port (8002) unless overridden
  SENTIMENT_PORT="${SENTIMENT_PORT:-8002}"
  SENTIMENT_HOST="${HOST}"
  echo "[start_app] sentiment pipeline: http://${SENTIMENT_HOST}:${SENTIMENT_PORT} (starting in background)"
  # Use the repo helper script which honors env vars
  SENTIMENT_PORT="$SENTIMENT_PORT" SENTIMENT_HOST="$SENTIMENT_HOST" ./scripts/start_sentiment.sh > /tmp/mw_pipeline_${SENTIMENT_PORT}.log 2>&1 &
  echo $! > /tmp/mw_sentiment.pid
) &

# Start backend
(
  cd backend
  export PORT="$BACKEND_PORT"
  export HOST="$HOST"
  # If you use .env in backend, load it here (optional):
  # [ -f .env ] && set -a && source .env && set +a
  ./start_backend_strict.sh
) &

# Start frontend
(
  cd frontend
  # Ensure frontend hits the same backend
  if [ -f .env.local ]; then
    # keep existing, but you can sanity print:
    echo "[start_app] using frontend/.env.local"
  fi
  npm run dev -- --host "$HOST" --port "$FRONTEND_PORT"
) &

wait
