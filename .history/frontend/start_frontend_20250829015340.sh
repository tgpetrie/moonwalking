#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
if [ ! -d "node_modules" ]; then
  npm install --no-bin-links
fi
[ ! -f .env ] && cp .env.example .env

# Ensure the backend knows the configured strict port (intent write early)
BACKEND_PORT_FILE="$(cd "$(dirname "$0")/.." && pwd)/../backend/frontend.port"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"
echo -n "$FRONTEND_PORT" > "$BACKEND_PORT_FILE" || true

# Start the dev server via the wrapper which waits for readiness
./scripts/start-dev-with-port.sh
