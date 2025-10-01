#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR"

# Defaults
VITE_PORT="${VITE_PORT:-3100}"
BACKEND_PORT="${BACKEND_PORT:-5001}"
export BACKEND_PORT

# PID files & logs
BACKEND_PID_FILE="${ROOT_DIR}/backend/backend.pid"
VITE_PID_FILE="${ROOT_DIR}/frontend/vite.pid"
BACKEND_LOG="${ROOT_DIR}/backend/server.stdout"
VITE_LOG="${ROOT_DIR}/frontend/vite.stdout"

# Helpers
is_running() {
  local pid="$1"
  [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null
}

safe_kill_pidfile() {
  local file="$1"
  if [ -f "$file" ]; then
    local pid
    pid=$(cat "$file" || true)
    if [ -n "$pid" ] && is_running "$pid"; then
      echo "[start_local] stopping process $pid from $file"
      kill "$pid" 2>/dev/null || true
      # give it a moment to exit
      for _ in {1..10}; do
        if ! is_running "$pid"; then break; fi
        sleep 0.2
      done
    fi
    rm -f "$file"
  fi
}

wait_for_port() {
  local host="127.0.0.1"
  local port="$1"
  local timeout_secs="${2:-30}"
  local start
  start=$(date +%s)
  echo "[start_local] waiting for ${host}:${port} to be available (timeout ${timeout_secs}s)"
  while true; do
    # bash /dev/tcp as portable check on macOS/linux with bash
    if (echo > /dev/tcp/${host}/${port}) >/dev/null 2>&1; then
      echo "[start_local] ${host}:${port} is listening"
      return 0
    fi
    now=$(date +%s)
    if [ $((now - start)) -ge "$timeout_secs" ]; then
      echo "[start_local] timeout waiting for ${host}:${port}"
      return 1
    fi
    sleep 0.5
  done
}

# Ensure the chosen ports are free (kill any stray listeners) using lsof where available
kill_port() {
  local port="$1"
  if command -v lsof >/dev/null 2>&1; then
    local pids
    pids=$(lsof -tiTCP:"${port}" -sTCP:LISTEN || true)
    if [ -n "${pids}" ]; then
      echo "[start_local] freeing port ${port} (killing: ${pids})"
      kill ${pids} 2>/dev/null || true
      sleep 0.5
    fi
  fi
}

# Stop any previously-recorded processes so we can restart cleanly. FORCE_START
# remains supported but no longer required for the common "replace whatever is
# running" flow.
maybe_cleanup_pidfile() {
  local file="$1" name="$2"

  # Nothing to do if the pidfile is missing.
  [ -f "$file" ] || return 0

  local pid
  pid=$(cat "$file" 2>/dev/null || true)

  # Remove empty or unreadable pid files.
  if [ -z "$pid" ]; then
    rm -f "$file"
    return 0
  fi

  if is_running "$pid"; then
    if [ "${FORCE_START:-0}" = "1" ]; then
      echo "[start_local] replacing existing ${name} process ($pid)"
    else
      echo "[start_local] stopping existing ${name} process ($pid)"
    fi
    safe_kill_pidfile "$file"
  else
    rm -f "$file"
  fi
}

maybe_cleanup_pidfile "$BACKEND_PID_FILE" backend
maybe_cleanup_pidfile "$VITE_PID_FILE" vite

kill_port "${BACKEND_PORT}"
kill_port "${VITE_PORT}"

# Activate venv
if [ -f .venv/bin/activate ]; then
  # shellcheck disable=SC1091
  . .venv/bin/activate
else
  echo "[start_local] venv missing. Run ./setup_dev.sh first." >&2
  exit 1
fi

# Write frontend/.env.local for Vite & API/WS base (only when missing unless forced)
mkdir -p frontend
if [ "${FORCE_ENV_WRITE:-0}" = "1" ] || [ ! -f frontend/.env.local ]; then
  cat > frontend/.env.local <<EOF_ENV
VITE_API_URL=http://127.0.0.1:${BACKEND_PORT}/api
VITE_WS_URL=ws://127.0.0.1:${BACKEND_PORT}/ws
EOF_ENV
  echo "[start_local] wrote frontend/.env.local"
else
  echo "[start_local] frontend/.env.local exists; not overwriting (set FORCE_ENV_WRITE=1 to force)"
fi

echo "[start_local] backend on ${BACKEND_PORT}, Vite on ${VITE_PORT}"

# stop_all will be registered on exit to ensure children are cleaned up
stop_all() {
  echo; echo "[start_local] stopping..."
  safe_kill_pidfile "$VITE_PID_FILE"
  safe_kill_pidfile "$BACKEND_PID_FILE"
}

trap stop_all INT TERM EXIT

# Start backend
mkdir -p backend
echo "[start_local] starting backend (logs -> ${BACKEND_LOG})"
cd backend
nohup python app.py --host 127.0.0.1 --port "${BACKEND_PORT}" --kill-port > "${BACKEND_LOG}" 2>&1 &
BACK_PID=$!
echo "$BACK_PID" > "$BACKEND_PID_FILE"
cd "$ROOT_DIR"

# Start Vite
mkdir -p frontend
echo "[start_local] starting Vite (logs -> ${VITE_LOG})"
cd frontend
nohup npm run dev -- --port "${VITE_PORT}" > "${VITE_LOG}" 2>&1 &
VITE_PID=$!
echo "$VITE_PID" > "$VITE_PID_FILE"
cd "$ROOT_DIR"

# Wait for services to be ready
if ! wait_for_port "${BACKEND_PORT}" 30; then
  echo "[start_local] backend did not come up within timeout; see ${BACKEND_LOG}" >&2
fi
if ! wait_for_port "${VITE_PORT}" 30; then
  echo "[start_local] vite did not come up within timeout; see ${VITE_LOG}" >&2
fi

echo "[start_local] open http://127.0.0.1:${VITE_PORT} ; API http://127.0.0.1:${BACKEND_PORT}"

# follow logs if requested; otherwise wait on child PIDs so trap works
if [ "${FOLLOW_LOGS:-0}" = "1" ]; then
  tail -n +1 -f "${BACKEND_LOG}" "${VITE_LOG}"
else
  # wait on the two PIDs by polling their liveness so the script remains running and trap can catch shutdown
  echo "[start_local] entering monitor loop (pid backend=${BACK_PID:-}, vite=${VITE_PID:-})"
  while true; do
    still=false
    if [ -n "${BACK_PID:-}" ] && is_running "${BACK_PID}"; then
      still=true
    fi
    if [ -n "${VITE_PID:-}" ] && is_running "${VITE_PID}"; then
      still=true
    fi
    if [ "$still" = false ]; then
      echo "[start_local] both processes exited; leaving monitor loop"
      break
    fi
    sleep 0.5
  done
fi
