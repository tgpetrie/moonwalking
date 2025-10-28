#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_PID_FILE="${ROOT_DIR}/backend/backend.pid"
BRIDGE_PID_FILE="${ROOT_DIR}/bridge.pid"
VITE_PID_FILE="${ROOT_DIR}/frontend/vite.pid"

kill_if_pidfile() {
  local file="$1"; local name="$2"
  if [ -f "$file" ]; then
    pid=$(cat "$file" 2>/dev/null || true)
    if [ -n "$pid" ]; then
      if kill -0 "$pid" 2>/dev/null; then
        echo "[stop_local] sending SIGTERM to $name ($pid)"
        kill -TERM "$pid" 2>/dev/null || true
        for _ in {1..25}; do
          if ! kill -0 "$pid" 2>/dev/null; then break; fi
          sleep 0.2
        done
        if kill -0 "$pid" 2>/dev/null; then
          echo "[stop_local] $name still alive; sending SIGKILL"
          kill -9 "$pid" 2>/dev/null || true
        else
          echo "[stop_local] $name stopped"
        fi
      else
        echo "[stop_local] $name pid $pid not running"
      fi
    fi
    rm -f "$file"
  else
    echo "[stop_local] no pid file for $name"
  fi
}

kill_if_pidfile "$VITE_PID_FILE" "vite"
kill_if_pidfile "$BRIDGE_PID_FILE" "bridge"
kill_if_pidfile "$BACKEND_PID_FILE" "backend"

echo "[stop_local] clearing any leftovers on ports 5001/5100/5173"
for PORT in 5001 5100 5173; do
  PID_ON_PORT=$(lsof -nP -iTCP:$PORT -sTCP:LISTEN -t 2>/dev/null || true)
  if [ -n "$PID_ON_PORT" ]; then
    echo "[stop_local] killing pid $PID_ON_PORT on $PORT"
    kill $PID_ON_PORT 2>/dev/null || true
    sleep 0.2
    if kill -0 $PID_ON_PORT 2>/dev/null; then
      kill -9 $PID_ON_PORT 2>/dev/null || true
    fi
  fi
done

echo "[stop_local] done."
echo "logs:"
echo "  backend: $ROOT_DIR/backend/server.stdout"
echo "  bridge:  $ROOT_DIR/bridge.stdout"
echo "  vite:    $ROOT_DIR/frontend/vite.stdout"
#!/usr/bin/env bash
set -euo pipefail
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_PID_FILE="${ROOT_DIR}/backend/backend.pid"
VITE_PID_FILE="${ROOT_DIR}/frontend/vite.pid"
BACKEND_LOG="${ROOT_DIR}/backend/server.stdout"
VITE_LOG="${ROOT_DIR}/frontend/vite.stdout"

echo "[stop_local] stopping services (pid files: ${BACKEND_PID_FILE}, ${VITE_PID_FILE})"

kill_if_pidfile() {
  local file="$1"; local sig="${2:-TERM}"; local name="$3"
  if [ -f "$file" ]; then
    pid=$(cat "$file" 2>/dev/null || true)
    if [ -n "$pid" ]; then
      if kill -0 "$pid" 2>/dev/null; then
        echo "[stop_local] sending SIG${sig} to $name ($pid)"
        kill -s "$sig" "$pid" 2>/dev/null || true
        # wait up to 5s for it to exit
        for _ in {1..25}; do
          if ! kill -0 "$pid" 2>/dev/null; then break; fi
          sleep 0.2
        done
        if kill -0 "$pid" 2>/dev/null; then
          echo "[stop_local] $name did not exit; sending SIGKILL"
          kill -9 "$pid" 2>/dev/null || true
        else
          echo "[stop_local] $name stopped"
        fi
      else
        echo "[stop_local] $name pid $pid not running"
      fi
    fi
    rm -f "$file"
  else
    echo "[stop_local] no pid file at $file"
  fi
}

kill_if_pidfile "$VITE_PID_FILE" TERM "Vite"
kill_if_pidfile "$BACKEND_PID_FILE" TERM "backend"

echo "[stop_local] done. Check logs: ${BACKEND_LOG}, ${VITE_LOG}"
