#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR"

echo "[restart_local] stopping services"
./stop_local.sh

# Give the OS a moment to release ports
sleep 0.5

echo "[restart_local] starting services (running start_local.sh in foreground)"
echo "[restart_local] invoking start_local.sh in foreground (press Ctrl+C to stop)"
# Use FORCE_START=1 to ensure start_local replaces any leftover processes and FOLLOW_LOGS=1 to show logs
env FORCE_START=1 FOLLOW_LOGS=1 ./start_local.sh

echo "[restart_local] start_local.sh exited; check status with ./status_local.sh or tail logs in backend/server.stdout and frontend/vite.stdout"

exit 0
