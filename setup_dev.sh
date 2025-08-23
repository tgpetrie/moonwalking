#!/usr/bin/env bash
# Unified dev start script
# Usage: ./start_dev.sh

set -euo pipefail

# --- CONFIG ---
FRONTEND_DIR="frontend"
BACKEND_DIR="backend"
FRONTEND_PORTS=(5173 5174)
BACKEND_PORT=5001

# --- HELPERS ---
kill_ports() {
  for p in "$@"; do
    if lsof -ti :"$p" >/dev/null 2>&1; then
      echo "Killing processes on port $p..."
      lsof -ti :"$p" | xargs kill -9 || true
    fi
  done
}

# --- MAIN ---
echo "🔧 Cleaning up old dev servers..."
kill_ports "${FRONTEND_PORTS[@]}" "$BACKEND_PORT"

echo "🚀 Starting backend..."
(
  cd "$BACKEND_DIR"
  source .venv/bin/activate 2>/dev/null || true
  python app.py
) > backend/server.log 2>&1 &

echo "🚀 Starting frontend..."
(
  cd "$FRONTEND_DIR"
  npm run dev
) > frontend/dev.log 2>&1 &

echo "✅ Dev servers launched. Logs:"
echo "   backend → backend/server.log"
echo "   frontend → frontend/dev.log"
echo ""
echo "Run './status.sh' to see active ports."