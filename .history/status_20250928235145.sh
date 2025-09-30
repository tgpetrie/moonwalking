#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR"

STATE_DIR="/tmp/bhabit_run"
echo "state dir: ${STATE_DIR}"
for pidfile in "${STATE_DIR}/backend.pid" "${STATE_DIR}/frontend.pid"; do
  if [ -f "$pidfile" ]; then
    pid=$(cat "$pidfile" 2>/dev/null || true)
    printf "%s: %s\n" "$(basename $pidfile)" "${pid}"
    if [ -n "$pid" ] && ps -p "$pid" >/dev/null 2>&1; then
      ps -p "$pid" -o pid,cmd --no-headers
    else
      echo "  not running"
    fi
  else
    printf "%s: not present\n" "$(basename $pidfile)"
  fi
done

echo "Listening ports (tcp):"
if command -v lsof >/dev/null 2>&1; then
  lsof -nP -iTCP -sTCP:LISTEN | egrep '\b(5001|3100|5173|5174|5175|5176)\b' || true
else
  ss -ltnp | egrep '5001|3100|5173|5174|5175|5176' || true
fi
#!/bin/bash

# BHABIT CBMOONERS - Quick Status Check
# Check if everything is running properly

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

echo "🐰 BHABIT CBMOONERS - Quick Status Check"
echo "========================================"

# Check backend
if curl -s http://localhost:5001/health > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Backend API${NC} - Running on http://localhost:5001"
else
    echo -e "${RED}❌ Backend API${NC} - Not accessible"
fi

# Check frontend
if curl -s http://localhost:5173 > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Frontend App${NC} - Running on http://localhost:5173"
else
    echo -e "${RED}❌ Frontend App${NC} - Not accessible"
fi

# Check API data
API_DATA=$(curl -s http://localhost:5001/api/component/gainers-table 2>/dev/null)
if echo "$API_DATA" | grep -q "data"; then
    echo -e "${GREEN}✅ API Data${NC} - Cryptocurrency data is flowing"
else
    echo -e "${RED}❌ API Data${NC} - No data or API error"
fi

# Check external API
if curl -s https://api.exchange.coinbase.com/products > /dev/null 2>&1; then
    echo -e "${GREEN}✅ External APIs${NC} - Coinbase accessible"
else
    echo -e "${RED}❌ External APIs${NC} - Connectivity issues"
fi

echo ""
echo -e "${BLUE}Quick commands:${NC}"
echo "• ./dev.sh health     - Detailed health check"
echo "• ./dev.sh start      - Start both servers"
echo "• ./dev.sh diagnose   - Fix any issues"
