#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_PID_FILE="${ROOT_DIR}/backend/backend.pid"
VITE_PID_FILE="${ROOT_DIR}/frontend/vite.pid"

echo "[status_local] repository: ${ROOT_DIR}"

report() {
  local file="$1"; local name="$2"
  if [ -f "$file" ]; then
    pid=$(cat "$file" 2>/dev/null || true)
    if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
      echo "[status_local] $name running: pid=$pid"
      ps -p "$pid" -o pid,ppid,cmd || true
    else
      echo "[status_local] $name pid file exists but process not running: $file"
    fi
  else
    echo "[status_local] $name not running (no pid file: $file)"
  fi
}

report "$BACKEND_PID_FILE" backend
report "$VITE_PID_FILE" vite

echo; echo "[status_local] listening ports (lsof output, if available):"
if command -v lsof >/dev/null 2>&1; then
  lsof -nP -iTCP:5001 -sTCP:LISTEN || true
  lsof -nP -iTCP:3100 -sTCP:LISTEN || true
else
  echo "lsof not available"
fi
