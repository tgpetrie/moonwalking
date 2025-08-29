#!/usr/bin/env bash
# Stop the frontend dev server started by start_backend.sh or manually.
set -euo pipefail

HERE_DIR="$(cd "$(dirname "$0")" && pwd)"
PIDFILE="$HERE_DIR/frontend.pid"
PORT=5173

echo "[stop_frontend] looking for frontend pidfile: $PIDFILE"
if [ -f "$PIDFILE" ]; then
  PID=$(cat "$PIDFILE" 2>/dev/null || true)
  if [ -n "$PID" ]; then
    echo "[stop_frontend] killing pid $PID from pidfile"
    kill "$PID" 2>/dev/null || true
    sleep 0.5
    if kill -0 "$PID" 2>/dev/null; then
      echo "[stop_frontend] pid $PID still alive, forcing"
      kill -9 "$PID" 2>/dev/null || true
    fi
    rm -f "$PIDFILE" || true
    echo "[stop_frontend] stopped (pidfile removed)"
    exit 0
  else
    echo "[stop_frontend] pidfile empty, removing"
    rm -f "$PIDFILE" || true
  fi
fi

echo "[stop_frontend] no pidfile found, searching by port $PORT"
PID=$(lsof -ti :$PORT 2>/dev/null || true)
if [ -n "$PID" ]; then
  echo "[stop_frontend] killing process(es) on port $PORT: $PID"
  kill $PID 2>/dev/null || true
  sleep 0.5
  PID=$(lsof -ti :$PORT 2>/dev/null || true)
  if [ -n "$PID" ]; then
    echo "[stop_frontend] force-killing remaining: $PID"
    kill -9 $PID 2>/dev/null || true
  fi
  echo "[stop_frontend] stopped processes on port $PORT"
  exit 0
fi

echo "[stop_frontend] no frontend process found (pidfile or port)"
exit 0
