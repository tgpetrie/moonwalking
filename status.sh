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
