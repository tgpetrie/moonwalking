# stop orchestrator background run if used earlier
if [ -f /tmp/bhabit_start.pid ]; then
  kill $(cat /tmp/bhabit_start.pid) 2>/dev/null || true
  rm -f /tmp/bhabit_start.pid
fi

# stop backend (any python running app.py on port 5001)
pkill -f "python3 .*app.py" || true
lsof -ti:5001 | xargs kill -9 2>/dev/null || true

# stop frontend (vite dev server)
pkill -f "vite" || true
lsof -ti:5173 | xargs kill -9 2>/dev/null || true
#!/usr/bin/env bash
# Robust stopper for orchestrator, backend, and frontend dev servers.
# Works even if commands/ports changed between runs.

set -o pipefail

info() { printf "[stop] %s\n" "$*"; }
ok()   { printf "[stop] %s\n" "$*"; }
warn() { printf "[stop] %s\n" "$*"; }

kill_pidfile() {
  local f="$1"
  if [ -f "$f" ]; then
    local pid
    pid=$(cat "$f" 2>/dev/null)
    if [ -n "$pid" ]; then
      info "Killing PID from $f ($pid)"
      kill "$pid" 2>/dev/null || true
      sleep 0.2
      kill -9 "$pid" 2>/dev/null || true
    fi
    rm -f "$f"
    ok "Removed $f"
  fi
}

kill_by_pattern() {
  local pat="$1"
  info "Killing by pattern: $pat"
  pkill -f "$pat" 2>/dev/null || true
  sleep 0.2
  if pgrep -f "$pat" >/dev/null 2>&1; then
    warn "Pattern still alive, sending -9: $pat"
    pkill -9 -f "$pat" 2>/dev/null || true
  fi
}

kill_by_port() {
  local port="$1"
  local desc="${2:-process}"
  local pids
  pids=$(lsof -ti:"$port" 2>/dev/null | tr '\n' ' ')
  if [ -n "$pids" ]; then
    info "Killing $desc on port $port (pids: $pids)"
    kill $pids 2>/dev/null || true
    sleep 0.2
    kill -9 $pids 2>/dev/null || true
    ok "Freed $desc port $port"
  fi
}

info "Stopping orchestrator/background…"
kill_pidfile /tmp/bhabit_start.pid

info "Stopping backend (Flask/Uvicorn/Gunicorn/Python app.py)…"
kill_by_pattern "python3 .*app.py"
kill_by_pattern "flask run"
kill_by_pattern "uvicorn .*app:app"
kill_by_pattern "gunicorn .*app:app"

# Common backend ports you have used
for p in 5000 5001 5002 8000 8001; do
  kill_by_port "$p" backend
done

info "Stopping frontend (Vite dev server)…"
kill_by_pattern "[n]ode .*vite"
kill_by_pattern "vite dev"

# Common Vite ports (you mentioned 5176 earlier)
for p in 5173 5174 5175 5176; do
  kill_by_port "$p" vite
done

ok "All stop commands issued."
exit 0
#!/usr/bin/env bash
# stop_orchestrator_background.sh
# Stop ONLY the instance started by the paired start script, with clear logs.
# Uses PID files first; falls back to port-based lookup from state.json; then common patterns/ports.

set -euo pipefail

STATE_DIR="/tmp/bhabit_run"
BACKEND_PID="$STATE_DIR/backend.pid"
FRONTEND_PID="$STATE_DIR/frontend.pid"
STATE_JSON="$STATE_DIR/state.json"

info() { printf "[stop] %s\n" "$*"; }
ok()   { printf "[stop] %s\n" "$*"; }
warn() { printf "[stop] %s\n" "$*"; }

kill_pid_if_running () {
  local pid_file="$1"
  local label="$2"
  if [ -f "$pid_file" ]; then
    local pid
    pid=$(cat "$pid_file" 2>/dev/null || true)
    if [ -n "${pid:-}" ] && ps -p "$pid" >/dev/null 2>&1; then
      info "Killing $label PID $(cat "$pid_file") from $(basename "$pid_file")"
      kill "$pid" 2>/dev/null || true
      for i in {1..10}; do ps -p "$pid" >/dev/null 2>&1 || break; sleep 0.1; done
      ps -p "$pid" >/dev/null 2>&1 && kill -9 "$pid" 2>/dev/null || true
    else
      info "$label not running (no live PID in $(basename "$pid_file"))"
    fi
    rm -f "$pid_file"
    ok "Removed $(basename "$pid_file")"
  fi
}

kill_by_port () {
  local port="$1"; local desc="${2:-process}"
  local pids
  pids=$(lsof -ti tcp:"$port" -sTCP:LISTEN 2>/dev/null | tr '\n' ' ')
  if [ -n "$pids" ]; then
    info "Killing $desc on port $port (pids: $pids)"
    kill $pids 2>/dev/null || true
    for i in {1..10}; do
      local alive
      alive=$(lsof -ti tcp:"$port" -sTCP:LISTEN 2>/dev/null | tr '\n' ' ')
      [ -z "$alive" ] && break
      sleep 0.1
    done
    local still
    still=$(lsof -ti tcp:"$port" -sTCP:LISTEN 2>/dev/null | tr '\n' ' ')
    if [ -n "$still" ]; then
      warn "Port $port still busy; sending -9 to: $still"
      kill -9 $still 2>/dev/null || true
    fi
    ok "Freed $desc port $port"
  fi
}

kill_by_pattern () {
  local pat="$1"
  info "Killing by pattern: $pat"
  pkill -f "$pat" 2>/dev/null || true
  sleep 0.1
  if pgrep -f "$pat" >/dev/null 2>&1; then
    warn "Pattern still alive, sending -9: $pat"
    pkill -9 -f "$pat" 2>/dev/null || true
  fi
}

info "Stopping orchestrator/background…"
kill_pid_if_running "$FRONTEND_PID" frontend
kill_pid_if_running "$BACKEND_PID" backend

# Fallback via stored port
if [ -f "$STATE_JSON" ]; then
  BACKEND_PORT=$(awk -F: '/backend_port/ {gsub(/[^0-9]/, "", $2); print $2}' "$STATE_JSON" 2>/dev/null || true)
  if [ -n "${BACKEND_PORT:-}" ]; then
    kill_by_port "$BACKEND_PORT" backend
  fi
  rm -f "$STATE_JSON"
fi

# Final safety net: known patterns and ports you often use
info "Applying final safety checks…"
kill_by_pattern "python3 .*app.py"
kill_by_pattern "flask run"
kill_by_pattern "uvicorn .*app:app"
kill_by_pattern "gunicorn .*app:app"

for p in 5000 5001 5002 8000 8001; do kill_by_port "$p" backend; done

kill_by_pattern "[n]ode .*vite"
kill_by_pattern "vite dev"
for p in 5173 5174 5175 5176; do kill_by_port "$p" vite; done

ok "All stop commands issued."
exit 0