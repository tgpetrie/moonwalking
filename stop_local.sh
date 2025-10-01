#!/usr/bin/env bash
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
