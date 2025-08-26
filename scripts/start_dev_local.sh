#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"

echo "Starting backend..."
(
  cd "$BACKEND_DIR"
  if [[ -d .venv ]]; then
    source .venv/bin/activate
  fi
  # Run backend in background and log output
  python app.py
) > "$ROOT_DIR/backend/server.log" 2>&1 &

echo "Starting frontend..."
(
  cd "$FRONTEND_DIR"
  npm run dev
) > "$ROOT_DIR/frontend/dev.log" 2>&1 &

echo "Dev servers launched. Check logs: backend/server.log and frontend/dev.log"
