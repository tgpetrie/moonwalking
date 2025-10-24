#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/frontend"
export VITE_API_URL="${VITE_API_URL:-http://127.0.0.1:5001}"
echo "[i] VITE_API_URL=$VITE_API_URL"
if [[ ! -d node_modules ]]; then
  npm ci
fi
npm run dev -- --host 127.0.0.1 --port 5173
