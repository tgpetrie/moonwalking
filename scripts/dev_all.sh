#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

# Clean slate
"$ROOT/scripts/kill_dev_procs.sh" || true
"$ROOT/scripts/kill_ports.sh" 5001 5173 || true

# Start backend in background
"$ROOT/scripts/dev_backend.sh" &
BACK_PID=$!

echo "[i] Waiting for backend on :5001…"
ready=0

# Use seq (portable) instead of {1..60} brace expansion
for i in $(seq 1 60); do
  if curl -fsS "http://127.0.0.1:5001/api/metrics" >/dev/null 2>&1; then
    echo "[+] Backend ready."
    ready=1
    break
  fi

  # Bail out if backend exited
  if ! kill -0 "$BACK_PID" 2>/dev/null; then
    echo "[-] Backend process exited early. Check your Python/venv. Aborting." >&2
    kill "$BACK_PID" 2>/dev/null || true
    exit 1
  fi

  sleep 0.5
done

if [[ "$ready" -ne 1 ]]; then
  echo "[-] Timeout waiting for backend on :5001" >&2
  kill "$BACK_PID" 2>/dev/null || true
  exit 1
fi

# Stop backend when this script exits
cleanup() { kill "$BACK_PID" 2>/dev/null || true; }
trap cleanup EXIT

# Run frontend in foreground (Ctrl+C to stop)
exec "$ROOT/scripts/dev_frontend.sh"
