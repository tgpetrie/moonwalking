#!/usr/bin/env bash
set -euo pipefail

echo "[status] listening ports:"
lsof -iTCP -sTCP:LISTEN -n -P | awk 'NR==1 || /127\.0\.0\.1/ {print}'

echo
echo "[status] curl checks (best-effort):"
for url in \
  "http://127.0.0.1:3100" \
  "http://127.0.0.1:5001/api/server-info" \
  "http://127.0.0.1:8787" \
  "http://127.0.0.1:8789/api/server-info"
do
  echo; echo "==> $url"
  curl -sS "$url" | head -c 300 || true
  echo
done

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

echo -e "🐰 ${YELLOW}BHABIT Status Check${NC}"
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

echo ""
echo -e "${BLUE}API Health Checks${NC}"

# Test server-info
SI_URL="http://127.0.0.1:${PAGES_PORT}/api/server-info"
if command -v curl >/dev/null 2>&1; then
  echo -n "server-info: "
  RESP=$(curl -sS --max-time 2 "$SI_URL" 2>/dev/null || echo "")
  if [[ -n "$RESP" ]]; then
    if command -v jq >/dev/null 2>&1; then
      echo "$RESP" | jq -c . || echo "$RESP"
    else
      echo "$RESP"
    fi
  else
    echo -e "${RED}UNREACHABLE${NC} ($SI_URL)"
  fi

  # Test watchlist endpoint
  echo -n "watchlist: "
  WL_URL="http://127.0.0.1:${PAGES_PORT}/api/watchlist"
  WL_RESP=$(curl -sS --max-time 2 "$WL_URL" 2>/dev/null || echo "")
  if [[ -n "$WL_RESP" ]]; then
    if command -v jq >/dev/null 2>&1; then
      echo "$WL_RESP" | jq -c . || echo "$WL_RESP"
    else
      echo "$WL_RESP"
    fi
  else
    echo -e "${RED}UNREACHABLE${NC} ($WL_URL)"
  fi
else
  echo -e "${YELLOW}curl not found${NC}: cannot perform health checks"
fi

echo ""
echo -e "${BLUE}Quick Actions${NC}"
echo "- Start dev env: ./start_app.sh"
echo "- View logs:     tail -f .dev-do.log .dev-pages.log"
echo "- Stop all:      pkill -f wrangler"
