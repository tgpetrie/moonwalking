#!/usr/bin/env bash
# Wrapper to start Vite dev server and write the detected port to ../backend/frontend.port
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
BACKEND_PORT_FILE="$ROOT/../backend/frontend.port"

# Allow optional --port passed through to vite
VITE_ARGS=("$@")

# Start vite in a subprocess and capture output to a temp logfile
TMP_LOG=$(mktemp -t vite-log.XXXXXX)
trap 'rm -f "$TMP_LOG"' EXIT

echo "[start-dev-with-port] starting vite (logging to $TMP_LOG)"
# Start vite in background and redirect stdout/stderr to tempfile
npx vite "${VITE_ARGS[@]}" > "$TMP_LOG" 2>&1 &
VITE_PID=$!

# Wait for Vite to print the local URL line and extract port
PORT=""
for i in {1..20}; do
  if grep -Eo "http://[0-9.]+:([0-9]{2,5})" "$TMP_LOG" >/dev/null 2>&1; then
    PORT=$(grep -Eo "http://[0-9.]+:([0-9]{2,5})" "$TMP_LOG" | sed -E 's/.*:([0-9]+)$/\1/' | head -n1)
    break
  fi
  if grep -Eo "http://localhost:([0-9]{2,5})" "$TMP_LOG" >/dev/null 2>&1; then
    PORT=$(grep -Eo "http://localhost:([0-9]{2,5})" "$TMP_LOG" | sed -E 's/.*:([0-9]+)$/\1/' | head -n1)
    break
  fi
  sleep 0.25
done

if [ -n "$PORT" ]; then
  echo "[start-dev-with-port] detected vite port: $PORT"
  # Write the port to the backend file
  echo "$PORT" > "$BACKEND_PORT_FILE" || true
else
  echo "[start-dev-with-port] Warning: could not detect vite port; frontend may be on default port"
  # Write configured default to file as a fallback ( Vite default is 5173 )
  echo "5173" > "$BACKEND_PORT_FILE" || true
fi

# Now tail the temp log and wait for the vite process so behavior is similar to running vite directly
tail -n +1 -f "$TMP_LOG" &
TAIL_PID=$!

# Wait for vite to exit and then cleanup
wait $VITE_PID
kill $TAIL_PID 2>/dev/null || true
