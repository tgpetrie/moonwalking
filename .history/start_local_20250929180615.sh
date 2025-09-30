#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR"

# Defaults
VITE_PORT="${VITE_PORT:-3100}"
BACKEND_PORT="${BACKEND_PORT:-5001}"
export BACKEND_PORT

# Ensure the chosen ports are free (kill any stray listeners)
kill_port() {
  local port="$1"
  if command -v lsof >/dev/null 2>&1; then
    local pids
    pids=$(lsof -tiTCP:"${port}" -sTCP:LISTEN || true)
    if [ -n "${pids}" ]; then
      echo "[start_local] freeing port ${port} (killing: ${pids})"
      kill ${pids} 2>/dev/null || true
      # give the OS a moment to release the port
      sleep 0.5
    fi
  fi
}

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

# Write frontend/.env.local for Vite & API/WS base
# Only write if the file does not already exist, unless FORCE_ENV_WRITE=1
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

# Start backend API (kill any existing process bound to the same port)
(
  cd backend
  exec python app.py --host 127.0.0.1 --port "${BACKEND_PORT}" --kill-port
) &
BACK_PID=$!

# write pidfile for stop_all
: "${STATE_DIR:=/tmp/bhabit_run}"
mkdir -p "${STATE_DIR}" 2>/dev/null || true
echo "$BACK_PID" > "${STATE_DIR}/backend.pid" 2>/dev/null || true

# Start Vite
(
  cd frontend
  # dev script already sets --host, we only pass the port override
  npm run dev -- --port "${VITE_PORT}"
) &
VITE_PID=$!

echo "$VITE_PID" > "${STATE_DIR}/frontend.pid" 2>/dev/null || true

stop_local_cleanup() {
  echo
  echo "[start_local] stopping..."
  kill ${BACK_PID:-} ${VITE_PID:-} 2>/dev/null || true
  rm -f "${STATE_DIR}/backend.pid" "${STATE_DIR}/frontend.pid" 2>/dev/null || true
}

trap 'stop_local_cleanup' INT TERM EXIT

echo "[start_local] open http://127.0.0.1:${VITE_PORT} ; API http://127.0.0.1:${BACKEND_PORT}"
wait
