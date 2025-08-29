#!/usr/bin/env bash
# Helper to (re)start the backend server used by the project.
# - creates/activates a virtualenv at ./ .venv
# - installs requirements if needed
# - optionally kills existing process on port
# - starts python app.py with the appropriate flags
# - can run in foreground or background (with nohup > server.log)

set -euo pipefail

HERE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE_DIR"

PORT=5001
KILL_PORT=false
AUTO_PORT=false
DEBUG=false
BG=false
LOGFILE="server.log"
RESTART_FRONTEND=false
FRONTEND_DIR="$(cd "$HERE_DIR/../frontend" >/dev/null 2>&1 && pwd || echo ../frontend)"
FRONTEND_PORT=5173
FRONTEND_LOG="${FRONTEND_DIR}/server.log"
FRONTEND_PIDFILE="${FRONTEND_DIR}/frontend.pid"

usage() {
  cat <<EOF
Usage: $0 [--port <port>] [--kill-port] [--auto-port] [--debug] [--bg]

Options:
  --port N        Start server on port N (default: 5001)
  --kill-port     Kill any process on target port before starting
  --auto-port     Let app automatically find an available port
  --debug         Start with debug logging enabled
  --bg            Run server in background and write logs to $LOGFILE
  -h|--help       Show this help

Examples:
  $0 --kill-port --port 5001
  $0 --auto-port --bg
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --port)
      PORT="$2"
      shift 2
      ;;
    --kill-port)
      KILL_PORT=true
      shift
      ;;
    --auto-port)
      AUTO_PORT=true
      shift
      ;;
    --debug)
      DEBUG=true
      shift
      ;;
    --bg)
      BG=true
      shift
      ;;
    --restart-frontend)
      RESTART_FRONTEND=true
      shift
      ;;
    -h|--help)
      usage; exit 0
      ;;
    *)
      echo "Unknown arg: $1" >&2; usage; exit 2
      ;;
  esac
done

echo "[start_backend] cwd=$HERE_DIR"
echo "[start_backend] PORT=$PORT KILL_PORT=$KILL_PORT AUTO_PORT=$AUTO_PORT DEBUG=$DEBUG BG=$BG"

# Setup virtualenv
if [ ! -d ".venv" ]; then
  echo "[start_backend] Creating virtualenv .venv"
  python3 -m venv .venv
fi

# Activate
source .venv/bin/activate

echo "[start_backend] Installing requirements (pip may skip already-installed packages)"
pip install -r requirements.txt || true

start_cmd=(python app.py)
if [ "$AUTO_PORT" = true ]; then
  start_cmd+=(--auto-port)
else
  start_cmd+=(--port "$PORT")
fi
if [ "$KILL_PORT" = true ]; then
  start_cmd+=(--kill-port)
fi
if [ "$DEBUG" = true ]; then
  start_cmd+=(--debug)
fi

# Flatten command for printing
printf -v START_CMD_STR "%q " "${start_cmd[@]}"
echo "[start_backend] start command: $START_CMD_STR"

if [ "$BG" = true ]; then
  echo "[start_backend] starting in background -> $LOGFILE"
  nohup ${START_CMD_STR} > "$LOGFILE" 2>&1 &
  BACK_PID=$!
  disown
  # write pidfile for convenience
  echo "$BACK_PID" > "$HERE_DIR/backend.pid" || true
  sleep 0.5
  echo "[start_backend] backend launched (PID: $BACK_PID)"

  # Optionally restart frontend dev server
  if [ "$RESTART_FRONTEND" = true ]; then
    echo "[start_backend] restarting frontend in $FRONTEND_DIR (port $FRONTEND_PORT)"
    if lsof -ti :$FRONTEND_PORT >/dev/null 2>&1; then
      echo "[start_backend] killing process on port $FRONTEND_PORT"
      lsof -ti :$FRONTEND_PORT | xargs -r kill -9 || true
      sleep 0.5
    fi
    if [ -d "$FRONTEND_DIR" ]; then
      pushd "$FRONTEND_DIR" >/dev/null || true
      echo "[start_backend] running npm install (may take a minute)"
      npm install --no-audit --no-fund || true
      echo "[start_backend] starting frontend in background -> $FRONTEND_LOG"
      # Start frontend with nohup and capture PID; write pidfile for easier control
      nohup npm run dev > "$FRONTEND_LOG" 2>&1 &
      FRONT_PID=$!
      disown
      # Ensure pidfile directory exists (frontend dir) and write pidfile atomically
      if ! echo "$FRONT_PID" > "$FRONTEND_PIDFILE"; then
        echo "[start_backend] Warning: failed to write frontend pidfile to $FRONTEND_PIDFILE"
      fi
      popd >/dev/null || true
      echo "[start_backend] frontend launched (PID: $FRONT_PID) (pidfile: $FRONTEND_PIDFILE)"
    else
      echo "[start_backend] frontend directory not found: $FRONTEND_DIR"
    fi
  fi

  echo "[start_backend] tailing $LOGFILE (press Ctrl-C to stop viewing)"
  tail -n 200 -f "$LOGFILE"
else
  # Run in foreground, allowing Ctrl-C to stop
  exec ${START_CMD_STR}
fi
