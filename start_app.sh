
#!/usr/bin/env bash
set -euo pipefail

print_status() { echo -e "\033[1;33m$*\033[0m"; }
print_error()  { echo -e "\033[1;31m$*\033[0m"; }

# go to repo root (this script's directory)
cd "$(dirname "$0")"

print_status "Starting backend and frontend servers (logs will be prefixed)..."

# Start backend
( cd backend && python3 app.py | sed -e 's/^/[backend] /' ) &
BACKEND_PID=$!

# Start frontend
( cd frontend && npm run dev | sed -e 's/^/[frontend] /' ) &
FRONTEND_PID=$!

trap 'print_status "Stopping servers..."; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null || true' INT TERM

print_status "Logs are prefixed with [backend] and [frontend]; press Ctrl+C to stop both."
wait