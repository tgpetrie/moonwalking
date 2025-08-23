#!/usr/bin/env zsh
set -euo pipefail

# Start script: kills any process on ports 5173 (frontend) and 5001 (backend),
# starts backend and frontend preview, waits for them to listen, and opens the browser.

FRONTEND_PORT=5173
BACKEND_PORT=5001

# Resolve directories
SCRIPTDIR=$(cd "$(dirname "$0")" && pwd)
FRONTEND_DIR=$(cd "$SCRIPTDIR/.." && pwd)
REPO_ROOT=$(cd "$FRONTEND_DIR/.." && pwd)
BACKEND_DIR="$REPO_ROOT/backend"
LOGDIR="$FRONTEND_DIR/logs"
mkdir -p "$LOGDIR"

echo "Stopping processes on ports $FRONTEND_PORT and $BACKEND_PORT (if any)"
for p in $FRONTEND_PORT $BACKEND_PORT; do
  PIDS=$(lsof -ti tcp:$p || true)
  if [[ -n "$PIDS" ]]; then
    echo "Killing PIDs on port $p: $PIDS"
    kill $PIDS || kill -9 $PIDS || true
  else
    echo "No process on port $p"
  fi
done

# Start backend
if [[ -d "$BACKEND_DIR" ]]; then
  echo "Starting backend from $BACKEND_DIR"
  pushd "$BACKEND_DIR" >/dev/null
  if [[ -x ./start.sh ]]; then
    ./start.sh > "$LOGDIR/backend.log" 2>&1 &
    BACKEND_PID=$!
  elif command -v gunicorn >/dev/null && [[ -f app.py ]]; then
    gunicorn app:app -b 0.0.0.0:$BACKEND_PORT > "$LOGDIR/backend.log" 2>&1 &
    BACKEND_PID=$!
  else
    python3 app.py > "$LOGDIR/backend.log" 2>&1 &
    BACKEND_PID=$!
  fi
  popd >/dev/null
else
  echo "Warning: backend directory $BACKEND_DIR not found; skipping backend start"
fi

# Wait for backend to listen
if [[ -n "${BACKEND_PID:-}" ]]; then
  echo -n "Waiting for backend on port $BACKEND_PORT"
  RETRIES=40
  i=0
  while ! lsof -i tcp:$BACKEND_PORT -sTCP:LISTEN >/dev/null 2>&1; do
    sleep 0.25
    i=$((i+1))
    echo -n "."
    if [[ $i -ge $RETRIES ]]; then
      echo
      echo "Backend did not start within expected time; check $LOGDIR/backend.log"
      break
    fi
  done
  echo " done."
fi

# Start frontend preview
echo "Starting frontend preview from $FRONTEND_DIR"
pushd "$FRONTEND_DIR" >/dev/null
if [[ -f package.json ]]; then
  # Start Vite dev server with HMR on port 5173 for development
  npm run dev -- --port $FRONTEND_PORT > "$LOGDIR/frontend.log" 2>&1 &
  FRONTEND_PID=$!
else
  echo "No package.json in $FRONTEND_DIR; cannot start frontend"
fi
popd >/dev/null

# Wait for frontend
if [[ -n "${FRONTEND_PID:-}" ]]; then
  echo -n "Waiting for frontend on port $FRONTEND_PORT"
  i=0
  RETRIES=40
  while ! lsof -i tcp:$FRONTEND_PORT -sTCP:LISTEN >/dev/null 2>&1; do
    sleep 0.25
    i=$((i+1))
    echo -n "."
    if [[ $i -ge $RETRIES ]]; then
      echo
      echo "Frontend did not start within expected time; check $LOGDIR/frontend.log"
      break
    fi
  done
  echo " done."
fi

# Open browser
URL="http://localhost:$FRONTEND_PORT"
if [[ "$(uname)" == "Darwin" ]]; then
  open "$URL"
elif command -v xdg-open >/dev/null; then
  xdg-open "$URL" >/dev/null 2>&1 || true
else
  echo "Please open $URL in your browser"
fi

echo "Backend PID: ${BACKEND_PID:-unknown}, Frontend PID: ${FRONTEND_PID:-unknown}"
echo "Logs: $LOGDIR"
