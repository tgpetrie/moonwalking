#!/usr/bin/env bash
set -euo pipefail

# -------------------------------------------------------------------
# Local dev runner (smart):
# - Finds free ports (backend starting 5001, frontend starting 5173)
# - Stores PIDs it started and only stops those on next run
# - Exports PYTHONPATH for Flask imports
# - Starts backend (non-fatal if bind blocked) and always starts frontend
# -------------------------------------------------------------------

# Load NVM if available
if [ -s "$HOME/.nvm/nvm.sh" ]; then
  export NVM_DIR="$HOME/.nvm"
  source "$NVM_DIR/nvm.sh"
  # Use Node v22 if available, otherwise default
  nvm use 22 2>/dev/null || nvm use default 2>/dev/null || true
elif [ -d "$HOME/.nvm/versions/node" ]; then
  # Direct PATH approach if nvm.sh not available
  LATEST_NODE=$(ls -1d "$HOME/.nvm/versions/node"/v* 2>/dev/null | sort -V | tail -1)
  if [ -n "$LATEST_NODE" ]; then
    export PATH="$LATEST_NODE/bin:$PATH"
  fi
fi

HOST="${HOST:-127.0.0.1}"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

BACKEND_START=${BACKEND_START:-5003}
FRONTEND_START=${FRONTEND_START:-5173}

BACKEND_PID_FILE=${BACKEND_PID_FILE:-/tmp/mw_backend.pid}
FRONTEND_PID_FILE=${FRONTEND_PID_FILE:-/tmp/mw_frontend.pid}
PIPELINE_PID_FILE=${PIPELINE_PID_FILE:-/tmp/mw_pipeline.pid}
BACKEND_PORT_FILE=${BACKEND_PORT_FILE:-/tmp/mw_backend.port}
FRONTEND_PORT_FILE=${FRONTEND_PORT_FILE:-/tmp/mw_frontend.port}

SENTIMENT_HOST="${SENTIMENT_HOST:-$HOST}"
SENTIMENT_PORT="${SENTIMENT_PORT:-8002}"
SENTIMENT_PIPELINE_URL="http://${SENTIMENT_HOST}:${SENTIMENT_PORT}"

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
  if [ -f "$PIPELINE_PID_FILE" ]; then
    ppid=$(cat "$PIPELINE_PID_FILE" 2>/dev/null || echo "")
    echo "pipeline pid: ${ppid:-<missing>}"
  else
    echo "pipeline pid: <missing>"
  fi
  if [ -f "$BACKEND_PORT_FILE" ]; then
    echo "backend port: $(cat "$BACKEND_PORT_FILE")"
  fi
  if [ -f "$FRONTEND_PORT_FILE" ]; then
    echo "frontend port: $(cat "$FRONTEND_PORT_FILE")"
  fi
  echo "sentiment port: $SENTIMENT_PORT"
  # health checks
  if [ -f "$BACKEND_PORT_FILE" ]; then
    bp=$(cat "$BACKEND_PORT_FILE")
    if curl -sS "http://$HOST:$bp/api/health" >/dev/null 2>&1; then
      echo "backend /api/health: OK"
    else
      echo "backend /api/health: UNAVAILABLE"
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
  if curl -sS "http://$SENTIMENT_HOST:$SENTIMENT_PORT/health" >/dev/null 2>&1; then
    echo "sentiment pipeline /health: OK"
  else
    echo "sentiment pipeline /health: UNAVAILABLE"
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

# AI-branch enforcement: if script exists, run it and abort on failure
if [ -f "$ROOT_DIR/scripts/check_ai_rules.sh" ]; then
  echo "[start.local] running AI-branch enforcement check..."
  bash "$ROOT_DIR/scripts/check_ai_rules.sh" || {
    echo "[start.local] AI-branch enforcement failed — aborting start." >&2
    exit 2
  }
fi

# stop previously started processes (only ours)
kill_pidfile "$BACKEND_PID_FILE"
kill_pidfile "$FRONTEND_PID_FILE"
kill_pidfile "$PIPELINE_PID_FILE"

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

# In VS Code tasks, child processes can be terminated when the task ends.
# Detach backend/frontend into a separate session by default in that environment.
DETACH=${DETACH:-0}
if [ "${TERM_PROGRAM:-}" = "vscode" ]; then
  DETACH=1
fi

start_detached() {
  local logfile="$1"
  shift

  # On macOS, `setsid` may not exist; and VS Code tasks can SIGTERM the process
  # group when the task ends. Spawn the child in a new session explicitly.
  python3 - "$logfile" "$@" <<'PY'
import os
import subprocess
import sys

logfile = sys.argv[1]
cmd = sys.argv[2:]

with open(logfile, "ab", buffering=0) as f:
    p = subprocess.Popen(
        cmd,
        stdout=f,
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
        preexec_fn=os.setsid,
    )

print(p.pid)
PY
}

