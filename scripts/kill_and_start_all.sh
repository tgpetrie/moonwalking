#!/usr/bin/env bash
set -euo pipefail

# Kill and start both backend and frontend together.
# - Prefers existing `backend/kill_and_start_backend.sh` and
#   `frontend/kill_and_start_vite.sh` if present and executable.
# - Falls back to inline steps if those scripts are missing.

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
echo "[all] root: $ROOT_DIR"

########################################
# Backend
########################################
echo "[all] => backend"
if [ -x "$ROOT_DIR/backend/kill_and_start_backend.sh" ]; then
  echo "[all] running backend script: backend/kill_and_start_backend.sh"
  bash "$ROOT_DIR/backend/kill_and_start_backend.sh"
else
  echo "[all] backend starter script missing; attempting inline start"
  cd "$ROOT_DIR/backend"
  echo "[backend] killing app.py and listeners on 5001"
  pkill -f "app.py" 2>/dev/null || true
  kill -9 $(lsof -tiTCP:5001 -sTCP:LISTEN 2>/dev/null) 2>/dev/null || true

  # Ensure venv and deps
  [ -d .venv ] || python3 -m venv .venv
  . .venv/bin/activate
  pip install -q --upgrade pip setuptools wheel
  if [ -f requirements.txt ]; then
    pip install -q -r requirements.txt
  fi

  echo "[backend] starting Flask dev server on 127.0.0.1:5001 -> /tmp/mw_backend.log"
  nohup python app.py --host "127.0.0.1" --port "5001" > /tmp/mw_backend.log 2>&1 &
  sleep 1
  tail -n 30 /tmp/mw_backend.log || true
fi

########################################
# Frontend (Vite)
########################################
echo "[all] => frontend"
if [ -x "$ROOT_DIR/frontend/kill_and_start_vite.sh" ]; then
  echo "[all] running frontend script: frontend/kill_and_start_vite.sh"
  bash "$ROOT_DIR/frontend/kill_and_start_vite.sh"
else
  echo "[all] frontend starter script missing; attempting inline start"
  cd "$ROOT_DIR/frontend"
  echo "[frontend] killing vite and listeners on 5173/5174/5175"
  pkill -f "vite" 2>/dev/null || true
  kill -9 $(lsof -tiTCP:5173,5174,5175 -sTCP:LISTEN 2>/dev/null) 2>/dev/null || true

  if [ ! -d node_modules ]; then
    npm install --no-bin-links
  fi

  echo "[frontend] starting vite on 127.0.0.1:5173 -> /tmp/mw_vite.log"
  nohup npm run dev -- --host "127.0.0.1" --port "5173" > /tmp/mw_vite.log 2>&1 &
  sleep 1
  tail -n 30 /tmp/mw_vite.log || true
fi

echo "[all] done — backend on :5001, frontend on :5173 (logs: /tmp/mw_backend.log, /tmp/mw_vite.log)"
