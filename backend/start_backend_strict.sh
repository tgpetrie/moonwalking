#!/usr/bin/env bash
set -euo pipefail

PORT="${PORT:-5001}"
HOST="${HOST:-127.0.0.1}"

echo "[strict] starting backend on ${HOST}:${PORT} (no auto-port fallback)"
cd "$(dirname "$0")"

# Activate venv if present
if [ -f "../.venv/bin/activate" ]; then
	# shellcheck disable=SC1091
	source "../.venv/bin/activate"
fi

export PORT HOST

# Run in strict mode: pin the port and attempt to free it first.
python app.py --port "$PORT" --host "$HOST" --kill-port