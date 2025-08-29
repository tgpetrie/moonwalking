#!/usr/bin/env zsh
set -euo pipefail

FRONTEND_PORT=${FRONTEND_PORT:-5173}
BACKEND_PORT=${BACKEND_PORT:-5001}

SCRIPTDIR=$(cd "$(dirname "$0")" && pwd)
FRONTEND_DIR=$(cd "$SCRIPTDIR/.." && pwd)
REPO_ROOT=$(cd "$FRONTEND_DIR/.." && pwd)
BACKEND_DIR="$REPO_ROOT/backend"
LOGDIR="$FRONTEND_DIR/logs"
mkdir -p "$LOGDIR"

# Write intended FE port immediately so backend can read it
echo "$FRONTEND_PORT" > "$BACKEND_DIR/frontend.port"

echo "Killing anything on :$FRONTEND_PORT and :$BACKEND_PORT (if any)…"
for p in "$FRONTEND_PORT" "$BACKEND_PORT"; do
  if PIDS=$(lsof -ti tcp:$p 2>/dev/null | tr '\n' ' '); then
    [[ -n "$PIDS" ]] && kill $PIDS 2>/dev/null || true
    sleep 0.2
    if lsof -ti tcp:$p >/dev/null 2>&1; then
      PIDS=$(lsof -ti tcp:$p 2>/dev/null | tr '\n' ' ')
      [[ -n "$PIDS" ]] && kill -9 $PIDS 2>/dev/null || true
    fi
  fi
done

# Start backend (use your local start if present)
if [[ -d "$BACKEND_DIR" ]]; then
  echo "Starting backend…"
  (
    cd "$BACKEND_DIR"
    if [[ -x ./start.sh ]]; then
      ./start.sh > "$LOGDIR/backend.log" 2>&1
    else
      PORT=$BACKEND_PORT python app.py > "$LOGDIR/backend.log" 2>&1
    fi
  ) &
fi

# Start frontend (Vite)
echo "Starting Vite on :$FRONTEND_PORT…"
(
  cd "$FRONTEND_DIR"
  if [[ -f package.json ]]; then
    npm run dev -- --strictPort --port "$FRONTEND_PORT" > "$LOGDIR/frontend.log" 2>&1
  else
    echo "No package.json found in $FRONTEND_DIR" > "$LOGDIR/frontend.log"
    exit 1
  fi
) &

# Wait until Vite actually binds
echo -n "Waiting for Vite to listen on :$FRONTEND_PORT"
for i in {1..80}; do
  if lsof -i tcp:$FRONTEND_PORT -sTCP:LISTEN >/dev/null 2>&1; then
    echo " ✓"
    break
  fi
  echo -n "."
  sleep 0.25
  if [[ $i -eq 80 ]]; then
    echo " (timeout) — see $LOGDIR/frontend.log"
  fi
done

# Open browser (optional)
URL="http://localhost:$FRONTEND_PORT"
case "$(uname -s)" in
  Darwin) open "$URL" ;;
  Linux) command -v xdg-open >/dev/null && xdg-open "$URL" >/dev/null 2>&1 || true ;;
esac

echo "Logs in $LOGDIR"
