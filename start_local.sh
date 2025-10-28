#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_PID_FILE="${ROOT_DIR}/backend/backend.pid"
BRIDGE_PID_FILE="${ROOT_DIR}/bridge.pid"
VITE_PID_FILE="${ROOT_DIR}/frontend/vite.pid"

BACKEND_LOG="${ROOT_DIR}/backend/server.stdout"
BRIDGE_LOG="${ROOT_DIR}/bridge.stdout"
VITE_LOG="${ROOT_DIR}/frontend/vite.stdout"
FRONTEND_ENV="${ROOT_DIR}/frontend/.env.local"

echo "[start_local] killing leftovers on 5001/5100/5173 and clearing pidfiles..."

kill_if_pidfile () {
  local file="$1"; local name="$2"
  if [ -f "$file" ]; then
    pid=$(cat "$file" 2>/dev/null || true)
    if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
      echo "[start_local] killing $name pid $pid"
      kill "$pid" 2>/dev/null || true
      sleep 0.3
      if kill -0 "$pid" 2>/dev/null; then
        kill -9 "$pid" 2>/dev/null || true
      fi
    fi
    rm -f "$file"
  fi
}

kill_if_pidfile "$BACKEND_PID_FILE" "backend" || true
kill_if_pidfile "$BRIDGE_PID_FILE" "bridge" || true
kill_if_pidfile "$VITE_PID_FILE" "vite" || true

# also nuke by port just in case
for PORT in 5001 5100 5173; do
  PID_ON_PORT=$(lsof -nP -iTCP:$PORT -sTCP:LISTEN -t 2>/dev/null || true)
  if [ -n "$PID_ON_PORT" ]; then
    echo "[start_local] port $PORT in use by $PID_ON_PORT, killing"
    kill $PID_ON_PORT 2>/dev/null || true
    sleep 0.3
    if kill -0 $PID_ON_PORT 2>/dev/null; then
      kill -9 $PID_ON_PORT 2>/dev/null || true
    fi
  fi
done

cat > "$FRONTEND_ENV" <<EOF
VITE_API_URL=http://127.0.0.1:5173
VITE_WS_URL=ws://127.0.0.1:5173
VITE_DISABLE_LOCAL_PROBE=1
EOF

echo "[start_local] starting backend (Flask @5001)..."
(
  cd "$ROOT_DIR/backend"
  nohup python3 app.py --port 5001 --host 127.0.0.1 > "$BACKEND_LOG" 2>&1 &
  echo $! > "$BACKEND_PID_FILE"
)
sleep 1
echo "[start_local] backend pid $(cat "$BACKEND_PID_FILE")"

echo "[start_local] starting bridge (Node @5100)..."
(
  cd "$ROOT_DIR"
  nohup node server.js > "$BRIDGE_LOG" 2>&1 &
  echo $! > "$BRIDGE_PID_FILE"
)
sleep 1
echo "[start_local] bridge pid $(cat "$BRIDGE_PID_FILE")"

echo "[start_local] starting Vite dev (React @5173)..."
(
  cd "$ROOT_DIR/frontend"
  rm -rf node_modules/.vite || true
  nohup npx vite --host 127.0.0.1 --port 5173 --strictPort > "$VITE_LOG" 2>&1 &
  echo $! > "$VITE_PID_FILE"
)
sleep 1
echo "[start_local] vite pid $(cat "$VITE_PID_FILE")"

echo "[start_local] all services launched."
echo "  backend: http://127.0.0.1:5001/api/health"
echo "  bridge:  http://127.0.0.1:5100/health"
echo "  ui:      http://127.0.0.1:5173/"
