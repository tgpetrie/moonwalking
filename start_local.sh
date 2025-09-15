#!/usr/bin/env bash
set -euo pipefail

here="$(cd "$(dirname "$0")" && pwd)"
cd "$here"

# Pick free backend port starting at 5001
pick_port() {
  local p=5001
  while lsof -iTCP -sTCP:LISTEN -n -P | grep -q ":$p "; do p=$((p+1)); done
  echo "$p"
}

PORT="$(pick_port)"
export BACKEND_PORT="$PORT"

# Activate venv
# shellcheck disable=SC1091
source .venv/bin/activate 2>/dev/null || {
  echo "[start_local] venv missing. Run ./setup_dev.sh first." >&2
  exit 1
}

# Write frontend/.env.local for Vite & API base
mkdir -p frontend
cat > frontend/.env.local <<EOF
VITE_API_URL=http://127.0.0.1:${BACKEND_PORT}
EOF

echo "[start_local] backend on ${BACKEND_PORT}, Vite on 3100"

# Start backend API
( cd backend && \
  exec python app.py --port "${BACKEND_PORT}" \
       --kill-port --host 127.0.0.1 ) &
BACK_PID=$!

# Start Vite
( cd frontend && exec npm run dev -- --port 3100 --host 127.0.0.1 ) &
VITE_PID=$!

trap 'echo; echo "[start_local] stopping..."; kill $BACK_PID $VITE_PID 2>/dev/null || true' INT TERM

echo "[start_local] open http://127.0.0.1:3100 ; API http://127.0.0.1:${BACKEND_PORT}"
wait
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
