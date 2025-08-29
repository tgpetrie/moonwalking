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
AUTO_PORT=true
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

# If requested, kill any process currently listening on the target PORT.
if [ "$KILL_PORT" = true ]; then
  echo "[start_backend] kill-port requested: checking for listeners on port $PORT"
  # Try to read pid from known pidfile first
  if [ -f "$HERE_DIR/backend.pid" ]; then
    OLD_PID=$(cat "$HERE_DIR/backend.pid" 2>/dev/null || true)
    if [ -n "$OLD_PID" ]; then
      echo "[start_backend] found backend.pid -> $OLD_PID; attempting graceful kill"
      kill "$OLD_PID" 2>/dev/null || true
      sleep 0.25
      kill -0 "$OLD_PID" 2>/dev/null && kill -9 "$OLD_PID" 2>/dev/null || true
      rm -f "$HERE_DIR/backend.pid" || true
    fi
  fi

  if lsof -ti :$PORT >/dev/null 2>&1; then
    echo "[start_backend] killing process on port $PORT"
    lsof -ti :$PORT | xargs -r kill -9 || true
    sleep 0.25
  else
    echo "[start_backend] no process found listening on port $PORT"
  fi
fi

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
    # If a frontend pidfile exists, prefer using the stop helper to gracefully stop it
    if [ -f "$FRONTEND_PIDFILE" ]; then
      echo "[start_backend] found frontend pidfile at $FRONTEND_PIDFILE; attempting graceful stop"
      if [ -x "$FRONTEND_DIR/stop_frontend.sh" ]; then
        bash "$FRONTEND_DIR/stop_frontend.sh" || true
      else
        # fallback: attempt to kill by pid then by port
        PID=$(cat "$FRONTEND_PIDFILE" 2>/dev/null || true)
        if [ -n "$PID" ]; then
          echo "[start_backend] killing frontend pid $PID"
          kill "$PID" 2>/dev/null || true
          sleep 0.5
          kill -9 "$PID" 2>/dev/null || true
        fi
      fi
      # remove stale pidfile if present
      rm -f "$FRONTEND_PIDFILE" || true
    fi
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
      # If frontend Vite is configured with strictPort:true, assume the configured port and write it directly
      VITE_CONFIG_FILE="$FRONTEND_DIR/vite.config.js"
      if [ -f "$VITE_CONFIG_FILE" ] && grep -qE "strictPort\s*:\s*true" "$VITE_CONFIG_FILE"; then
        echo "[start_backend] detected Vite strictPort=true in $VITE_CONFIG_FILE; writing configured frontend port $FRONTEND_PORT"
        echo "$FRONTEND_PORT" > "$HERE_DIR/frontend.port" || true
      else
        # Attempt to detect actual listening port for the frontend process and write to backend/frontend.port
        FRONTEND_PORT_DETECTED=""
        # First, try to parse the frontend log (Vite prints local URLs). This is usually most reliable.
        for i in 1 2 3 4 5 6 7 8 9 10; do
          if [ -f "$FRONTEND_LOG" ]; then
            # Look for Vite style lines (e.g. "  Local: http://127.0.0.1:5173/") or any http://localhost:<port>
            PORT_STR=$(grep -Eo "http://[0-9.]+:([0-9]{2,5})" "$FRONTEND_LOG" | sed -E 's/.*:([0-9]+)$/\1/' | head -n1 || true)
            if [ -z "$PORT_STR" ]; then
              PORT_STR=$(grep -Eo "http://localhost:([0-9]{2,5})" "$FRONTEND_LOG" | sed -E 's/.*:([0-9]+)$/\1/' | head -n1 || true)
            fi
            if [ -n "$PORT_STR" ]; then
              FRONTEND_PORT_DETECTED="$PORT_STR"
              break
            fi
          fi
          # Fallback: try lsof against the process (works if child process listens)
          if lsof -Pan -p "$FRONT_PID" -iTCP -sTCP:LISTEN -n -P >/dev/null 2>&1; then
            PORT_STR=$(lsof -Pan -p "$FRONT_PID" -iTCP -sTCP:LISTEN -n -P | awk '{for(i=1;i<=NF;i++) if($i ~ /:[0-9]+/) print $i}' | sed -E 's/.*:([0-9]+)$/\1/' | head -n1 || true)
            if [ -n "$PORT_STR" ]; then
              FRONTEND_PORT_DETECTED="$PORT_STR"
              break
            fi
          fi
          sleep 0.5
        done
        if [ -n "$FRONTEND_PORT_DETECTED" ]; then
          echo "[start_backend] detected frontend listening on port $FRONTEND_PORT_DETECTED"
          # Write the detected port next to backend app so backend can read it
          echo "$FRONTEND_PORT_DETECTED" > "$HERE_DIR/frontend.port" || true
        else
          echo "[start_backend] Warning: could not detect frontend listening port; falling back to configured port $FRONTEND_PORT"
          echo "$FRONTEND_PORT" > "$HERE_DIR/frontend.port" || true
        fi
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
