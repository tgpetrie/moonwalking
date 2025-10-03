#!/usr/bin/env bash
# dev_bootstrap.sh — safe bootstrap + health probe for Moonwalkings
set -euo pipefail

BACKEND_PORT="${BACKEND_PORT:-5001}"
WORKER_PORT="${WORKER_PORT:-8787}"
VITE_PORT="${VITE_PORT:-3100}"
BACKEND_HEALTH="http://127.0.0.1:${BACKEND_PORT}/api/health"

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
LOG_DIR="$ROOT_DIR/.logs"
mkdir -p "$LOG_DIR"

log() { printf "[dev_bootstrap] %s\n" "$*"; }
err() { printf "[dev_bootstrap][ERR] %s\n" "$*" >&2; }
have() { command -v "$1" >/dev/null 2>&1; }

probe_health() {
  local url="$1"; local retries="${2:-20}"; local delay="${3:-0.5}";
  for ((i=1;i<=retries;i++)); do
    if curl -fsS "$url" >/dev/null; then
      log "Healthy: $url"; return 0
    fi
    sleep "$delay"
  done
  err "Timed out waiting for: $url"; return 1
}

start_backend() {
  if [[ -x "$ROOT_DIR/scripts/start_backend.sh" ]]; then
    log "Starting backend via scripts/start_backend.sh (PORT=$BACKEND_PORT)"
    BACKEND_PORT="$BACKEND_PORT" nohup "$ROOT_DIR/scripts/start_backend.sh" \
      >"$LOG_DIR/backend.stdout" 2>"$LOG_DIR/backend.stderr" & echo $! >"$LOG_DIR/backend.pid"
    return 0
  fi
  if [[ -f "$ROOT_DIR/backend/app.py" ]]; then
    log "Starting backend via python backend/app.py (PORT=$BACKEND_PORT)"
    BACKEND_PORT="$BACKEND_PORT" nohup python "$ROOT_DIR/backend/app.py" \
      >"$LOG_DIR/backend.stdout" 2>"$LOG_DIR/backend.stderr" & echo $! >"$LOG_DIR/backend.pid"
    return 0
  fi
  err "No backend start script found. Skipping."
}

start_worker() {
  if [[ -x "$ROOT_DIR/scripts/start_worker.sh" ]]; then
    log "Starting Worker via scripts/start_worker.sh (PORT=$WORKER_PORT)"
    WORKER_PORT="$WORKER_PORT" nohup "$ROOT_DIR/scripts/start_worker.sh" \
      >"$LOG_DIR/worker.stdout" 2>"$LOG_DIR/worker.stderr" & echo $! >"$LOG_DIR/worker.pid"
    return 0
  fi
  if have wrangler && [[ -f "$ROOT_DIR/wrangler.toml" || -d "$ROOT_DIR/workers" ]]; then
    log "Starting Cloudflare Worker locally via wrangler dev (PORT=$WORKER_PORT)"
    nohup wrangler dev --local --port "$WORKER_PORT" \
      >"$LOG_DIR/worker.stdout" 2>"$LOG_DIR/worker.stderr" & echo $! >"$LOG_DIR/worker.pid"
    return 0
  fi
  err "No Worker start method found. Skipping."
}

start_vite() {
  if [[ -x "$ROOT_DIR/scripts/start_frontend.sh" ]]; then
    log "Starting Vite via scripts/start_frontend.sh (PORT=$VITE_PORT)"
    VITE_PORT="$VITE_PORT" nohup "$ROOT_DIR/scripts/start_frontend.sh" \
      >"$LOG_DIR/vite.stdout" 2>"$LOG_DIR/vite.stderr" & echo $! >"$LOG_DIR/vite.pid"
    return 0
  fi
  if have npm && [[ -f "$ROOT_DIR/frontend/package.json" ]]; then
    log "Starting Vite via npm (PORT=$VITE_PORT)"
    ( cd "$ROOT_DIR/frontend" && PORT="$VITE_PORT" nohup npm run dev \
        >"$LOG_DIR/vite.stdout" 2>"$LOG_DIR/vite.stderr" & echo $! >"$LOG_DIR/vite.pid" )
    return 0
  fi
  err "No frontend start method found. Skipping."
}

stop_all() {
  for svc in backend worker vite; do
    if [[ -f "$LOG_DIR/$svc.pid" ]]; then
      pid=$(cat "$LOG_DIR/$svc.pid" || true)
      if [[ -n "${pid:-}" ]] && kill -0 "$pid" 2>/dev/null; then
        log "Stopping $svc (pid=$pid)"; kill "$pid" 2>/dev/null || true
      fi
      rm -f "$LOG_DIR/$svc.pid"
    fi
  done
}

