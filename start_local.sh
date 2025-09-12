#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

BACKEND_PORT="${BACKEND_PORT:-5001}"
VITE_PORT="${VITE_PORT:-3100}"

# Stop leftovers (best-effort)
pkill -f "python3 app.py" 2>/dev/null || true
pkill -f "vite"           2>/dev/null || true

# Pick a free backend port (5001 fallback to 5002..5005)
pick_free_port() {
  for p in "$@"; do
    if ! (command -v lsof >/dev/null 2>&1 && lsof -tiTCP:"$p" -sTCP:LISTEN >/dev/null 2>&1); then
      echo "$p"; return 0
    fi
  done
  echo "$1"
}
BACKEND_PORT=$(pick_free_port "$BACKEND_PORT" 5002 5003 5004 5005)

# Start backend
(
  cd backend
  if [ -f ../.venv/bin/activate ]; then
    . ../.venv/bin/activate
  fi
  python3 app.py --port "$BACKEND_PORT" > ../backend.log 2>&1 &
  echo $! > ../.backend.pid
)

# Point frontend to backend /api and disable WS in pure-local mode
{
  printf 'VITE_API_BASE=http://127.0.0.1:%s/api\n' "$BACKEND_PORT"
  printf 'VITE_DISABLE_WS=true\n'
} > frontend/.env.local

# Start frontend on 3100
(
  cd frontend
  npm install --no-fund --no-audit >/dev/null 2>&1 || true
  npm run dev -- --host 127.0.0.1 --port "$VITE_PORT" > ../frontend.log 2>&1 &
  echo $! > ../.vite.pid
)

echo "Backend  : http://127.0.0.1:${BACKEND_PORT}"
echo "Frontend : http://127.0.0.1:${VITE_PORT}"
