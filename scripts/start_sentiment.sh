#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PORT="${SENTIMENT_PORT:-8002}"
HOST="${SENTIMENT_HOST:-0.0.0.0}"
LOG_LEVEL="${SENTIMENT_LOG_LEVEL:-info}"

# Choose interpreter: prefer project venv, fall back to system python3/python
PY_INTERP=""
if [ -x ".venv/bin/python" ]; then
  PY_INTERP=".venv/bin/python"
elif [ -x "backend/.venv/bin/python" ]; then
  PY_INTERP="backend/.venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
  PY_INTERP="$(command -v python3)"
elif command -v python >/dev/null 2>&1; then
  PY_INTERP="$(command -v python)"
else
  echo "[sentiment] No python interpreter found (need python3 or venv)" >&2
  exit 1
fi

"$PY_INTERP" -V
"$PY_INTERP" -m backend.sentiment_api \
  --host "$HOST" \
  --port "$PORT" \
  --log-level "$LOG_LEVEL" \
  "$@"
