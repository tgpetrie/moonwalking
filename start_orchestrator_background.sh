#!/usr/bin/env bash
set -euo pipefail

_resolve() {
  local target="$1"
  if command -v readlink >/dev/null 2>&1 && readlink -f "$target" >/dev/null 2>&1; then
    readlink -f "$target"
  else
    python3 - "$target" <<'PY'
import os, sys
print(os.path.realpath(sys.argv[1]))
PY
  fi
}
SCRIPT_PATH="$(_resolve "$0")"
SCRIPT_DIR="$(cd "$(dirname "$SCRIPT_PATH")" && pwd)"
cd "$SCRIPT_DIR"

STATE_DIR="/tmp/bhabit_run"
BACKEND_PID="$STATE_DIR/backend.pid"
FRONTEND_PID="$STATE_DIR/frontend.pid"
STATE_JSON="$STATE_DIR/state.json"

mkdir -p "$STATE_DIR"

BACKEND_PORT=5001

is_listening() { lsof -iTCP:"$1" -sTCP:LISTEN >/dev/null 2>&1; }

if is_listening "$BACKEND_PORT"; then
  if [ -f "$BACKEND_PID" ]; then
    PID=$(cat "$BACKEND_PID" 2>/dev/null || true)
    if [ -n "${PID:-}" ] && ps -p "$PID" >/dev/null 2>&1; then
      kill "$PID" 2>/dev/null || true
      for i in {1..20}; do ps -p "$PID" >/dev/null 2>&1 || break; sleep 0.1; done
      ps -p "$PID" >/dev/null 2>&1 && kill -9 "$PID" 2>/dev/null || true
    fi
  fi
fi

if is_listening "$BACKEND_PORT"; then
  echo "Backend port 5001 is in use. Run $SCRIPT_DIR/stop_orchestrator_background.sh and try again." >&2
  exit 1
fi

[ -d "$SCRIPT_DIR/.venv" ] && source "$SCRIPT_DIR/.venv/bin/activate" || true

[ -d "$SCRIPT_DIR/backend" ] || { echo "Missing directory: $SCRIPT_DIR/backend" >&2; exit 1; }
[ -d "$SCRIPT_DIR/frontend" ] || { echo "Missing directory: $SCRIPT_DIR/frontend" >&2; exit 1; }

(
  cd "$SCRIPT_DIR/backend"
  nohup python3 app.py --port "$BACKEND_PORT" > "$SCRIPT_DIR/backend.log" 2>&1 &
  echo $! > "$BACKEND_PID"
)

(
  cd "$SCRIPT_DIR/frontend"
  # Only write .env.local if missing unless FORCE_ENV_WRITE=1 is set
  if [ "${FORCE_ENV_WRITE:-0}" = "1" ] || [ ! -f .env.local ]; then
    printf "VITE_API_URL=http://localhost:%s\n" "$BACKEND_PORT" > .env.local
    echo "[start_orchestrator_background] wrote frontend/.env.local"
  else
    echo "[start_orchestrator_background] frontend/.env.local exists; not overwriting"
  fi
  nohup npm run dev > "$SCRIPT_DIR/frontend.log" 2>&1 &
  echo $! > "$FRONTEND_PID"
)

cat > "$STATE_JSON" <<JSON
{
  "backend_port": $BACKEND_PORT,
  "backend_pid_file": "$BACKEND_PID",
  "frontend_pid_file": "$FRONTEND_PID",
  "started_at": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
}
JSON

echo "Started. Backend port: $BACKEND_PORT"
echo "PIDs: backend=$(cat "$BACKEND_PID"), frontend=$(cat "$FRONTEND_PID")"
