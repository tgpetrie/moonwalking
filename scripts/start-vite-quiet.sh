#!/usr/bin/env bash
set -e
# Quiet Vite start script — safe for VS Code terminal (no installs, no tails)
ROOT="$HOME/Documents/moonwalkings"

cd "$ROOT" || exit 1

echo "STEP 1: kill ports 5173/5174 if present"
lsof -tiTCP:5173 -sTCP:LISTEN | xargs -r kill -9 || true
lsof -tiTCP:5174 -sTCP:LISTEN | xargs -r kill -9 || true

echo "STEP 2: remove stale pid files"
rm -f frontend/vite.pid vite.pid || true

echo "STEP 3: start vite (assume deps already installed)"
cd frontend || exit 1
nohup npm run dev -- --host --port 5173 > ../frontend/vite.stdout 2>&1 &
echo $! > ../frontend/vite.pid
echo "Vite started pid=$(cat ../frontend/vite.pid 2>/dev/null || echo none)"

exit 0
