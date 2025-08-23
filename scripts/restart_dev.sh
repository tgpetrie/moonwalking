#!/usr/bin/env bash
set -euo pipefail

DRY=0
if [[ "${1:-}" == "--dry-run" ]]; then DRY=1; fi

logdir="./logs"
mkdir -p "$logdir"
timestamp="$(date +"%Y-%m-%d_%H-%M-%S")"
logfile="$logdir/start-$timestamp.log"

ports=(5173 5174 5001)

echo "Scanning ports: ${ports[*]}"
for p in "${ports[@]}"; do
  if lsof -ti :"$p" >/dev/null 2>&1; then
    pids=$(lsof -ti :"$p")
    echo "Killing PIDs on port $p: $(echo "$pids" | tr '\n' ' ')"
    if [[ $DRY -eq 0 ]]; then
      echo "$pids" | xargs -n1 kill -9 || true
    fi
  else
    echo "No process found on port $p"
  fi
done

start_bg () {
  local label="$1"
  local cmd="$2"
  echo "Starting: $cmd"
  if [[ $DRY -eq 0 ]]; then
    nohup bash -lc "$cmd" >> "$logfile" 2>&1 &
    echo "  PID: $!  log: $logfile"
  else
    echo "  (dry-run) would nohup: $cmd"
  fi
}

# Frontend
if [[ -x "./frontend/start.sh" ]]; then
  start_bg "frontend" "./frontend/start.sh"
else
  # fallback to vite directly
  start_bg "frontend" "cd ./frontend && npm install && npx vite --port 5173"
fi

# Backend
if [[ -x "./backend/start.sh" ]]; then
  start_bg "backend" "./backend/start.sh"
else
  # fallback: try Flask app.py on 5001
  start_bg "backend" "cd ./backend && \
    python -m venv .venv && source .venv/bin/activate && \
    pip install -r requirements.txt 2>/dev/null || true && \
    (FLASK_APP=app:app flask --debug run --port 5001 || python app.py)"
fi

echo "Done."
