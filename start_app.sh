#!/usr/bin/env bash
set -euo pipefail
export LC_ALL=C
# ///////////////////////////////////////////////////////////////////////////////////////////////////////
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

# --- helpers ---
port_in_use() {
  local p="$1"
  command -v lsof >/dev/null 2>&1 || return 1
  lsof -nP -iTCP:"$p" -sTCP:LISTEN >/dev/null 2>&1
}

find_free_port() {
  local start="$1"
  local p="$start"
  while port_in_use "$p"; do
    p=$((p+1))
  done
  echo "$p"
}

write_frontend_env() {
  local host="$1"
  local port="$2"
  local env_file="frontend/.env.local"
  local tmp_file="${env_file}.tmp"
  mkdir -p "$(dirname "$env_file")"
  cat >"$tmp_file" <<EOF
VITE_API_BASE_URL=http://${host}:${port}
VITE_API_BASE=http://${host}:${port}
VITE_API_URL=http://${host}:${port}
VITE_PROXY_TARGET=http://${host}:${port}
EOF
  mv -f "$tmp_file" "$env_file"
}

wait_for_listener() {
  local port="$1"
  local seconds="${2:-15}"
  if ! command -v lsof >/dev/null 2>&1; then
    return 0
  fi
  local i=0
  while [ "$i" -lt "$seconds" ]; do
    if lsof -nP -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
    i=$((i+1))
  done
  return 1
}

wait_for_http() {
  local url="$1"
  local seconds="${2:-20}"
  local i=0
  while [ "$i" -lt "$seconds" ]; do
    if command -v curl >/dev/null 2>&1; then
      if curl -fsS "$url" >/dev/null 2>&1; then return 0; fi
    else
      # curl not available; don't block start
      return 0
    fi
    sleep 1
    i=$((i+1))
  done
  return 1
}

# Kill anything currently listening on a port (macOS/Linux)
kill_listeners_on_port() {
  local port="$1"
  local pids=""

  if command -v lsof >/dev/null 2>&1; then
    # PIDs listening on TCP port
    pids="$(lsof -nP -t -iTCP:"${port}" -sTCP:LISTEN 2>/dev/null | sort -u || true)"
  else
    echo "[start_app] ERROR: lsof not found; cannot reclaim port ${port}"
    return 1
  fi

  if [ -z "${pids}" ]; then
    return 0
  fi

  echo "[start_app] reclaiming port ${port} (killing PIDs: ${pids})"

  # Try graceful first
  kill ${pids} 2>/dev/null || true

  # Wait briefly for exit
  local i=0
  while [ $i -lt 15 ]; do
    if ! lsof -nP -iTCP:"${port}" -sTCP:LISTEN >/dev/null 2>&1; then
      return 0
    fi
    sleep 0.2
    i=$((i+1))
  done

  # Force kill if still holding the port
  echo "[start_app] port ${port} still busy; force killing PIDs: ${pids}"
  kill -9 ${pids} 2>/dev/null || true

  # Final confirm
  local j=0
  while [ $j -lt 10 ]; do
    if ! lsof -nP -iTCP:"${port}" -sTCP:LISTEN >/dev/null 2>&1; then
      return 0
    fi
    sleep 0.2
    j=$((j+1))
  done

  echo "[start_app] ERROR: port ${port} still in use after kill attempts"
  return 1
}

