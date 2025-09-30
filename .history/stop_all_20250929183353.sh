#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR"

# State dir may be overridden by the environment for CI or tests
: "${STATE_DIR:=/tmp/bhabit_run}"
echo "[stop_all] stopping dev services (state dir: ${STATE_DIR})"

# Ensure STATE_DIR exists (harmless if it doesn't)
mkdir -p "${STATE_DIR}" 2>/dev/null || true

# Helper: safely kill a list of PIDs (accepts whitespace/newline separated)
kill_pids() {
  local pids="$1"
  # Split on IFS (whitespace/newline) by using set --
  if [ -z "${pids}" ]; then
    return 0
  fi
  # Iterate and kill each numeric PID
  for pid in ${pids}; do
    if [[ "$pid" =~ ^[0-9]+$ ]] && ps -p "$pid" >/dev/null 2>&1; then
      echo "[stop_all] killing pid $pid"
      kill "$pid" 2>/dev/null || true
      sleep 0.05
      if ps -p "$pid" >/dev/null 2>&1; then
        echo "[stop_all] escalating to kill -9 $pid"
        kill -9 "$pid" 2>/dev/null || true
      fi
    fi
  done
}

# Kill PID files if present (support a few sensible locations)
PIDFILES=("${STATE_DIR}/backend.pid" "${STATE_DIR}/frontend.pid" "${STATE_DIR}/backend-pid" "${STATE_DIR}/frontend-pid")
for pidfile in "${PIDFILES[@]}"; do
  if [ -f "$pidfile" ]; then
    pid=$(sed -n '1p' "$pidfile" 2>/dev/null || true)
    if [ -n "$pid" ]; then
      kill_pids "$pid"
    fi
    rm -f "$pidfile" 2>/dev/null || true
  fi
done

# Ports commonly used in dev
PORTS=(5001 3100 5173 5174 5175 5176)
if command -v lsof >/dev/null 2>&1; then
  for p in "${PORTS[@]}"; do
    # lsof -t returns PIDs only; -iTCP:PORT -sTCP:LISTEN filters listeners
    pids=$(lsof -t -iTCP:"${p}" -sTCP:LISTEN 2>/dev/null || true)
    if [ -n "$pids" ]; then
      echo "[stop_all] killing listeners on port ${p}: ${pids}"
      # Use kill_pids helper to safely iterate
      kill_pids "$pids"
    fi
  done
else
  echo "[stop_all] lsof not found; skipping port-based kills"
fi

# Fallback patterns (conservative)
echo "[stop_all] killing common dev process patterns (python app.py, vite, npm dev, wrangler, pnpm)"
# Try pgrep/kill if available, otherwise use pkill. Both are commonly present on macOS/Linux.
if command -v pgrep >/dev/null 2>&1 && command -v xargs >/dev/null 2>&1; then
  # Find full commands and extract PIDs then kill via helper
  for pattern in "python .*app.py" "node .*vite" "npm .*run dev" "pnpm .*dev" "wrangler.*dev"; do
    pids=$(pgrep -f "$pattern" || true)
    if [ -n "$pids" ]; then
      echo "[stop_all] pattern match '$pattern' -> pids: $pids"
      kill_pids "$pids"
    fi
  done
else
  # Fallback to pkill -f (very conservative) if pgrep not available
  pkill -f "python .*app.py" 2>/dev/null || true
  pkill -f "node .*vite" 2>/dev/null || true
  pkill -f "npm .*run dev" 2>/dev/null || true
  pkill -f "pnpm .*dev" 2>/dev/null || true
  pkill -f "wrangler.*dev" 2>/dev/null || true
fi

echo "[stop_all] done"
