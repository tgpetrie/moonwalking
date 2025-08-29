#!/usr/bin/env bash
# Stop the backend server started by start_backend.sh
# It prefers a pid file (backend.pid) if present; otherwise it finds the process
# listening on the target port and kills it. Use --force to escalate to SIGKILL.

set -euo pipefail

HERE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE_DIR"

PIDFILE="backend.pid"
PORT=5001
FORCE=false

usage() {
  cat <<EOF
Usage: $0 [--pidfile <file>] [--port <port>] [--force]

Options:
  --pidfile PATH   Use this pidfile (default: backend.pid)
  --port N         Target port to search for process (default: 5001)
  --force          Use SIGKILL if regular TERM fails
  -h|--help        Show this help
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --pidfile)
      PIDFILE="$2"; shift 2;;
    --port)
      PORT="$2"; shift 2;;
    --force)
      FORCE=true; shift;;
    -h|--help)
      usage; exit 0;;
    *) echo "Unknown arg: $1" >&2; usage; exit 2;;
  esac
done

echo "[stop_backend] cwd=$HERE_DIR pidfile=$PIDFILE port=$PORT force=$FORCE"

kill_pid() {
  local pid=$1
  if [ -z "$pid" ]; then
    return 1
  fi
  if kill -0 "$pid" 2>/dev/null; then
    echo "[stop_backend] sending SIGTERM to $pid"
    kill "$pid" || true
    # wait up to 5s
    for i in {1..10}; do
      if kill -0 "$pid" 2>/dev/null; then
        sleep 0.5
      else
        echo "[stop_backend] process $pid terminated"
        return 0
      fi
    done
    if [ "$FORCE" = true ]; then
      echo "[stop_backend] SIGTERM failed, sending SIGKILL to $pid"
      kill -9 "$pid" || true
      return 0
    else
      echo "[stop_backend] process $pid did not exit after SIGTERM; rerun with --force to SIGKILL" >&2
      return 2
    fi
  else
    echo "[stop_backend] no such process: $pid"
    return 1
  fi
}

# If pidfile exists, try that first
if [ -f "$PIDFILE" ]; then
  PID=$(cat "$PIDFILE" 2>/dev/null || true)
  if [ -n "$PID" ]; then
    kill_pid "$PID" && rm -f "$PIDFILE" && exit 0 || true
  else
    echo "[stop_backend] pidfile exists but is empty: $PIDFILE"
  fi
fi

# Fallback: find process by port
echo "[stop_backend] pidfile not used or failed; searching for process on port $PORT"
PIDS=$(lsof -ti ":$PORT" 2>/dev/null || true)
if [ -z "$PIDS" ]; then
  echo "[stop_backend] no process found listening on port $PORT"
  exit 0
fi

echo "[stop_backend] found PIDs: $PIDS"
for pid in $PIDS; do
  kill_pid "$pid" || true
done

echo "[stop_backend] done"
