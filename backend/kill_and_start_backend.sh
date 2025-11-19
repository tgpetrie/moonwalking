#!/usr/bin/env bash
set -euo pipefail

LOG=/tmp/mw_backend.log
PORT=5001
HOST=127.0.0.1

echo "[backend] killing anything on :$PORT and old app.py"
pkill -f "app.py" 2>/dev/null || true
kill -9 $(lsof -tiTCP:$PORT -sTCP:LISTEN 2>/dev/null) 2>/dev/null || true

cd "$(dirname "$0")"
[ -d .venv ] || python3 -m venv .venv
. .venv/bin/activate
pip install -q --upgrade pip setuptools wheel
pip install -q -r requirements.txt

echo "[backend] starting Flask on $HOST:$PORT → $LOG"
nohup python app.py --host "$HOST" --port "$PORT" > "$LOG" 2>&1 &
sleep 1
echo "[backend] tail log:"
tail -n 50 "$LOG" || true
