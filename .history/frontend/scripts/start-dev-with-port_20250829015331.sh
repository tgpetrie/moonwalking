#!/usr/bin/env bash
# Wrapper to start Vite dev server and write the intended port to ../backend/frontend.port
# Then wait for TCP readiness before returning. This implements: write -> start -> wait.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
BACKEND_PORT_FILE="$ROOT/../backend/frontend.port"

# Configurable via env or default
FRONTEND_PORT="${FRONTEND_PORT:-5173}"
TIMEOUT="${TIMEOUT:-30}"

# Allow optional extra args passed through to vite
VITE_ARGS=("$@")

TMP_LOG=$(mktemp -t vite-log.XXXXXX)
trap 'rm -f "$TMP_LOG"' EXIT

echo "[start-dev-with-port] intent: port=$FRONTEND_PORT, writing to $BACKEND_PORT_FILE"
# 0) Write the intended port early so other processes can discover intent
echo -n "$FRONTEND_PORT" > "$BACKEND_PORT_FILE" || true

echo "[start-dev-with-port] starting vite (logging to $TMP_LOG)"
# Start vite in background and redirect stdout/stderr to tempfile
npx vite "${VITE_ARGS[@]}" > "$TMP_LOG" 2>&1 &
VITE_PID=$!

echo "Waiting for Vite on :$FRONTEND_PORT (timeout ${TIMEOUT}s)"
deadline=$((SECONDS + TIMEOUT))
ready=0
if command -v nc >/dev/null 2>&1; then
  while [ "$SECONDS" -lt "$deadline" ]; do
    if nc -z 127.0.0.1 "$FRONTEND_PORT" 2>/dev/null; then
      ready=1
      break
    fi
    sleep 0.25
  done
else
  # Fallback: try HTTP probe with curl if available
  if command -v curl >/dev/null 2>&1; then
    while [ "$SECONDS" -lt "$deadline" ]; do
      if curl -fsS "http://127.0.0.1:${FRONTEND_PORT}/" >/dev/null 2>&1; then
        ready=1
        break
      fi
      sleep 0.25
    done
  else
    # Last-resort: try bash /dev/tcp (may not be available on all shells)
    while [ "$SECONDS" -lt "$deadline" ]; do
      if (echo > /dev/tcp/127.0.0.1/$FRONTEND_PORT) >/dev/null 2>&1; then
        ready=1
        break
      fi
      sleep 0.25
    done
  fi
fi

if [ "$ready" -ne 1 ]; then
  echo "❌ Vite didn’t bind :$FRONTEND_PORT within ${TIMEOUT}s. Check for port conflict: lsof -nPi :$FRONTEND_PORT"
  kill "$VITE_PID" 2>/dev/null || true
  exit 1
fi

# Optional: detect actual bound port from vite log (useful if not strictPort)
DETECTED_PORT=""
if grep -Eo "http://[0-9.]+:([0-9]{2,5})" "$TMP_LOG" >/dev/null 2>&1; then
  DETECTED_PORT=$(grep -Eo "http://[0-9.]+:([0-9]{2,5})" "$TMP_LOG" | sed -E 's/.*:([0-9]+)$/\1/' | head -n1)
elif grep -Eo "http://localhost:([0-9]{2,5})" "$TMP_LOG" >/dev/null 2>&1; then
  DETECTED_PORT=$(grep -Eo "http://localhost:([0-9]{2,5})" "$TMP_LOG" | sed -E 's/.*:([0-9]+)$/\1/' | head -n1)
fi

if [ -n "$DETECTED_PORT" ] && [ "$DETECTED_PORT" != "$FRONTEND_PORT" ]; then
  echo "[start-dev-with-port] detected vite actual port: $DETECTED_PORT (overwriting intent file)"
  echo -n "$DETECTED_PORT" > "$BACKEND_PORT_FILE" || true
else
  echo "[start-dev-with-port] vite appears to be listening on :$FRONTEND_PORT"
fi

echo "✅ Vite is listening on http://127.0.0.1:${FRONTEND_PORT}"

# Tail the log so the wrapper behaves like running vite directly
tail -n +1 -f "$TMP_LOG" &
TAIL_PID=$!

# Wait for vite to exit and then cleanup
wait $VITE_PID
kill $TAIL_PID 2>/dev/null || true
