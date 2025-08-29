#!/bin/bash
cd "$(dirname "$0")"
if [ ! -d "node_modules" ]; then
  npm install --no-bin-links
fi
[ ! -f .env ] && cp .env.example .env
# Ensure the backend knows the configured strict port (5173) for Vite
BACKEND_PORT_FILE="$(cd "$(dirname "$0")/.." && pwd)/../backend/frontend.port"
echo "5173" > "$BACKEND_PORT_FILE" || true
# Start the dev server (dev script has been patched to use the start-dev-with-port wrapper)
npm run dev
