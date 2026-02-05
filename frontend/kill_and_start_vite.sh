#!/usr/bin/env bash
set -euo pipefail

LOG=/tmp/mw_vite.log
PORT=5173
HOST=127.0.0.1

echo "[vite] killing vite and :$PORT/:5174/:5175 listeners"
pkill -f "vite"



cd "$(dirname "$0")"
rm -rf node_modules/.vite

echo "[vite] starting on $HOST:$PORT → $LOG"
nohup npm run dev -- --host "$HOST" --port "$PORT" > "$LOG" 2>&1 &
sleep 1
tail -n 30 "$LOG" || true