status() {
  for svc in backend worker vite; do
    if [[ -f "$LOG_DIR/$svc.pid" ]]; then
      pid=$(cat "$LOG_DIR/$svc.pid" || true)
      if [[ -n "${pid:-}" ]] && kill -0 "$pid" 2>/dev/null; then
        log "$svc: RUNNING (pid=$pid)"
      else
        log "$svc: STOPPED"
      fi
    else
      log "$svc: STOPPED"
    fi
  done
}

usage() {
  cat <<USAGE
Usage: $0 [run|stop|status|probe]
  run    Start available services and probe backend health
  stop   Stop services started by this script
  status Show status of services
  probe  Only probe backend health

Env: BACKEND_PORT=$BACKEND_PORT WORKER_PORT=$WORKER_PORT VITE_PORT=$VITE_PORT
USAGE
}

cmd="${1:-run}"; shift || true
case "$cmd" in
  run)
    log "Bootstrap starting"
    start_backend || true
    start_worker  || true
    start_vite    || true
    log "Probing health: $BACKEND_HEALTH"
    probe_health "$BACKEND_HEALTH" 40 0.5 || exit 1
    log "OK. Tail recent logs:"
    for f in backend.stdout worker.stdout vite.stdout; do
      [[ -f "$LOG_DIR/$f" ]] && { echo "--- $f (last 40 lines) ---"; tail -n 40 "$LOG_DIR/$f" || true; }
    done
    ;;
  stop)   stop_all ;;
  status) status ;;
  probe)  probe_health "$BACKEND_HEALTH" 1 0.1 || exit 1 ;;
  *) usage; exit 1;;
esac

#!/usr/bin/env bash
cmd="${1:-run}"; shift || true
case "$cmd" in
  run)
    log "Bootstrap starting"
    start_backend || true
    start_worker  || true
    start_vite    || true
    log "Probing health: $BACKEND_HEALTH"
    probe_health "$BACKEND_HEALTH" 40 0.5 || exit 1
    log "OK. Tail recent logs:"
    for f in backend.stdout worker.stdout vite.stdout; do
      [[ -f "$LOG_DIR/$f" ]] && { echo "--- $f (last 40 lines) ---"; tail -n 40 "$LOG_DIR/$f" || true; }
    done
    ;;
  stop)   stop_all ;;
  status) status ;;
  probe)  probe_health "$BACKEND_HEALTH" 1 0.1 || exit 1 ;;
  *) usage; exit 1;;
esac

      >"$LOG_DIR/backend.stdout" 2>"$LOG_DIR/backend.stderr" & echo $! >"$LOG_DIR/backend.pid"
    return 0
  fi
  err "No backend start script found. Skipping."
}

start_worker() {
  if [[ -x "$ROOT_DIR/scripts/start_worker.sh" ]]; then
    log "Starting Worker via scripts/start_worker.sh (PORT=$WORKER_PORT)"
    WORKER_PORT="$WORKER_PORT" nohup "$ROOT_DIR/scripts/start_worker.sh" \
      >"$LOG_DIR/worker.stdout" 2>"$LOG_DIR/worker.stderr" & echo $! >"$LOG_DIR/worker.pid"
    return 0
  fi
  if have wrangler && [[ -f "$ROOT_DIR/wrangler.toml" || -d "$ROOT_DIR/workers" ]]; then
    log "Starting Worker locally via wrangler dev (PORT=$WORKER_PORT)"
    nohup wrangler dev --local --port "$WORKER_PORT" \
      >"$LOG_DIR/worker.stdout" 2>"$LOG_DIR/worker.stderr" & echo $! >"$LOG_DIR/worker.pid"
    return 0
  fi
  err "No Worker start method found. Skipping."
}

start_vite() {
  if [[ -x "$ROOT_DIR/scripts/start_frontend.sh" ]]; then
    log "Starting Vite via scripts/start_frontend.sh (PORT=$VITE_PORT)"
    VITE_PORT="$VITE_PORT" nohup "$ROOT_DIR/scripts/start_frontend.sh" \
      >"$LOG_DIR/vite.stdout" 2>"$LOG_DIR/vite.stderr" & echo $! >"$LOG_DIR/vite.pid"
    return 0
  fi
  if have npm && [[ -f "$ROOT_DIR/frontend/package.json" ]]; then
    log "Starting Vite via npm (PORT=$VITE_PORT)"
    ( cd "$ROOT_DIR/frontend" && PORT="$VITE_PORT" nohup npm run dev \
        >"$LOG_DIR/vite.stdout" 2>"$LOG_DIR/vite.stderr" & echo $! >"$LOG_DIR/vite.pid" )
    return 0
  fi
  err "No frontend start method found. Skipping."
}

