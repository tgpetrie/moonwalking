#!/usr/bin/env bash
# start_backend.sh — small helper to launch the Flask backend reliably
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

# If a virtualenv exists, prefer it (but don't activate automatically)
if [[ -f "$ROOT_DIR/pyproject.toml" || -f "$ROOT_DIR/requirements.txt" ]]; then
  log_prefix="[start_backend]"
  printf "%s Using requirements at %s\n" "$log_prefix" "$ROOT_DIR/requirements.txt" || true
fi

# Ensure FLASK_APP points to the application module
export FLASK_APP=${FLASK_APP:-backend.app}
export FLASK_ENV=${FLASK_ENV:-development}

printf "[start_backend] Running: flask run --host=127.0.0.1 --port=${BACKEND_PORT:-5001}\n"
flask run --host=127.0.0.1 --port="${BACKEND_PORT:-5001}"
