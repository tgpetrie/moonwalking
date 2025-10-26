#!/bin/bash
set -e

# === CONFIG ===
NODE_BACKEND_FILE="server.js"
FLASK_BACKEND_FILE="backend/app.py"

NODE_PORT=3100
FLASK_PORT=5001
FRONTEND_PORT=5173
FRONTEND_DIR="frontend"

NODE_CMD="node $NODE_BACKEND_FILE --host 127.0.0.1 --port $NODE_PORT"
FLASK_CMD="HOST=127.0.0.1 PORT=$FLASK_PORT python3 $FLASK_BACKEND_FILE"
FRONTEND_CMD="npm run dev -- --host 127.0.0.1 --port $FRONTEND_PORT"

# === UTIL ===
port_in_use() { lsof -ti :$1 >/dev/null 2>&1; }

kill_port() {
  local port=$1
  if port_in_use "$port"; then
    echo "🔪 Killing process on port $port..."
    lsof -ti :$port | xargs -r kill -9 || true
  fi
}

start_service() {
  local name="$1" cmd="$2" port="$3" log="$4"
  echo "🚀 Starting $name on port $port..."
  kill_port "$port"
  nohup bash -c "$cmd" > "$log" 2>&1 &
  local pid=$!
  sleep 1
  if port_in_use "$port"; then
    echo "✅ $name running (PID $pid, port $port)"
  else
    echo "❌ $name failed to start. Check $log"
  fi
  echo ""
}

# === CLEAN ===
if [[ "$1" == "--clean" ]]; then
  echo "🧹 Cleaning caches..."
  find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
  find . -type f -name "*.pyc" -delete 2>/dev/null || true
  rm -rf frontend/node_modules/.cache 2>/dev/null || true
  echo "✅ Clean done."
  echo ""
fi

# === DETECT AND START ===
SERVICES=()

if [ -f "$FLASK_BACKEND_FILE" ]; then
  SERVICES+=("flask")
fi

if [ -f "$NODE_BACKEND_FILE" ]; then
  SERVICES+=("node")
fi

if [ -d "$FRONTEND_DIR" ]; then
  SERVICES+=("vite")
fi

if [ ${#SERVICES[@]} -eq 0 ]; then
  echo "❌ No services found (expected server.js, backend/app.py, or frontend/)"
  exit 1
fi

echo "📦 Detected services: ${SERVICES[*]}"
echo ""

for svc in "${SERVICES[@]}"; do
  case $svc in
    flask)
      start_service "Flask backend" "$FLASK_CMD" "$FLASK_PORT" "backend.log"
      ;;
    node)
      start_service "Node backend" "$NODE_CMD" "$NODE_PORT" "node.log"
      ;;
    vite)
      cd "$FRONTEND_DIR"
      start_service "Vite frontend" "$FRONTEND_CMD" "$FRONTEND_PORT" "vite.log"
      cd ..
      ;;
  esac
done

# === SUMMARY ===
echo ""
echo "🌐 Active endpoints:"
[ -f "$FLASK_BACKEND_FILE" ] && echo "  Flask → http://127.0.0.1:$FLASK_PORT"
[ -f "$NODE_BACKEND_FILE" ] && echo "  Node  → http://127.0.0.1:$NODE_PORT"
[ -d "$FRONTEND_DIR" ] && echo "  Frontend → http://127.0.0.1:$FRONTEND_PORT"

echo ""
echo "🧾 Logs:"
[ -f "$FLASK_BACKEND_FILE" ] && echo "  backend.log"
[ -f "$NODE_BACKEND_FILE" ] && echo "  node.log"
[ -d "$FRONTEND_DIR" ] && echo "  $FRONTEND_DIR/vite.log"

if [[ "$1" == "--logs" ]]; then
  echo ""
  echo "📡 Tailing logs... (Ctrl+C to exit)"
  tail -f backend.log node.log frontend/vite.log 2>/dev/null
fi