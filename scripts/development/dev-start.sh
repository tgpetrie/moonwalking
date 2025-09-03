#!/usr/bin/env bash
# Dev orchestrator: starts backend + frontend with health gating, warmup & flags.
set -euo pipefail
IFS=$'\n\t'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"

DEFAULT_BACKEND_PORT=5001
DEFAULT_FRONTEND_PORT=5173
BACKEND_PORT=${PORT:-$DEFAULT_BACKEND_PORT}
FRONTEND_PORT=$DEFAULT_FRONTEND_PORT

KILL=false
NO_FRONTEND=false
NO_BACKEND=false
WARM=false
QUIET=false
VERBOSE=false
TEST_MODE=false
HEALTH_TIMEOUT=40
WARM_ENDPOINTS=(
    "/api/component/gainers-table"
    "/api/component/losers-table"
    "/api/component/gainers-table-1min"
    "/api/component/losers-table"  # duplicate ensures both caches warm post first fetch logic
    "/api/component/top-banner-scroll"
    "/api/component/bottom-banner-scroll"
    "/api/health"
)

log() {
    local level="$1"; shift
    $QUIET && [[ "$level" != "ERR" ]] && return 0
    local ts
    ts=$(date +"%H:%M:%S")
    echo "[$ts][$level] $*" >&2
}

die() { log ERR "$*"; exit 1; }

usage() {
    cat <<EOF
Usage: $0 [options]
    -k, --kill            Kill processes occupying dev ports first
            --no-frontend     Do not start frontend
            --no-backend      Do not start backend
            --warm            After backend healthy, hit key endpoints to warm caches
    -q, --quiet           Suppress non-error logs
    -v, --verbose         Verbose (set -x)
            --test            Dry-run: validate script & simulate steps; exit 0
            --timeout <sec>   Health wait timeout (default $HEALTH_TIMEOUT)
    -h, --help            Show this help
Environment Overrides:
    PORT                  Backend port (default $DEFAULT_BACKEND_PORT)
    FRONTEND_PORT         (Optional) Override frontend dev port (default $DEFAULT_FRONTEND_PORT)
EOF
}

parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            -k|--kill) KILL=true ; shift ;;
            --no-frontend) NO_FRONTEND=true ; shift ;;
            --no-backend) NO_BACKEND=true ; shift ;;
            --warm) WARM=true ; shift ;;
            -q|--quiet) QUIET=true ; shift ;;
            -v|--verbose) VERBOSE=true ; shift ;;
            --test) TEST_MODE=true ; shift ;;
            --timeout) HEALTH_TIMEOUT="$2"; shift 2 ;;
            -h|--help) usage; exit 0 ;;
            *) die "Unknown argument: $1" ;;
        esac
    done
    [[ -n "${FRONTEND_PORT:-}" ]] && FRONTEND_PORT=${FRONTEND_PORT}
}

need_cmd() { command -v "$1" >/dev/null 2>&1 || die "Required command '$1' not found"; }

kill_port() { local p=$1; lsof -ti:"$p" | xargs kill -9 2>/dev/null || true; }

kill_ports() {
    log INF "Killing processes on ports $BACKEND_PORT and ${FRONTEND_PORT}..$((FRONTEND_PORT+2))"
    kill_port "$BACKEND_PORT"
    for p in $(seq "$FRONTEND_PORT" $((FRONTEND_PORT+2))); do kill_port "$p"; done
}

wait_for_health() {
    local url="http://localhost:${BACKEND_PORT}/api/health"
    local start
    start=$(date +%s)
    while true; do
        if curl -fsS "$url" >/dev/null 2>&1; then
            log INF "Backend healthy ($url)"
            return 0
        fi
        local now
        now=$(date +%s)
        if (( now - start >= HEALTH_TIMEOUT )); then
            die "Backend not healthy after ${HEALTH_TIMEOUT}s (URL: $url)"
        fi
        sleep 1
    done
}

warm_caches() {
    log INF "Warming backend caches"
    for ep in "${WARM_ENDPOINTS[@]}"; do
        local url="http://localhost:${BACKEND_PORT}${ep}"
        curl -fsS "$url" >/dev/null 2>&1 && log INF "Warmed ${ep}" || log ERR "Warm failed ${ep}" || true
        sleep 0.3
    done
}

start_backend() {
    [[ $NO_BACKEND == true ]] && return 0
    log INF "Starting backend on port $BACKEND_PORT"
    (
        cd "$BACKEND_DIR"
        export PORT="$BACKEND_PORT"
        # Ensure Python deps (lightweight check) - skip if requirements missing
        if [[ -f requirements.txt ]]; then
            if ! python3 -c 'import flask' 2>/dev/null; then
                log INF "Installing backend deps (flask missing)"
                pip3 install -q -r requirements.txt || die "Backend dependency install failed"
            fi
        fi
        exec python3 app.py
    ) &
    BACKEND_PID=$!
    log INF "Backend PID $BACKEND_PID"
}

start_frontend() {
    [[ $NO_FRONTEND == true ]] && return 0
    log INF "Starting frontend (port ${FRONTEND_PORT})"
    (
        cd "$FRONTEND_DIR"
        if [[ -f package.json ]]; then
            # Install deps only if node_modules missing or package.json newer
            if [[ ! -d node_modules ]]; then
                log INF "Installing frontend dependencies"
                npm install --no-audit --no-fund >/dev/null 2>&1 || die "Frontend install failed"
            fi
            exec npm run dev -- --port ${FRONTEND_PORT}
        else
            die "frontend/package.json not found"
        fi
    ) &
    FRONTEND_PID=$!
    log INF "Frontend PID $FRONTEND_PID"
}

cleanup() {
    local code=$?
    log INF "Cleaning up (exit code $code)"
    [[ -n "${BACKEND_PID:-}" ]] && kill "$BACKEND_PID" 2>/dev/null || true
    [[ -n "${FRONTEND_PID:-}" ]] && kill "$FRONTEND_PID" 2>/dev/null || true
    if $KILL; then
        kill_ports || true
    fi
    log INF "Done"
}
trap cleanup EXIT INT TERM

main() {
    parse_args "$@"
    $VERBOSE && set -x
    need_cmd lsof; need_cmd curl; need_cmd python3; need_cmd npm
    $KILL && kill_ports

    if $TEST_MODE; then
        log INF "--test mode: performing dry-run checks"
        [[ -d "$BACKEND_DIR" ]] || die "Missing backend dir"
        [[ -d "$FRONTEND_DIR" ]] || die "Missing frontend dir"
        log INF "Would start backend on $BACKEND_PORT and frontend on $FRONTEND_PORT"
        log INF "Dry-run success"
        return 0
    fi

    start_backend
    wait_for_health
    $WARM && warm_caches
    start_frontend

    log INF "Backend:  http://localhost:${BACKEND_PORT}"
    log INF "Frontend: http://localhost:${FRONTEND_PORT}"
    log INF "Press Ctrl+C to stop"

    # Wait on children
    wait
}

main "$@"