stop_all() {
  for svc in backend worker vite; do
    if [[ -f "$LOG_DIR/$svc.pid" ]]; then
      pid=$(cat "$LOG_DIR/$svc.pid" || true)
      if [[ -n "${pid:-}" ]] && kill -0 "$pid" 2>/dev/null; then
        log "Stopping $svc (pid=$pid)"; kill "$pid" 2>/dev/null || true
      fi
      rm -f "$LOG_DIR/$svc.pid"
    fi
  done
}

status() {
  for svc in backend worker vite; do
    if [[ -f "$LOG_DIR/$svc.pid" ]]; then
      pid=$(cat "$LOG_DIR/$svc.pid" || true)
      if [[ -n "${pid:-}" ]] && kill -0 "$pid" 2>/dev/null; then
        log "$svc: RUNNING (pid=$pid)"
      else
        log "$svc: STOPPED"
      fi
    else
      log "$svc: STOPPED"
    fi
  done
}

usage() {
  cat <<USAGE
Usage: $0 [run|stop|status|probe]
  run    Start available services and probe backend health
  stop   Stop services started by this script
  status Show status of services
  probe  Only probe backend health

Env: BACKEND_PORT=$BACKEND_PORT WORKER_PORT=$WORKER_PORT VITE_PORT=$VITE_PORT
USAGE
}

cmd="${1:-run}"; shift || true
case "$cmd" in
  run)
    log "Bootstrap starting"
    start_backend || true
    start_worker  || true
    start_vite    || true
    log "Probing health: $BACKEND_HEALTH"
    probe_health "$BACKEND_HEALTH" 40 0.5 || exit 1
    log "OK. Tail recent logs:"
    for f in backend.stdout worker.stdout vite.stdout; do
      [[ -f "$LOG_DIR/$f" ]] && { echo "--- $f (last 40 lines) ---"; tail -n 40 "$LOG_DIR/$f" || true; }
    done
    ;;
  stop)   stop_all ;;
  status) status ;;
  probe)  probe_health "$BACKEND_HEALTH" 1 0.1 || exit 1 ;;
  *) usage; exit 1;;
esac

*** Update File: /Users/cdmxx/Documents/moonwalkings/scripts/start_backend.sh
#!/usr/bin/env bash
echo "Starting backend..."
# Add your backend start logic here

*** Update File: /Users/cdmxx/Documents/moonwalkings/scripts/requirements.txt
Flask>=2.3.2
requests>=2.31.0
# dev_bootstrap.sh — safe bootstrap + health probe for Moonwalkings
# This file previously contained Python requirements; it's now a runnable script.
# If you still need to add dependencies, put them in requirements.txt (see notes at end).

set -euo pipefail

# ---------- Config (override with env vars) ----------
BACKEND_PORT="${BACKEND_PORT:-5001}"
WORKER_PORT="${WORKER_PORT:-8787}"
VITE_PORT="${VITE_PORT:-3100}"
BACKEND_HEALTH="http://127.0.0.1:${BACKEND_PORT}/api/health"

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
LOG_DIR="$ROOT_DIR/.logs"
mkdir -p "$LOG_DIR"

log() { printf "[dev_bootstrap] %s\n" "$*"; }
err() { printf "[dev_bootstrap][ERR] %s\n" "$*" >&2; }

have() { command -v "$1" >/dev/null 2>&1; }

# ---------- Helpers ----------
probe_health() {
  local url="$1"; local retries="${2:-20}"; local delay="${3:-0.5}";
  for ((i=1;i<=retries;i++)); do
    if curl -fsS "$url" >/dev/null; then
      log "Healthy: $url"
      return 0
    fi
    sleep "$delay"
  done
  err "Timed out waiting for: $url"
  return 1
}

start_backend() {
  # Prefer project-provided script if present
  if [[ -x "$ROOT_DIR/scripts/start_backend.sh" ]]; then
    log "Starting backend via scripts/start_backend.sh (PORT=$BACKEND_PORT)"
    BACKEND_PORT="$BACKEND_PORT" nohup "$ROOT_DIR/scripts/start_backend.sh" \
      >"$LOG_DIR/backend.stdout" 2>"$LOG_DIR/backend.stderr" & echo $! >"$LOG_DIR/backend.pid"
    return 0
  fi
  # Fallbacks kept conservative (no assumptions about module names)
  if [[ -f "$ROOT_DIR/backend/app.py" ]]; then
    log "Starting backend via python backend/app.py (PORT=$BACKEND_PORT)"
    BACKEND_PORT="$BACKEND_PORT" nohup python "$ROOT_DIR/backend/app.py" \
      >"$LOG_DIR/backend.stdout" 2>"$LOG_DIR/backend.stderr" & echo $! >"$LOG_DIR/backend.pid"
    return 0
  fi
  err "No backend start script found. Skipping."
}

