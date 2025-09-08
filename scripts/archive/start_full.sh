#!/bin/zsh
set -euo pipefail

echo "[CBMo4ers] 🚀 Starting fullstack (backend + frontend)..."

# Kill children on exit (Ctrl+C)
cleanup() {
  echo "[CBMo4ers] 🔻 Shutting down..."
  [[ -n "${BACKEND_PID-}" ]]  && kill $BACKEND_PID  2>/dev/null || true
  [[ -n "${FRONTEND_PID-}" ]] && kill $FRONTEND_PID 2>/dev/null || true
}
trap cleanup EXIT

# --- Backend ---
pushd "$HOME/Documents/moonwalkings/backend" >/dev/null
source ../.venv/bin/activate
echo "[Backend] Python: $(python -V)"
echo "[Backend] Starting Flask API on :5001 ..."
python app.py &          # app will auto-pick 5001 (or next free)
BACKEND_PID=$!
popd >/dev/null

# --- Frontend ---
pushd "$HOME/Documents/moonwalkings/frontend" >/dev/null
echo "[Frontend] Installing deps if needed..."
npm install --no-fund --no-audit
echo "[Frontend] Starting dev server on :3100 ..."
npm run dev &            # your nodemon server.js binds 127.0.0.1:3100
FRONTEND_PID=$!
popd >/dev/null

echo "[CBMo4ers] ✅ Backend:  http://127.0.0.1:5001"
echo "[CBMo4ers] ✅ Frontend: http://127.0.0.1:3100"
echo "[CBMo4ers] Press Ctrl+C to stop both."

# Wait for both processes
wait
