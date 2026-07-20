#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUNTIME="$ROOT/.runtime"
mkdir -p "$RUNTIME"

listener_pid() {
  lsof -tiTCP:"$1" -sTCP:LISTEN 2>/dev/null | head -1 || true
}

stop_port() {
  local port="$1"
  local pid
  pid="$(listener_pid "$port")"
  if [ -z "$pid" ]; then
    return 0
  fi
  kill -TERM "$pid" 2>/dev/null || true
  for _ in 1 2 3 4 5; do
    if ! kill -0 "$pid" 2>/dev/null; then
      return 0
    fi
    sleep 1
  done
  kill -KILL "$pid" 2>/dev/null || true
}

start_services() {
  if [ ! -x "$ROOT/.venv/bin/python" ]; then
    echo "Missing $ROOT/.venv/bin/python; run ./setup_dev.sh first" >&2
    exit 1
  fi
  if [ ! -d "$ROOT/frontend/node_modules" ]; then
    echo "Missing frontend/node_modules; run ./setup_dev.sh first" >&2
    exit 1
  fi

  if [ -z "$(listener_pid 8003)" ]; then
    (
      cd "$ROOT"
      nohup .venv/bin/python -m backend.sentiment_api \
        --host 127.0.0.1 --port 8003 --log-level info \
        > "$RUNTIME/sentiment.log" 2>&1 &
      echo $! > "$RUNTIME/sentiment.pid"
    )
  fi

  if [ -z "$(listener_pid 5003)" ]; then
    (
      cd "$ROOT/backend"
      nohup ../.venv/bin/python app.py --host 127.0.0.1 --port 5003 \
        > "$RUNTIME/backend.log" 2>&1 &
      echo $! > "$RUNTIME/backend.pid"
    )
  fi

  if [ -z "$(listener_pid 5173)" ]; then
    (
      cd "$ROOT/frontend"
      nohup npm run dev -- --host 127.0.0.1 --port 5173 \
        > "$RUNTIME/frontend.log" 2>&1 &
      echo $! > "$RUNTIME/frontend.pid"
    )
  fi

  for _ in $(seq 1 90); do
    if curl -fsS http://127.0.0.1:5003/api/health >/dev/null 2>&1 \
      && curl -fsS http://127.0.0.1:5173/ >/dev/null 2>&1; then
      echo "Moonwalkings is running: http://127.0.0.1:5173"
      return 0
    fi
    sleep 1
  done
  echo "Services started but did not become healthy; inspect $RUNTIME/*.log" >&2
  return 1
}

stop_services() {
  stop_port 5173
  stop_port 5003
  stop_port 8003
  rm -f "$RUNTIME/frontend.pid" "$RUNTIME/backend.pid" "$RUNTIME/sentiment.pid"
}

status_services() {
  for service in "frontend:5173" "backend:5003" "sentiment:8003"; do
    name="${service%%:*}"
    port="${service##*:}"
    pid="$(listener_pid "$port")"
    if [ -n "$pid" ]; then
      echo "$name running on $port (pid $pid)"
    else
      echo "$name stopped on $port"
    fi
  done
}

case "${1:-status}" in
  start) start_services ;;
  stop) stop_services ;;
  restart)
    stop_services
    sleep 2
    start_services
    ;;
  status) status_services ;;
  *)
    echo "Usage: $0 {start|stop|restart|status}" >&2
    exit 2
    ;;
esac
