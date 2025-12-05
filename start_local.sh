#!/usr/bin/env bash
set -euo pipefail

# -------------------------------------------------------------------
# Local dev runner (smart):
# - Finds free ports (backend starting 5001, frontend starting 5173)
# - Stores PIDs it started and only stops those on next run
# - Exports PYTHONPATH for Flask imports
# - Starts backend (non-fatal if bind blocked) and always starts frontend
# -------------------------------------------------------------------

HOST="${HOST:-127.0.0.1}"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

BACKEND_START=${BACKEND_START:-5001}
FRONTEND_START=${FRONTEND_START:-5173}

BACKEND_PID_FILE=${BACKEND_PID_FILE:-/tmp/mw_backend.pid}
FRONTEND_PID_FILE=${FRONTEND_PID_FILE:-/tmp/mw_frontend.pid}
BACKEND_PORT_FILE=${BACKEND_PORT_FILE:-/tmp/mw_backend.port}
FRONTEND_PORT_FILE=${FRONTEND_PORT_FILE:-/tmp/mw_frontend.port}

# Usage helper: start_local.sh status
if [ "${1:-}" = "status" ]; then
  echo "[start.local] status"
  if [ -f "$BACKEND_PID_FILE" ]; then
    bpid=$(cat "$BACKEND_PID_FILE" 2>/dev/null || echo "")
    echo "backend pid: ${bpid:-<missing>}"
  else
    echo "backend pid: <missing>"
  fi
  if [ -f "$FRONTEND_PID_FILE" ]; then
    fpid=$(cat "$FRONTEND_PID_FILE" 2>/dev/null || echo "")
    echo "frontend pid: ${fpid:-<missing>}"
  else
    echo "frontend pid: <missing>"
  fi
  if [ -f "$BACKEND_PORT_FILE" ]; then
    echo "backend port: $(cat "$BACKEND_PORT_FILE")"
  fi
  if [ -f "$FRONTEND_PORT_FILE" ]; then
    echo "frontend port: $(cat "$FRONTEND_PORT_FILE")"
  fi
  # health checks
  if [ -f "$BACKEND_PORT_FILE" ]; then
    bp=$(cat "$BACKEND_PORT_FILE")
    if curl -sS "http://$HOST:$bp/data" >/dev/null 2>&1; then
      echo "backend /data: OK"
    else
      echo "backend /data: UNAVAILABLE"
    fi
  fi
  if [ -f "$FRONTEND_PORT_FILE" ]; then
    fp=$(cat "$FRONTEND_PORT_FILE")
    if curl -sS "http://$HOST:$fp/" >/dev/null 2>&1; then
      echo "frontend root: OK"
    else
      echo "frontend root: UNAVAILABLE"
    fi
  fi
  exit 0
fi

# Kill process stored in a pidfile, if it exists
kill_pidfile() {
  local pidfile="$1"

  if [ -f "$pidfile" ]; then
    local pid
    pid="$(cat "$pidfile" 2>/dev/null || true)"

    if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
      echo "[start.local] Killing process $pid from $pidfile..."
      kill "$pid" 2>/dev/null || true
    fi

    rm -f "$pidfile" || true
  fi
}

# stop previously started processes (only ours)
kill_pidfile "$BACKEND_PID_FILE"
kill_pidfile "$FRONTEND_PID_FILE"

kill_process_on_port() {
  local port=$1
  local pids
  pids=$(lsof -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null || true)
  if [ -n "$pids" ]; then
    echo "[start.local] freeing port $port"
    for pid in $pids; do
      echo "[start.local]  - killing pid $pid"
      kill "$pid" >/dev/null 2>&1 || true
    done
    sleep 1
    if lsof -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1; then
      echo "[start.local] ERROR: port $port still in use after attempting to kill processes"
      exit 1
    fi
  fi
}

kill_process_on_port "$BACKEND_START"
kill_process_on_port "$FRONTEND_START"

BACKEND_PORT="$BACKEND_START"
FRONTEND_PORT="$FRONTEND_START"

