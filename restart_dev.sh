#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

BACKEND_HOST="${BACKEND_HOST:-127.0.0.1}"
BACKEND_PORT="${BACKEND_PORT:-5001}"
FRONTEND_HOST="${FRONTEND_HOST:-127.0.0.1}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"

BACKEND_PID_FILE="${BACKEND_PID_FILE:-/tmp/mw_backend.pid}"
FRONTEND_PID_FILE="${FRONTEND_PID_FILE:-/tmp/mw_frontend.pid}"
BACKEND_LOG="${BACKEND_LOG:-/tmp/mw_backend.log}"
FRONTEND_LOG="${FRONTEND_LOG:-/tmp/mw_frontend.log}"

say() { printf "\n[restart.dev] %s\n" "$*"; }

kill_pidfile() {
  local f="$1"
  if [[ -f "$f" ]]; then
    local pid
    pid="$(cat "$f" 2>/dev/null || true)"
    if [[ -n "${pid:-}" ]] && kill -0 "$pid" 2>/dev/null; then
      say "killing pid $pid from $f"
      kill "$pid" 2>/dev/null || true
      sleep 0.2
      kill -9 "$pid" 2>/dev/null || true
    fi
    rm -f "$f"
  fi
}

free_port() {
  local port="$1"
  say "freeing port $port"
  local pids
  pids="$(lsof -ti tcp:"$port" 2>/dev/null || true)"
  if [[ -n "$pids" ]]; then
    # shellcheck disable=SC2086
    kill $pids 2>/dev/null || true
    sleep 0.2
    # shellcheck disable=SC2086
    kill -9 $pids 2>/dev/null || true
  fi
}

wait_ok() {
  local url="$1"
  local tries="${2:-30}"
  local delay="${3:-0.25}"
  for _ in $(seq 1 "$tries"); do
    if curl -fsS "$url" >/dev/null 2>&1; then
      say "ok: $url"
      return 0
    fi
    sleep "$delay"
  done
  say "timeout waiting for $url"
  return 1
}

say "stopping old processes"
kill_pidfile "$BACKEND_PID_FILE"
kill_pidfile "$FRONTEND_PID_FILE"

free_port "$BACKEND_PORT"
free_port "$FRONTEND_PORT"

say "starting backend (STRICT) on ${BACKEND_HOST}:${BACKEND_PORT}"
(
  cd "$ROOT_DIR/backend"
  export HOST="$BACKEND_HOST"
  export PORT="$BACKEND_PORT"
  # must not auto-hop; prefer venv python, then python3, then python
  if [[ -f "$ROOT_DIR/backend/.venv/bin/python" ]]; then
    exec "$ROOT_DIR/backend/.venv/bin/python" -u app.py
  elif [[ -f "$ROOT_DIR/.venv/bin/python" ]]; then
    exec "$ROOT_DIR/.venv/bin/python" -u app.py
  elif command -v python3 >/dev/null 2>&1; then
    exec python3 -u app.py
  else
    exec python -u app.py
  fi
) >"$BACKEND_LOG" 2>&1 &
echo $! >"$BACKEND_PID_FILE"
BACK_PID="$(cat "$BACKEND_PID_FILE")"

say "starting frontend (Vite) on ${FRONTEND_HOST}:${FRONTEND_PORT}"
(
  cd "$ROOT_DIR/frontend"
  export VITE_HOST="$FRONTEND_HOST"
  export VITE_PORT="$FRONTEND_PORT"
  exec npm run dev -- --host "$FRONTEND_HOST" --port "$FRONTEND_PORT"
) >"$FRONTEND_LOG" 2>&1 &
echo $! >"$FRONTEND_PID_FILE"
FRONT_PID="$(cat "$FRONTEND_PID_FILE")"

say "waiting for health"
wait_ok "http://${BACKEND_HOST}:${BACKEND_PORT}/api/health" 40 0.25 || true
wait_ok "http://${BACKEND_HOST}:${BACKEND_PORT}/api/data" 40 0.25 || true
wait_ok "http://${FRONTEND_HOST}:${FRONTEND_PORT}/" 40 0.25 || true

say "logs:"
say "  backend:  tail -n 80 $BACKEND_LOG"
say "  frontend: tail -n 80 $FRONTEND_LOG"

say "pids:"
say "  backend:  $BACK_PID"
say "  frontend: $FRONT_PID"
