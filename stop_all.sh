#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR"

STATE_DIR="/tmp/bhabit_run"
echo "[stop_all] stopping dev services (state dir: ${STATE_DIR})"

# Kill PID files if present
for pidfile in "${STATE_DIR}/backend.pid" "${STATE_DIR}/frontend.pid"; do
  if [ -f "$pidfile" ]; then
    pid=$(cat "$pidfile" 2>/dev/null || true)
    if [ -n "$pid" ] && ps -p "$pid" >/dev/null 2>&1; then
      echo "[stop_all] killing pid $pid from $pidfile"
      kill "$pid" 2>/dev/null || true
      sleep 0.1
      if ps -p "$pid" >/dev/null 2>&1; then
        echo "[stop_all] escalating to kill -9 $pid"
        kill -9 "$pid" 2>/dev/null || true
      fi
    fi
    rm -f "$pidfile" 2>/dev/null || true
  fi
done

# Ports commonly used in dev
PORTS=(5001 3100 5173 5174 5175 5176)
if command -v lsof >/dev/null 2>&1; then
  for p in "${PORTS[@]}"; do
    pids=$(lsof -tiTCP:"${p}" -sTCP:LISTEN || true)
    if [ -n "$pids" ]; then
      echo "[stop_all] killing listeners on port ${p}: ${pids}"
      kill $pids 2>/dev/null || true
    fi
  done
fi

# Fallback patterns (conservative)
echo "[stop_all] killing common dev process patterns (python app.py, vite, npm dev, wrangler)"
pkill -f "python .*app.py" 2>/dev/null || true
pkill -f "python3 .*app.py" 2>/dev/null || true
pkill -f "node .*vite" 2>/dev/null || true
pkill -f "npm .*dev" 2>/dev/null || true
pkill -f "wrangler.*dev" 2>/dev/null || true

echo "[stop_all] done"
#!/usr/bin/env bash
set -euo pipefail

echo "[stop] stopping common dev processes"
pkill -f "python app.py --port" 2>/dev/null || true
pkill -f "vite" 2>/dev/null || true
pkill -f "wrangler.*dev" 2>/dev/null || true
pkill -f "wrangler.*pages" 2>/dev/null || true
echo "[stop] done."