echo "[start.local] backend -> http://$HOST:$BACKEND_PORT (strict)"
echo "[start.local] frontend -> http://$HOST:$FRONTEND_PORT (strict)"

# Backend (non-fatal if environment blocks bind)
if [ "$DETACH" = "1" ]; then
  backend_cmd=$(cat <<EOF
cd "$ROOT_DIR"
if [ -d "backend/.venv" ]; then
  source backend/.venv/bin/activate
elif [ -d ".venv" ]; then
  source .venv/bin/activate
fi
export PYTHONPATH="$ROOT_DIR/backend"
export FLASK_APP=backend.app
export FLASK_ENV=development
export CORS_ALLOWED_ORIGINS="http://127.0.0.1:5173,http://localhost:5173,http://127.0.0.1:5176,http://localhost:5176,http://127.0.0.1:3100,http://localhost:3100"
export ALERT_IMPULSE_1M_PCT="${ALERT_IMPULSE_1M_PCT:-0.75}"
export ALERT_IMPULSE_3M_PCT="${ALERT_IMPULSE_3M_PCT:-1.25}"
export ALERT_IMPULSE_COOLDOWN_SECONDS="${ALERT_IMPULSE_COOLDOWN_SECONDS:-45}"
export ALERT_IMPULSE_DEDUPE_DELTA="${ALERT_IMPULSE_DEDUPE_DELTA:-0.15}"
export ALERT_IMPULSE_TTL_MINUTES="${ALERT_IMPULSE_TTL_MINUTES:-6}"
export ALERTS_STICKY_SECONDS="${ALERTS_STICKY_SECONDS:-120}"
export SENTIMENT_HOST="$SENTIMENT_HOST"
export SENTIMENT_PORT="$SENTIMENT_PORT"
export SENTIMENT_PIPELINE_URL="$SENTIMENT_PIPELINE_URL"
exec flask run --host "$HOST" --port "$BACKEND_PORT"
EOF
)
  start_detached /tmp/mw_backend.log bash -c "$backend_cmd" > "$BACKEND_PID_FILE"
else
  (
    cd "$ROOT_DIR"
    # Activate venv if it exists (check backend/.venv first, then .venv)
    if [ -d "backend/.venv" ]; then
      source backend/.venv/bin/activate
    elif [ -d ".venv" ]; then
      source .venv/bin/activate
    fi
    export PYTHONPATH="$ROOT_DIR/backend"
    export FLASK_APP=backend.app
    export FLASK_ENV=development
    # Export CORS origins for Vite dev ports
    export CORS_ALLOWED_ORIGINS="http://127.0.0.1:5173,http://localhost:5173,http://127.0.0.1:5176,http://localhost:5176,http://127.0.0.1:3100,http://localhost:3100"
    export ALERT_IMPULSE_1M_PCT="${ALERT_IMPULSE_1M_PCT:-0.75}"
    export ALERT_IMPULSE_3M_PCT="${ALERT_IMPULSE_3M_PCT:-1.25}"
    export ALERT_IMPULSE_COOLDOWN_SECONDS="${ALERT_IMPULSE_COOLDOWN_SECONDS:-45}"
    export ALERT_IMPULSE_DEDUPE_DELTA="${ALERT_IMPULSE_DEDUPE_DELTA:-0.15}"
    export ALERT_IMPULSE_TTL_MINUTES="${ALERT_IMPULSE_TTL_MINUTES:-6}"
    export ALERTS_STICKY_SECONDS="${ALERTS_STICKY_SECONDS:-120}"
    export SENTIMENT_HOST="$SENTIMENT_HOST"
    export SENTIMENT_PORT="$SENTIMENT_PORT"
    export SENTIMENT_PIPELINE_URL="$SENTIMENT_PIPELINE_URL"
    flask run --host "$HOST" --port "$BACKEND_PORT"
  ) > /tmp/mw_backend.log 2>&1 &
  echo $! > "$BACKEND_PID_FILE"
fi

# persist chosen ports so helper commands can inspect them
echo "$BACKEND_PORT" > "$BACKEND_PORT_FILE"

# --- start sentiment pipeline (best-effort) ---
port_in_use() {
  local p="$1"
  command -v lsof >/dev/null 2>&1 || return 1
  lsof -nP -iTCP:"$p" -sTCP:LISTEN >/dev/null 2>&1
}

PIPELINE=""
for c in \
  "$ROOT_DIR/scripts/start_sentiment.sh" \
  "$ROOT_DIR/backend/start_sentiment_pipeline.sh" \
  "$ROOT_DIR/start_sentiment_pipeline.sh" \
  "$ROOT_DIR/backend/start_pipeline.sh" \
  "$ROOT_DIR/start_pipeline.sh"
do
  if [ -f "$c" ]; then
    PIPELINE="$c"
    break
  fi
done

