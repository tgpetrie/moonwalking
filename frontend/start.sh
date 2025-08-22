#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
echo "[frontend/start.sh] cwd=$(pwd)"

if [ ! -f package.json ]; then
  echo "ERROR: package.json not found in $(pwd). Are you in the frontend directory?" >&2
  exit 2
fi

if [ -d node_modules ]; then
  echo "node_modules already present — skipping npm install"
else
  echo "Installing node dependencies..."
  npm install
fi

echo "Starting Vite dev server"
npm run dev -- --host 0.0.0.0 --port 5173
