#!/usr/bin/env bash
set -euo pipefail

# BHABIT Status Check Script
# Shows running processes and tests API endpoints

GREEN='\033[0;32m'
RED='\033[0;31m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

: "${PAGES_PORT:=8789}"
: "${DO_PORT:=8787}"
: "${FLASK_PORT:=5001}"
: "${VITE_PORT:=5173}"

read_pid() { local f=$1; [[ -f "$f" ]] && cat "$f" || echo ""; }
is_alive() { local p=$1; [[ -n "$p" ]] && ps -p "$p" >/dev/null 2>&1; }

# Check various PIDs
PAGES_PID=$(read_pid .dev-pages.pid)
DO_PID=$(read_pid .dev-do.pid)
FLASK_PID=$(pgrep -f "python.*app.py" | head -1 || echo "")
VITE_PID=$(pgrep -f "vite" | head -1 || echo "")

echo "🐰 BHABIT Status Check"
echo "======================"

# Cloudflare processes
if is_alive "$PAGES_PID"; then
  echo -e "${GREEN}Pages dev${NC} PID=$PAGES_PID  URL=http://127.0.0.1:${PAGES_PORT}"
else
  echo -e "${RED}Pages dev not running${NC} (expected on :${PAGES_PORT})"
fi

if is_alive "$DO_PID"; then
  echo -e "${GREEN}Worker/DO dev${NC} PID=$DO_PID URL=http://127.0.0.1:${DO_PORT}"
else
  echo -e "${RED}Worker/DO dev not running${NC} (expected on :${DO_PORT})"
fi

# Flask backend
if [[ -n "$FLASK_PID" ]] && is_alive "$FLASK_PID"; then
  echo -e "${GREEN}Flask Backend${NC} PID=$FLASK_PID URL=http://127.0.0.1:${FLASK_PORT}"
else
  echo -e "${RED}Flask Backend not running${NC} (expected on :${FLASK_PORT})"
fi

# Vite frontend
if [[ -n "$VITE_PID" ]] && is_alive "$VITE_PID"; then
  echo -e "${GREEN}Vite Frontend${NC} PID=$VITE_PID URL=http://127.0.0.1:${VITE_PORT}"
else
  echo -e "${RED}Vite Frontend not running${NC} (expected on :${VITE_PORT})"
fi

echo ""
echo -e "${BLUE}API Health Checks${NC}"

# Test server-info
SI_URL="http://127.0.0.1:${PAGES_PORT}/api/server-info"
if command -v curl >/dev/null 2>&1; then
  echo -n "server-info: "
  RESP=$(curl -sS "$SI_URL" 2>/dev/null || echo "")
  if [[ -n "$RESP" ]]; then
    if command -v jq >/dev/null 2>&1; then
      echo "$RESP" | jq -c . || echo "$RESP"
    else
      echo "$RESP"
    fi
  else
    echo -e "${RED}FAILED${NC} ($SI_URL)"
  fi

  # Test watchlist endpoint
  echo -n "watchlist: "
  WL_URL="http://127.0.0.1:${PAGES_PORT}/api/watchlist"
  WL_RESP=$(curl -sS "$WL_URL" 2>/dev/null || echo "")
  if [[ -n "$WL_RESP" ]]; then
    if command -v jq >/dev/null 2>&1; then
      echo "$WL_RESP" | jq -c . || echo "$WL_RESP"
    else
      echo "$WL_RESP"
    fi
  else
    echo -e "${RED}FAILED${NC} ($WL_URL)"
  fi

  # Test codex endpoint
  echo -n "codex: "
  CX_URL="http://127.0.0.1:${PAGES_PORT}/api/codex"
  CX_RESP=$(curl -sS "$CX_URL" 2>/dev/null || echo "")
  if [[ -n "$CX_RESP" ]]; then
    if command -v jq >/dev/null 2>&1; then
      echo "$CX_RESP" | jq -c . || echo "$CX_RESP"
    else
      echo "$CX_RESP"
    fi
  else
    echo -e "${RED}FAILED${NC} ($CX_URL)"
  fi
else
  echo -e "${YELLOW}curl not found${NC}: cannot perform health checks"
fi

echo ""
echo -e "${BLUE}Quick Actions${NC}"
echo "- Start all: ./start_app.sh"
echo "- Start CF only: ./start_cloudflare.sh"
echo "- Logs: tail -f .dev-pages.log .dev-do.log backend/server.log frontend/terminal.log"
echo "- Stop all: pkill -f 'python.*app.py' && pkill -f vite && pkill -f wrangler"
