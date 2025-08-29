#!/usr/bin/env bash
set -euo pipefail

# Quick smoke test for local dev setup
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"

BACKEND_PORT="${BACKEND_PORT:-5001}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"

echo "Checking backend /api/server-info..."
if curl -sS "http://127.0.0.1:${BACKEND_PORT}/api/server-info" | grep -q "frontend" ; then
  echo "backend /api/server-info: OK"
else
  echo "backend /api/server-info: FAIL" >&2
  exit 2
fi

echo "Checking backend/frontend.port file..."
if [[ -f "$BACKEND_DIR/frontend.port" ]]; then
  val=$(cat "$BACKEND_DIR/frontend.port")
  echo "backend/frontend.port contains: $val"
else
  echo "backend/frontend.port missing" >&2
  exit 3
fi

echo "Checking Vite listening on :$FRONTEND_PORT"
if lsof -i tcp:$FRONTEND_PORT -sTCP:LISTEN >/dev/null 2>&1; then
  echo "Vite listening: OK"
else
  echo "Vite not listening on :$FRONTEND_PORT" >&2
  exit 4
fi

echo "Smoke test: all checks passed"