start_worker() {
  if [[ -x "$ROOT_DIR/scripts/start_worker.sh" ]]; then
    log "Starting Worker via scripts/start_worker.sh (PORT=$WORKER_PORT)"
    WORKER_PORT="$WORKER_PORT" nohup "$ROOT_DIR/scripts/start_worker.sh" \
      >"$LOG_DIR/worker.stdout" 2>"$LOG_DIR/worker.stderr" & echo $! >"$LOG_DIR/worker.pid"
    return 0
  fi
  if have wrangler && [[ -f "$ROOT_DIR/wrangler.toml" || -d "$ROOT_DIR/workers" ]]; then
    log "Starting Cloudflare Worker locally via wrangler dev (PORT=$WORKER_PORT)"
    nohup wrangler dev --local --port "$WORKER_PORT" \
      >"$LOG_DIR/worker.stdout" 2>"$LOG_DIR/worker.stderr" & echo $! >"$LOG_DIR/worker.pid"
    return 0
  fi
  err "No Worker start method found. Skipping."
}

start_vite() {
  if [[ -x "$ROOT_DIR/scripts/start_frontend.sh" ]]; then
    log "Starting Vite via scripts/start_frontend.sh (PORT=$VITE_PORT)"
    VITE_PORT="$VITE_PORT" nohup "$ROOT_DIR/scripts/start_frontend.sh" \
      >"$LOG_DIR/vite.stdout" 2>"$LOG_DIR/vite.stderr" & echo $! >"$LOG_DIR/vite.pid"
    return 0
  fi
  if have npm && [[ -f "$ROOT_DIR/frontend/package.json" ]]; then
    log "Starting Vite via npm (PORT=$VITE_PORT)"
    ( cd "$ROOT_DIR/frontend" && PORT="$VITE_PORT" nohup npm run dev \
        >"$LOG_DIR/vite.stdout" 2>"$LOG_DIR/vite.stderr" & echo $! >"$LOG_DIR/vite.pid" )
    return 0
  fi
  err "No frontend start method found. Skipping."
}

stop_all() {
  for svc in backend worker vite; do
    if [[ -f "$LOG_DIR/$svc.pid" ]]; then
      pid=$(cat "$LOG_DIR/$svc.pid" || true)
      if [[ -n "${pid:-}" ]] && kill -0 "$pid" 2>/dev/null; then
        log "Stopping $svc (pid=$pid)"; kill "$pid" 2>/dev/null || true
      fi
      rm -f "$LOG_DIR/$svc.pid"
    fi
  done
}

status() {
  for svc in backend worker vite; do
    if [[ -f "$LOG_DIR/$svc.pid" ]]; then
      pid=$(cat "$LOG_DIR/$svc.pid" || true)
      if [[ -n "${pid:-}" ]] && kill -0 "$pid" 2>/dev/null; then
        log "$svc: RUNNING (pid=$pid)"
      else
        log "$svc: STOPPED"
      fi
    else
      log "$svc: STOPPED"
    fi
  done
}

usage() {
  cat <<USAGE
Usage: $0 [run|stop|status|probe]
  run    Start available services and probe backend health at $BACKEND_HEALTH
  stop   Stop services started by this script
  status Show status of services
  probe  Only probe backend health

Env overrides: BACKEND_PORT=$BACKEND_PORT WORKER_PORT=$WORKER_PORT VITE_PORT=$VITE_PORT
USAGE
}

cmd="${1:-run}"; shift || true
case "$cmd" in
  run)
    log "Bootstrap starting in $ROOT_DIR"
    start_backend || true
    start_worker  || true
    start_vite    || true
    log "Probing health: $BACKEND_HEALTH"
    probe_health "$BACKEND_HEALTH" 40 0.5 || exit 1
    log "OK. Tail recent logs:"
    for f in backend.stdout worker.stdout vite.stdout; do
      [[ -f "$LOG_DIR/$f" ]] && { echo "--- $f (last 40 lines) ---"; tail -n 40 "$LOG_DIR/$f" || true; }
    done
    ;;
  stop)
    stop_all
    ;;
  status)
    status
    ;;
  probe)
    probe_health "$BACKEND_HEALTH" 1 0.1 || exit 1
    ;;
  *) usage; exit 1;;
fi

# ---------- Notes ----------
# • Lint/type warnings you mentioned (psutil / None subtraction) are in existing code and
#   not from this script. Run your normal lint pipeline when convenient.
# • Dependencies: ensure requirements.txt contains at least:
#       Flask>=2.3.2
#       requests>=2.31.0
#   (This script no longer stores dependency lines.)
# • Vite proxy: if you want '/api/snapshots/*' -> Worker (${WORKER_PORT}) rewriting in dev,
#   add a proxy rule in frontend/vite.config.js under server.proxy.