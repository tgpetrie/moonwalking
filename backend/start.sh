#!/usr/bin/env bash
set -euo pipefail
# start backend dev server (safe, idempotent)
cd "$(dirname "$0")"
echo "[backend/start.sh] cwd=$(pwd)"

# Activate or create virtualenv
if [ -f .venv/bin/activate ]; then
  echo "Activating existing virtualenv .venv"
  # shellcheck source=/dev/null
  . .venv/bin/activate
else
  echo "Creating virtualenv .venv"
  python -m venv .venv
  # shellcheck source=/dev/null
  . .venv/bin/activate
  if [ -f requirements.txt ]; then
    echo "Installing python requirements..."
    pip install -r requirements.txt
  else
    echo "No requirements.txt found in $(pwd) — skipping pip install"
  fi
fi

echo "Starting backend with: python app.py"
if [ -f app.py ]; then
  python app.py
else
  echo "ERROR: app.py not found in $(pwd). Run 'ls -la' to inspect." >&2
  exit 2
fi
