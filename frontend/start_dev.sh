#!/usr/bin/env bash
# Unified dev start script (repo-root aware)
# Usage: ./start_dev.sh

set -euo pipefail

# Resolve repo root no matter where this script lives (frontend/ or root)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
# If the script is inside frontend/, go one level up; otherwise stay
if [[ "$(basename "$SCRIPT_DIR")" == "frontend" ]]; then
  ROOT_DIR="$(cd "$SCRIPT_DIR/.." &>/dev/null && pwd)"
else
  ROOT_DIR="$SCRIPT_DIR"
fi

FRONTEND_DIR="$ROOT_DIR/frontend"
BACKEND_DIR="$ROOT_DIR/backend"
LOG_DIR="$ROOT_DIR/logs"
mkdir -p "$LOG_DIR"

FRONTEND_PORTS=(5173 5174)
BACKEND_PORT=5001

kill_ports() {
  for p in "$@"; do
    if lsof -ti :"$p" >/dev/null 2>&1; then
      echo "Killing processes on port $p..."
      lsof -ti :"$p" | xargs kill -9 || true
    fi
  done
}

echo "🔧 Cleaning up old dev servers..."
kill_ports "${FRONTEND_PORTS[@]}" "$BACKEND_PORT"

echo "🚀 Starting backend..."
(
  cd "$BACKEND_DIR"
  # Prefer venv if present
  if [[ -f ".venv/bin/activate" ]]; then
    # shellcheck disable=SC1091
    source .venv/bin/activate
  fi
  # Prefer flask if FLASK_APP present, else run app.py
  if [[ -f "app.py" ]]; then
    python app.py
  else
    echo "No app.py found in $BACKEND_DIR" >&2
    exit 1
  fi
) > "$LOG_DIR/backend.log" 2>&1 &

echo "🚀 Starting frontend..."
(
  cd "$FRONTEND_DIR"
  # Ensure deps are installed (no-op if already installed)
  if [[ ! -d "node_modules" ]]; then
    npm ci || npm install
  fi
  npm run dev
) > "$LOG_DIR/frontend.log" 2>&1 &

echo "✅ Dev servers launched. Logs:"
echo "   backend → $LOG_DIR/backend.log"
echo "   frontend → $LOG_DIR/frontend.log"
echo ""
echo "Run '$ROOT_DIR/status.sh' to see active ports."
