#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

PAGES_PORT="${PAGES_PORT:-8789}"
DO_PORT="${DO_PORT:-8787}"
FLASK_PORT="${FLASK_PORT:-5001}"

echo "== BHABIT status =="

show_pid() {
  local label="$1" pidfile="$2"
  if [[ -f "$pidfile" ]]; then
    local pid="$(cat "$pidfile" || true)"
    if [[ -n "$pid" ]] && ps -p "$pid" >/dev/null 2>&1; then
      echo "${label}: running (PID $pid)"
    else
      echo "${label}: not running (stale pidfile $pidfile)"
    fi
  else
    echo "${label}: pidfile missing"
  fi
}

show_pid "Pages (wrangler pages dev)" ".dev-pages.pid"
show_pid "Worker/DO (wrangler dev)" ".dev-do.pid"
show_pid "Backend (Flask)" ".backend.pid"
show_pid "Frontend (Vite)" ".frontend.pid"

echo
echo "URLs:"
echo "  Pages:   http://127.0.0.1:${PAGES_PORT}"
echo "  Worker:  http://127.0.0.1:${DO_PORT}"
echo "  Backend: http://127.0.0.1:${FLASK_PORT}"

echo
echo "Health checks:"
check() {
  local url="$1"; shift
  if command -v curl >/dev/null 2>&1; then
    echo "- GET ${url}"
    set +e
    curl -fsS --max-time 2 "$url" | (command -v jq >/dev/null 2>&1 && jq . || cat) || echo "(unreachable)"
    set -e
  else
    echo "curl not installed"
  fi
  echo
}

check "http://127.0.0.1:${PAGES_PORT}/api/server-info"
check "http://127.0.0.1:${FLASK_PORT}/server-info"

echo "Recent logs:"; echo
for f in .dev-pages.log .dev-do.log .backend.log .frontend.log orchestrator.bg.log; do
  if [[ -f "$f" ]]; then
    echo "--- $f (last 40 lines) ---"
    tail -n 40 "$f" || true
    echo
  fi
done

echo "Done."
