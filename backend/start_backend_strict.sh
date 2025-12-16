#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# default to 5001 because that’s what your current runtime is using
BACKEND_PORT="${BACKEND_PORT:-5001}"
PY="${PY:-$ROOT/backend/.venv/bin/python}"
LOG="${LOG:-$ROOT/backend.strict.log}"

source "$ROOT/scripts/ports_strict.sh"

kill_port "$BACKEND_PORT"

echo "[strict] starting backend on :$BACKEND_PORT"
cd "$ROOT/backend"

# if your app reads PORT, keep it; if it reads something else, adjust here
PORT="$BACKEND_PORT" nohup "$PY" app.py > "$LOG" 2>&1 & disown || true

# your canonical aggregate is /data
wait_http "http://127.0.0.1:${BACKEND_PORT}/data"

echo "[strict] backend OK -> http://127.0.0.1:${BACKEND_PORT}/data"