echo "[start.local] backend -> http://$HOST:$BACKEND_PORT (strict)"
echo "[start.local] frontend -> http://$HOST:$FRONTEND_PORT (strict)"

# Backend (non-fatal if environment blocks bind)
(
  cd "$ROOT_DIR"
  export PYTHONPATH="$ROOT_DIR/backend"
  export FLASK_APP=backend.app
  export FLASK_ENV=development
  flask run --host "$HOST" --port "$BACKEND_PORT"
) > /tmp/mw_backend.log 2>&1 &
echo $! > "$BACKEND_PID_FILE"

# persist chosen ports so helper commands can inspect them
echo "$BACKEND_PORT" > "$BACKEND_PORT_FILE"

# Frontend — ensure deps then start Vite with env BACKEND_PORT and VITE_PORT
(
  cd "$ROOT_DIR/frontend"
  if [ ! -d node_modules ]; then
    echo "[start.local] installing frontend dependencies..."
    npm install
  fi
  BACKEND_PORT="$BACKEND_PORT" VITE_PORT="$FRONTEND_PORT" npm run dev -- --host "$HOST" --port "$FRONTEND_PORT" --strictPort
) > /tmp/mw_frontend.log 2>&1 &
echo $! > "$FRONTEND_PID_FILE"
echo "$FRONTEND_PORT" > "$FRONTEND_PORT_FILE"

echo "[start.local] backend pid: $(cat "$BACKEND_PID_FILE") (written to $BACKEND_PID_FILE)"
echo "[start.local] frontend pid: $(cat "$FRONTEND_PID_FILE") (written to $FRONTEND_PID_FILE)"

# Block until both backend /data and frontend root respond (short timeout)
WAIT_RETRIES=${WAIT_RETRIES:-20}
WAIT_INTERVAL=${WAIT_INTERVAL:-0.5}
echo "[start.local] waiting up to $(awk "BEGIN{print $WAIT_RETRIES*$WAIT_INTERVAL}")s for services to be healthy..."
i=0
backend_ok=0
frontend_ok=0
while [ $i -lt $WAIT_RETRIES ]; do
  if [ $backend_ok -eq 0 ]; then
    if curl -sS "http://$HOST:$BACKEND_PORT/data" >/dev/null 2>&1; then
      backend_ok=1
      echo "[start.local] backend /data is responding"
    fi
  fi
  if [ $frontend_ok -eq 0 ]; then
    if curl -sS "http://$HOST:$FRONTEND_PORT/" >/dev/null 2>&1; then
      frontend_ok=1
      echo "[start.local] frontend root is responding"
    fi
  fi
  if [ $backend_ok -eq 1 ] && [ $frontend_ok -eq 1 ]; then
    break
  fi
  sleep "$WAIT_INTERVAL"
  i=$((i+1))
done

if [ $backend_ok -ne 1 ]; then
  echo "[start.local] WARNING: backend did not respond to /data after ${WAIT_RETRIES} attempts"
  echo "[start.local] see /tmp/mw_backend.log for details"
fi
if [ $frontend_ok -ne 1 ]; then
  echo "[start.local] WARNING: frontend did not respond after ${WAIT_RETRIES} attempts"
  echo "[start.local] see /tmp/mw_frontend.log for details"
fi

# Optionally open browser on macOS when both services are at least partly healthy
if [ "${OPEN_BROWSER:-auto}" = "auto" ]; then
  if [ "$(uname -s)" = "Darwin" ]; then
    OPEN_BROWSER=1
  else
    OPEN_BROWSER=0
  fi
fi
if [ "${OPEN_BROWSER:-0}" = "1" ]; then
  echo "[start.local] opening http://$HOST:$FRONTEND_PORT in the default browser..."
  open "http://$HOST:$FRONTEND_PORT" >/dev/null 2>&1 || true
fi

echo "[start.local] logs → /tmp/mw_backend.log /tmp/mw_frontend.log"
echo "[start.local] to follow logs live: TAIL_LOGS=1 ./start_local.sh"