cleanup() {
  if [ -n "${BACKEND_PID:-}" ]; then
    if [ "${BACKEND_USE_GROUP_KILL:-0}" = "1" ]; then
      kill -TERM "-${BACKEND_PID}" >/dev/null 2>&1 || true
    else
      pkill -TERM -P "${BACKEND_PID}" >/dev/null 2>&1 || true
      kill -TERM "${BACKEND_PID}" >/dev/null 2>&1 || true
    fi
  fi
  if [ -n "${PIPELINE_PID:-}" ]; then
    pkill -TERM -P "${PIPELINE_PID}" >/dev/null 2>&1 || true
    kill -TERM "${PIPELINE_PID}" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT INT TERM

# --- config (override via env) ---
HOST="${HOST:-127.0.0.1}"

REQ_BACKEND_PORT="${BACKEND_PORT:-5003}"
REQ_FRONTEND_PORT="${FRONTEND_PORT:-5173}"

# Force fixed ports (no fallback). Reclaim them before launch.
BACKEND_PORT="$REQ_BACKEND_PORT"
FRONTEND_PORT="$REQ_FRONTEND_PORT"

# Always reclaim ports before launching (prevents "stuck" runs)
kill_listeners_on_port "${BACKEND_PORT}"
kill_listeners_on_port "${FRONTEND_PORT}"

SENTIMENT_HOST="${SENTIMENT_HOST:-$HOST}"
SENTIMENT_PORT="${SENTIMENT_PORT:-8002}"
SENTIMENT_PIPELINE_URL="http://${SENTIMENT_HOST}:${SENTIMENT_PORT}"

# Also reclaim sentiment port so it never "sticks"
kill_listeners_on_port "${SENTIMENT_PORT}"

export HOST BACKEND_PORT FRONTEND_PORT SENTIMENT_HOST SENTIMENT_PORT SENTIMENT_PIPELINE_URL

BACKEND_URL="http://${HOST}:${BACKEND_PORT}"
export BACKEND_URL

if [ "$BACKEND_PORT" != "$REQ_BACKEND_PORT" ]; then
  echo "[start_app] backend port ${REQ_BACKEND_PORT} busy -> using ${BACKEND_PORT}"
fi
if [ "$FRONTEND_PORT" != "$REQ_FRONTEND_PORT" ]; then
  echo "[start_app] frontend port ${REQ_FRONTEND_PORT} busy -> using ${FRONTEND_PORT}"
fi

echo "[start_app] backend:  http://${HOST}:${BACKEND_PORT}"
echo "[start_app] frontend: http://${HOST}:${FRONTEND_PORT}"

echo "[start_app] writing frontend/.env.local -> http://${HOST}:${BACKEND_PORT}"
write_frontend_env "$HOST" "$BACKEND_PORT"
echo "[start_app] using frontend/.env.local"

echo "[start_app] ports backend=http://${HOST}:${BACKEND_PORT} frontend=http://${HOST}:${FRONTEND_PORT}"

# --- start backend (once) ---
BACKEND_PID=""
BACKEND_USE_GROUP_KILL=0

start_backend_bg() {
  if command -v setsid >/dev/null 2>&1; then
    BACKEND_USE_GROUP_KILL=1
    setsid env \
      HOST="$HOST" \
      PORT="$BACKEND_PORT" \
      BACKEND_PORT="$BACKEND_PORT" \
      SENTIMENT_HOST="$SENTIMENT_HOST" \
      SENTIMENT_PORT="$SENTIMENT_PORT" \
      SENTIMENT_PIPELINE_URL="$SENTIMENT_PIPELINE_URL" \
      bash -lc 'cd backend && ./start_backend_strict.sh' &
  else
    BACKEND_USE_GROUP_KILL=0
    (
      cd backend
      env \
        HOST="$HOST" \
        PORT="$BACKEND_PORT" \
        BACKEND_PORT="$BACKEND_PORT" \
        SENTIMENT_HOST="$SENTIMENT_HOST" \
        SENTIMENT_PORT="$SENTIMENT_PORT" \
        SENTIMENT_PIPELINE_URL="$SENTIMENT_PIPELINE_URL" \
        ./start_backend_strict.sh
    ) &
  fi
  BACKEND_PID=$!
}

start_backend_bg

# Fast readiness: backend process is listening and responding.
wait_for_http "${BACKEND_URL}/health" 60

# Warm-up probe: /data can be heavy; don't block startup on it.
wait_for_http "${BACKEND_URL}/data" 30 || true

# --- start sentiment pipeline (best-effort) ---
PIPELINE=""
for c in \
  "./scripts/start_sentiment.sh" \
  "./backend/start_sentiment_pipeline.sh" \
  "./start_sentiment_pipeline.sh" \
  "./backend/start_pipeline.sh" \
  "./start_pipeline.sh"
do
  if [ -f "$c" ]; then
    PIPELINE="$c"
    break
  fi
done

if [ -n "$PIPELINE" ]; then
  if port_in_use "$SENTIMENT_PORT"; then
    echo "[start_app] sentiment port ${SENTIMENT_PORT} already in use; assuming pipeline is running, skipping start"
    PIPELINE=""
  fi
fi

if [ -n "$PIPELINE" ]; then
  echo "[start_app] sentiment pipeline: http://${SENTIMENT_HOST}:${SENTIMENT_PORT} (starting in background via ${PIPELINE})"
  (
    SENTIMENT_HOST="$SENTIMENT_HOST" SENTIMENT_PORT="$SENTIMENT_PORT" SENTIMENT_PIPELINE_URL="$SENTIMENT_PIPELINE_URL" bash "$PIPELINE"
  ) &
  PIPELINE_PID=$!
  wait_for_http "http://${SENTIMENT_HOST}:${SENTIMENT_PORT}/health" 30 || true
else
  echo "[start_app] sentiment pipeline starter not found; skipping pipeline start"
fi

# --- start frontend (foreground) ---
cd frontend
export VITE_PROXY_TARGET="http://${HOST}:${BACKEND_PORT}"

# Re-reclaim frontend port right before Vite (closes any zombie that grabbed it during backend warmup)
kill_listeners_on_port "${FRONTEND_PORT}"

# Auto-open on macOS
if [ "$(uname -s)" = "Darwin" ]; then
  (sleep 2; open "http://${HOST}:${FRONTEND_PORT}/" >/dev/null 2>&1 || true) &
fi

npm run dev -- --host "$HOST" --port "$FRONTEND_PORT"
