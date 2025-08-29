#!/usr/bin/env bash
set -euo pipefail

# Robust dev restarter for BHABIT CBMOONERS 4
# - Ensures python3 (falls back to python)
# - Ensures .venv exists
# - Starts backend @ :$BE_PORT (original-design/backend/app.py)
# - Starts frontend @ :$FE_PORT and points Vite to backend via VITE_API_BASE
# Usage: ./scripts/restart_dev.sh [FE_PORT]
# Env:   BE_PORT=5001 NO_BACKEND=1

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
LOG_DIR="$ROOT_DIR/logs"
FE_LOG_DIR="$ROOT_DIR/frontend/logs"
mkdir -p "$LOG_DIR" "$FE_LOG_DIR"

FE_PORT="${1:-5173}"
BE_PORT="${BE_PORT:-5001}"

# Pick python
if command -v python3 >/dev/null 2>&1; then
  PY=python3
elif command -v python >/dev/null 2>&1; then
  PY=python
else
  echo "[restart_dev] ERROR: python3/python not found in PATH" >&2
  exit 1
fi

BE_DIR="$ROOT_DIR/original-design/backend"
FE_DIR="$ROOT_DIR/frontend"

echo "[restart_dev] stopping any listeners on :$BE_PORT and :$FE_PORT"
(lsof -tiTCP:$BE_PORT -sTCP:LISTEN | xargs -r kill -9) 2>/dev/null || true
(lsof -tiTCP:$FE_PORT -sTCP:LISTEN | xargs -r kill -9) 2>/dev/null || true
pkill -f "vite|node .*vite|$BE_DIR/app.py|gunicorn|start-.*-$FE_PORT-$BE_PORT" 2>/dev/null || true

PORT_FILE="$ROOT_DIR/backend/frontend.port"
mkdir -p "$(dirname "$PORT_FILE")"
echo "$FE_PORT" > "$PORT_FILE"
echo "[restart_dev] wrote FE port file -> $PORT_FILE ($FE_PORT)"

if [[ "${NO_BACKEND:-}" != "1" ]]; then
  echo "[restart_dev] preparing python venv (.venv)"
  [[ -d "$ROOT_DIR/.venv" ]] || (cd "$ROOT_DIR" && $PY -m venv .venv)

  VENV_PY="$ROOT_DIR/.venv/bin/python"
  VENV_PIP="$ROOT_DIR/.venv/bin/pip"
  [[ -x "$VENV_PY" ]] || { echo "[restart_dev] ERROR: $VENV_PY missing"; exit 1; }

  echo "[restart_dev] installing backend requirements (if needed)"
  (cd "$BE_DIR" && "$VENV_PIP" -q install -r requirements.txt >/dev/null 2>&1 || true)

  echo "[restart_dev] starting backend @$BE_PORT"
  (
    cd "$BE_DIR"
    export PORT="$BE_PORT"
    export FLASK_ENV=development
    nohup "$VENV_PY" app.py > "$LOG_DIR/backend.log" 2>&1 &
    echo $! > "$LOG_DIR/backend.pid"
  )

  echo -n "[restart_dev] waiting for backend to listen on :$BE_PORT"
  for i in {1..60}; do
    if curl -fsS "http://127.0.0.1:$BE_PORT/api/server-info" >/dev/null 2>&1; then
      echo " ✓"; break
    fi
    echo -n "."; sleep 1
    [[ "$i" == "60" ]] && echo " (timeout) — see $LOG_DIR/backend.log"
  done
else
  echo "[restart_dev] skipping backend start (NO_BACKEND=1)"
fi

echo "[restart_dev] starting frontend on :$FE_PORT (backend http://127.0.0.1:$BE_PORT)"
(
  cd "$FE_DIR"
  export VITE_PORT="$FE_PORT"
  export VITE_API_BASE="http://127.0.0.1:$BE_PORT/api"
  if [[ -x "scripts/start-${FE_PORT}-${BE_PORT}.sh" ]]; then
    ./scripts/start-${FE_PORT}-${BE_PORT}.sh &
  else
    nohup npm run dev -- --port "$FE_PORT" > "$FE_LOG_DIR/frontend.log" 2>&1 &
  fi
)

echo
echo "Logs in $FE_LOG_DIR"
if [[ "${NO_BACKEND:-}" != "1" ]]; then
  echo "[restart_dev] ✅ Backend   -> http://127.0.0.1:$BE_PORT (log: $LOG_DIR/backend.log)"
else
  echo "[restart_dev] ⏭  Backend   -> skipped (NO_BACKEND=1)"
fi
echo "[restart_dev] ✅ Frontend  -> http://localhost:$FE_PORT  (FE log: $FE_LOG_DIR/frontend.log)"
echo "[restart_dev] Port file     $PORT_FILE = $FE_PORT"