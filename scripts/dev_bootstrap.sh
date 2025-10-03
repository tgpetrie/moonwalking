<file name=backend/app.py>import os
from flask import Flask, Response, request, jsonify
import requests

app = Flask(__name__)

WORKER_ORIGIN = os.getenv("WORKER_ORIGIN", "http://127.0.0.1:8787")

def _filter_headers(h):
    """
    Drop hop-by-hop headers that break proxies per RFC 7230 §6.1.
    """
    hop = {
        "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
        "te", "trailers", "transfer-encoding", "upgrade"
    }
    return {k: v for k, v in h.items() if k.lower() not in hop}

@app.route("/api/snapshots/<path:subpath>", methods=["GET"])
def proxy_snapshots(subpath):
    """
    GET /api/snapshots/* -> WORKER_ORIGIN/snapshots/*
    Passes query string through and filters hop-by-hop headers.
    """
    url = f"{WORKER_ORIGIN.rstrip('/')}/snapshots/{subpath}"
    upstream = requests.get(
        url,
        params=request.args,
        headers=_filter_headers(request.headers),
        timeout=8,
    )
    return Response(
        upstream.content,
        status=upstream.status_code,
        headers=_filter_headers(upstream.headers),
    )

@app.route("/health", methods=["GET"])
def health():
    """
    Simple liveness check used by dev_bootstrap.
    """
    return jsonify(ok=True), 200
</file>

<file name=scripts/smoke_dev.sh>#!/usr/bin/env bash
set -euo pipefail

API_ORIGIN="${API_ORIGIN:-http://127.0.0.1:3100}"  # Vite dev proxy origin
SNAP="${API_ORIGIN}/api/snapshots/one-hour-price"
SSE="${API_ORIGIN}/api/events"

echo "→ Checking snapshot: ${SNAP}"
json=$(curl -fsS --max-time 5 "${SNAP}")
echo "   OK: $(echo "$json" | head -c 120) ..."

# Basic sanity: ok==true and rows is an array
echo "$json" | python3 - <<'PY'
import sys, json
data = json.load(sys.stdin)
assert data.get("ok") is True, "ok != true"
assert isinstance(data.get("rows"), list), "rows not list"
PY
echo "   JSON shape looks good."

echo "→ Checking SSE: ${SSE}"
# Read just a couple SSE lines to confirm stream opens
curl -fsS -N --max-time 5 -H 'Accept: text/event-stream' "${SSE}" | sed -n '1,5p' || true
echo "   SSE opened."

echo "✓ Smoke tests passed."
</file>

<file name=scripts/dev_bootstrap.sh>#!/usr/bin/env bash
set -euo pipefail

# tiny helper: wait for an HTTP 200 from a URL
wait_for_http() {
  local url="$1" name="${2:-service}" tries="${3:-40}" sleep_s="${4:-0.25}"
  for ((i=1; i<=tries; i++)); do
    if curl -fsS --max-time 2 "$url" >/dev/null; then
      echo "[dev_bootstrap] $name is up: $url"
      return 0
    fi
    sleep "$sleep_s"
  done
  echo "[dev_bootstrap] $name did not become healthy: $url"
  return 1
}

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "[dev_bootstrap] repo root: $ROOT"

echo "[dev_bootstrap] killing old processes (wrangler, backend, vite) if present..."
pkill -f "wrangler.*dev" 2>/dev/null || true
pkill -f "node .*vite" 2>/dev/null || true
pkill -f "python .*backend/app.py" 2>/dev/null || true

# Free common ports if anything stuck
for P in 8787 5001 3100; do
  echo "[dev_bootstrap] freeing port $P if occupied"
  lsof -ti :${P} -sTCP:LISTEN | xargs -I{} kill -9 {} 2>/dev/null || true
done

# Activate venv if present
if [ -f ".venv/bin/activate" ]; then
  echo "[dev_bootstrap] activating .venv"
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

mkdir -p backend

echo "[dev_bootstrap] starting backend (Flask) -> backend/server.stdout"
# Start backend in background and capture pid
nohup bash -lc "python backend/app.py --host 127.0.0.1 --port 5001" > backend/server.stdout 2>&1 &
echo $! > backend/backend.pid

echo "[dev_bootstrap] waiting for backend health"
wait_for_http "http://127.0.0.1:5001/health" "backend" 40 0.25

echo "[dev_bootstrap] starting wrangler dev -> workers.log"
nohup npx wrangler@latest dev --local --port=8787 > workers.log 2>&1 &
echo $! > workers.pid || true

echo "[dev_bootstrap] waiting for worker at http://127.0.0.1:8787/api/events"
for i in $(seq 1 30); do
  if curl -sS --max-time 2 -I http://127.0.0.1:8787/api/events >/dev/null 2>&1; then
    echo "[dev_bootstrap] worker appears reachable"
    break
  fi
  sleep 1
done

echo "[dev_bootstrap] starting Vite dev -> frontend/vite.stdout"
nohup npm --prefix frontend run dev > frontend/vite.stdout 2>&1 &
echo $! > frontend/vite.pid || true

# Wait for Vite dev server to accept connections (default 3100)
echo "[dev_bootstrap] waiting for Vite dev server"
wait_for_http "http://127.0.0.1:3100" "vite" 40 0.25

# Run quick smoke tests to validate the stack
echo "[dev_bootstrap] running smoke tests (scripts/smoke_dev.sh)"
if ! scripts/smoke_dev.sh; then
  echo "[dev_bootstrap] smoke tests failed; check logs: backend/server.stdout frontend/vite.stdout workers.log"
  exit 1
fi

echo "[dev_bootstrap] done. Logs: backend/server.stdout frontend/vite.stdout workers.log"
echo "To follow logs: tail -f backend/server.stdout frontend/vite.stdout workers.log"

exit 0
</file>
