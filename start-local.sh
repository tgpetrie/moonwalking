#!/bin/zsh

# 0) paths (change if yours are different)
FRONTEND=~/Documents/moonwalkings/frontend
BACKEND=~/Documents/moonwalkings/backend

echo "== kill old vite on 5173-5175 =="
pids=$(lsof -tiTCP:5173,5174,5175 -sTCP:LISTEN 2>/dev/null || true)
if [ -n "$pids" ]; then
  echo "killing: $pids"
  kill -9 $pids 2>/dev/null || true
else
  echo "no vite pids on 5173-5175"
fi

echo "== clear vite cache =="
rm -rf "$FRONTEND/node_modules/.vite" 2>/dev/null || true

# 1) start backend (optional but useful)
# will use the venv we already created: backend/.venv
if [ -x "$BACKEND/.venv/bin/python" ]; then
  echo "== (re)start backend on 127.0.0.1:5003 =="
  # kill old backend on 5003
  bpids=$(lsof -tiTCP:5003 -sTCP:LISTEN 2>/dev/null || true)
  [ -n "$bpids" ] && kill -9 $bpids 2>/dev/null || true

  cd "$BACKEND"
  nohup .venv/bin/python app.py --host 127.0.0.1 --port 5003 >/tmp/mw_backend.log 2>&1 &
  echo $! > /tmp/mw_backend.pid
  echo "backend pid: $(cat /tmp/mw_backend.pid)"
else
  echo "backend venv not found, skipping backend start"
fi

# 2) start Vite in foreground (keep terminal open)
echo "== start vite on 127.0.0.1:5173 =="
cd "$FRONTEND"
npm run dev -- --host 127.0.0.1 --port 5173
