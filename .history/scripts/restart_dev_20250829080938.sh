#!/usr/bin/env bash
set -euo pipefail

# ---- Config ----
BACKEND_PORT="${BACKEND_PORT:-5001}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"
FE_WRAPPER="$FRONTEND_DIR/scripts/start-5173-5001.sh"
LOGDIR="$ROOT_DIR/logs"
mkdir -p "$LOGDIR"

echo "[restart_dev] root=$ROOT_DIR"
echo "[restart_dev] stopping any listeners on :$BACKEND_PORT and :$FRONTEND_PORT"

# Kill listeners (graceful then hard)
for p in "$BACKEND_PORT" "$FRONTEND_PORT"; do
  if PIDS=$(lsof -ti tcp:$p 2>/dev/null | tr '\n' ' '); then
    [[ -n "$PIDS" ]] && echo "[restart_dev] killing PIDs on :$p -> $PIDS" && kill $PIDS 2>/dev/null || true
    sleep 0.2
    if lsof -ti tcp:$p >/dev/null 2>&1; then
      PIDS=$(lsof -ti tcp:$p 2>/dev/null | tr '\n' ' ')
      [[ -n "$PIDS" ]] && echo "[restart_dev] force-killing PIDs on :$p -> $PIDS" && kill -9 $PIDS 2>/dev/null || true
    fi
  fi
done

# Ensure frontend.port is written immediately (so /api/server-info is correct even before FE binds)
echo "$FRONTEND_PORT" > "$BACKEND_DIR/frontend.port"
echo "[restart_dev] wrote FE port file -> $BACKEND_DIR/frontend.port ($FRONTEND_PORT)"

# ---- Start backend ----
echo "[restart_dev] starting backend @ :$BACKEND_PORT"
(
  cd "$BACKEND_DIR"
  # pick a Python (venv preferred)
  if [[ -d .venv ]]; then
    # shellcheck disable=SC1091
    source .venv/bin/activate
  fi

  BACK_LOG="$LOGDIR/backend.log"
  : > "$BACK_LOG"

  if [[ -x ./start.sh ]]; then
    echo "[restart_dev] using backend/start.sh (logs: $BACK_LOG)"
    PORT="$BACKEND_PORT" ./start.sh >>"$BACK_LOG" 2>&1 &
  else
    echo "[restart_dev] using python app.py (logs: $BACK_LOG)"
    PORT="$BACKEND_PORT" python app.py >>"$BACK_LOG" 2>&1 &
  fi
)&
BACK_PID=$!

# Wait for backend port to listen
echo -n "[restart_dev] waiting for backend to listen on :$BACKEND_PORT"
for i in {1..80}; do
  if lsof -i tcp:$BACKEND_PORT -sTCP:LISTEN >/dev/null 2>&1; then
    echo " ✓"
    break
  fi
  echo -n "."
  sleep 0.25
  if [[ $i -eq 80 ]]; then
    echo " (timeout) — see $LOGDIR/backend.log"
  fi
done

# ---- Start frontend via wrapper (it already waits for Vite) ----
echo "[restart_dev] starting frontend via $FE_WRAPPER (port $FRONTEND_PORT)"
chmod +x "$FE_WRAPPER"
FRONTEND_PORT="$FRONTEND_PORT" BACKEND_PORT="$BACKEND_PORT" "$FE_WRAPPER"

# Summaries
echo
echo "[restart_dev] ✅ Backend   -> http://127.0.0.1:$BACKEND_PORT (log: $LOGDIR/backend.log)"
echo "[restart_dev] ✅ Frontend  -> http://localhost:$FRONTEND_PORT  (FE log: $FRONTEND_DIR/logs/frontend.log)"
echo "[restart_dev] Port file     $BACKEND_DIR/frontend.port = $(cat "$BACKEND_DIR/frontend.port" 2>/dev/null || echo '?')"

