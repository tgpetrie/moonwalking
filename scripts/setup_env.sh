#!/usr/bin/env bash
set -euo pipefail
# Usage: ./scripts/setup_env.sh

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"

echo "== Setup dev environment =="

# Ensure Python 3 exists
if command -v python3 >/dev/null 2>&1; then
  PY=python3
else
  echo "python3 not found. Attempting to install via Homebrew..."
  if command -v brew >/dev/null 2>&1; then
    brew install python || true
  else
    echo "Homebrew not found. Please install Homebrew or Python manually: https://brew.sh/"
    exit 1
  fi
  PY=python3
fi

# Backend: create venv and install requirements
echo "Setting up backend venv..."
cd "$BACKEND_DIR"
if [[ ! -d .venv ]]; then
  $PY -m venv .venv
fi
source .venv/bin/activate
pip install --upgrade pip setuptools wheel
if [[ -f requirements.txt ]]; then
  pip install -r requirements.txt
fi
deactivate || true

# Frontend: install node modules
echo "Setting up frontend node modules..."
cd "$FRONTEND_DIR"
if [[ -f package.json ]]; then
  if command -v npm >/dev/null 2>&1; then
    npm ci || npm install
  else
    echo "npm not found. Install Node.js (https://nodejs.org/) or use nvm, then re-run this script."
    exit 1
  fi
fi

echo "Setup complete. To run dev servers:"
echo "  ./scripts/start_dev_local.sh  # starts frontend and backend in background logs"