if [ -n "$PIPELINE" ]; then
  if port_in_use "$SENTIMENT_PORT"; then
    echo "[start.local] sentiment port ${SENTIMENT_PORT} already in use; assuming pipeline is running, skipping start"
    PIPELINE=""
  fi
fi

if [ -n "$PIPELINE" ]; then
  echo "[start.local] sentiment pipeline: http://${SENTIMENT_HOST}:${SENTIMENT_PORT} (starting via ${PIPELINE})"
  if [ "$DETACH" = "1" ]; then
    pipeline_cmd=$(cat <<EOF
cd "$ROOT_DIR"
SENTIMENT_HOST="$SENTIMENT_HOST" SENTIMENT_PORT="$SENTIMENT_PORT" SENTIMENT_PIPELINE_URL="$SENTIMENT_PIPELINE_URL" exec bash "$PIPELINE"
EOF
)
    start_detached /tmp/mw_pipeline.log bash -c "$pipeline_cmd" > "$PIPELINE_PID_FILE"
  else
    (
      cd "$ROOT_DIR"
      SENTIMENT_HOST="$SENTIMENT_HOST" SENTIMENT_PORT="$SENTIMENT_PORT" SENTIMENT_PIPELINE_URL="$SENTIMENT_PIPELINE_URL" bash "$PIPELINE"
    ) > /tmp/mw_pipeline.log 2>&1 &
    echo $! > "$PIPELINE_PID_FILE"
  fi

  # Wait for pipeline to be ready (best-effort)
  echo "[start.local] waiting for sentiment pipeline to start..."
  i=0
  while [ $i -lt 30 ]; do
    if curl -sS "http://${SENTIMENT_HOST}:${SENTIMENT_PORT}/health" >/dev/null 2>&1; then
      echo "[start.local] sentiment pipeline /health is responding"
      break
    fi
    sleep 1
    i=$((i+1))
  done
else
  echo "[start.local] sentiment pipeline starter not found; skipping pipeline start"
fi

# Frontend — ensure deps then start Vite with env BACKEND_PORT and VITE_PORT
if [ "$DETACH" = "1" ]; then
  frontend_cmd=$(cat <<EOF
cd "$ROOT_DIR/frontend"
if [ ! -d node_modules ]; then
  echo "[start.local] installing frontend dependencies..."
  npm install
fi
VITE_API_URL="http://$HOST:$BACKEND_PORT" \
VITE_API_BASE_URL="http://$HOST:$BACKEND_PORT" \
VITE_SENTIMENT_BASE_URL="http://$HOST:$BACKEND_PORT" \
VITE_PROXY_TARGET="http://$HOST:$BACKEND_PORT" \
BACKEND_PORT="$BACKEND_PORT" VITE_PORT="$FRONTEND_PORT" \
exec npm run dev -- --host "$HOST" --port "$FRONTEND_PORT" --strictPort
EOF
)
  start_detached /tmp/mw_frontend.log bash -c "$frontend_cmd" > "$FRONTEND_PID_FILE"
else
  (
    cd "$ROOT_DIR/frontend"
    if [ ! -d node_modules ]; then
      echo "[start.local] installing frontend dependencies..."
      npm install
    fi
    VITE_API_URL="http://$HOST:$BACKEND_PORT" \
    VITE_PROXY_TARGET="http://$HOST:$BACKEND_PORT" \
    BACKEND_PORT="$BACKEND_PORT" VITE_PORT="$FRONTEND_PORT" \
    npm run dev -- --host "$HOST" --port "$FRONTEND_PORT" --strictPort
  ) > /tmp/mw_frontend.log 2>&1 &
  echo $! > "$FRONTEND_PID_FILE"
fi
echo "$FRONTEND_PORT" > "$FRONTEND_PORT_FILE"

echo "[start.local] backend pid: $(cat "$BACKEND_PID_FILE") (written to $BACKEND_PID_FILE)"
echo "[start.local] frontend pid: $(cat "$FRONTEND_PID_FILE") (written to $FRONTEND_PID_FILE)"

# Block until both backend /api/data and frontend root respond (short timeout)
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
    elif curl -sS "http://$HOST:$BACKEND_PORT/api/data" >/dev/null 2>&1; then
      backend_ok=1
      echo "[start.local] backend /api/data is responding"
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
  echo "[start.local] WARNING: backend did not respond to /api/data after ${WAIT_RETRIES} attempts"
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

echo "[start.local] logs → /tmp/mw_backend.log /tmp/mw_frontend.log /tmp/mw_pipeline.log"
echo "[start.local] to follow logs live: TAIL_LOGS=1 ./start_local.sh"
echo ""
echo "[start.local] services:"
echo "  backend:   http://$HOST:$BACKEND_PORT"
echo "  frontend:  http://$HOST:$FRONTEND_PORT"
echo "  pipeline:  http://$SENTIMENT_HOST:$SENTIMENT_PORT"
