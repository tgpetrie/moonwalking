#!/usr/bin/env bash
# Local dev launcher for Moonwalkings
# - Starts Flask backend on PORT (default 5002)
# - Optionally starts Cloudflare Worker via wrangler on EDGE_PORT (default 8787) if WRANGLER=1
# - Starts Vite frontend on VITE_PORT (default 5173) using pnpm if available, else npm

set -euo pipefail

PORT=${PORT:-5002}
HOST=${HOST:-127.0.0.1}
EDGE_PORT=${EDGE_PORT:-8787}
VITE_PORT=${VITE_PORT:-5173}
WRANGLER=${WRANGLER:-0}
REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"

: "${WORKER_ORIGIN:=http://127.0.0.1:${EDGE_PORT}}"
export WORKER_ORIGIN

notice() { printf "\033[1;34m==> %s\033[0m\n" "$*"; }
warn()   { printf "\033[1;33m[warn]\033[0m %s\n" "$*"; }
err()    { printf "\033[1;31m[err]\033[0m %s\n" "$*"; }

is_listening() {
  lsof -nP -iTCP:"$1" -sTCP:LISTEN >/dev/null 2>&1
}

kill_port() {
  local p="$1"
  local pids
  pids=$(lsof -ti tcp:"$p" || true)
  if [[ -n "$pids" ]]; then
    warn "Killing processes on port $p: $pids"
    kill -9 $pids || true
  fi
}

activate_venv() {
  if [[ -f "$REPO_ROOT/.venv/bin/activate" ]]; then
    # shellcheck disable=SC1091
    source "$REPO_ROOT/.venv/bin/activate"
  else
    warn "No .venv found; using system python3"
  fi
}

start_backend() {
  if is_listening "$PORT"; then
    notice "Backend already listening on :$PORT"
    return
  fi
  notice "Starting backend on $HOST:$PORT"
  (
    cd "$REPO_ROOT"
    PORT="$PORT" HOST="$HOST" nohup python3 -u -m flask --app backend/app run --host "$HOST" --port "$PORT" > /tmp/moonwalkings.backend.log 2>&1 &
    echo $! > /tmp/moonwalkings.backend.pid
  )
  sleep 1
  if is_listening "$PORT"; then
    notice "Backend up: http://$HOST:$PORT"
  else
    err "Backend failed to start; see /tmp/moonwalkings.backend.log"
    exit 1
  fi
}

start_wrangler() {
  if [[ "$WRANGLER" == "0" ]]; then
    return
  fi
  if ! command -v wrangler >/dev/null 2>&1; then
    warn "wrangler not found; skipping worker"
    return
  fi
  if is_listening "$EDGE_PORT"; then
    notice "Worker already listening on :$EDGE_PORT"
    return
  fi
  notice "Starting wrangler dev on :$EDGE_PORT"
  (
    cd "$REPO_ROOT/workers"
    nohup npx wrangler dev --ip 127.0.0.1 --port "$EDGE_PORT" --local > /tmp/moonwalkings.worker.log 2>&1 &
    echo $! > /tmp/moonwalkings.worker.pid
  )
  sleep 1
  if is_listening "$EDGE_PORT"; then
    notice "Worker up: http://127.0.0.1:$EDGE_PORT"
  else
    warn "Worker failed to start; showing last 60 lines of /tmp/moonwalkings.worker.log"
    if [[ -f /tmp/moonwalkings.worker.log ]]; then
      tail -n 60 /tmp/moonwalkings.worker.log || true
    else
      warn "(no worker log file yet)"
    fi
    warn "Common fixes:"
    warn "  • Port busy → lsof -ti :${EDGE_PORT} | xargs -r kill -9"
    warn "  • Old wrangler → npm i -g wrangler@4.42.0"
    warn "  • Compat date mismatch → set compatibility_date = \"2025-10-01\" in workers/wrangler.toml"
    warn "  • Try another port → EDGE_PORT=$((EDGE_PORT+1)) WRANGLER=1 ./start_backend_local.sh"
  fi
}

ensure_pnpm() {
  if command -v pnpm >/dev/null 2>&1; then
    return
  fi
  if command -v volta >/dev/null 2>&1; then
    notice "Installing pnpm via Volta"
    volta install pnpm || true
  else
    notice "Enabling pnpm via corepack"
    corepack enable || true
    corepack prepare pnpm@latest --activate || true
  fi
}

start_frontend() {
  if is_listening "$VITE_PORT"; then
    notice "Frontend already listening on :$VITE_PORT"
    return
  fi
  ensure_pnpm
  notice "Starting Vite frontend on :$VITE_PORT"
  (
    cd "$REPO_ROOT/frontend"
    if [[ ! -d node_modules ]]; then
      notice "Installing frontend deps"
      if command -v pnpm >/dev/null 2>&1; then pnpm install; else npm install --no-audit --no-fund; fi
    fi
    if command -v pnpm >/dev/null 2>&1; then
      pnpm run dev -- --host 127.0.0.1 --port "$VITE_PORT" --strictPort > /tmp/moonwalkings.vite.log 2>&1 &
    else
      npm run dev -- --host 127.0.0.1 --port "$VITE_PORT" --strictPort > /tmp/moonwalkings.vite.log 2>&1 &
    fi
    echo $! > /tmp/moonwalkings.vite.pid
  )
  sleep 1
  if is_listening "$VITE_PORT"; then
    notice "Frontend up: http://127.0.0.1:$VITE_PORT"
  else
    warn "Frontend may not be ready yet; tail /tmp/moonwalkings.vite.log"
  fi
}

### main
if [[ "${1:-}" == "kill" ]]; then
  notice "Stopping dev stack"
  kill_port "$PORT"
  kill_port "$EDGE_PORT"
  kill_port "$VITE_PORT"
  exit 0
fi

notice "Launching local stack"
notice "WORKER_ORIGIN=${WORKER_ORIGIN}"
activate_venv
start_backend
start_wrangler
start_frontend

notice "Health checks"
if curl -fsS "http://$HOST:$PORT/api/health" >/dev/null; then
  notice "Backend OK"
else
  warn "Backend health failed"
fi

notice "Open UI: http://127.0.0.1:$VITE_PORT"
notice "Logs: /tmp/moonwalkings.backend.log | /tmp/moonwalkings.vite.log | /tmp/moonwalkings.worker.log"