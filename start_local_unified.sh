#!/usr/bin/env bash
#
# start_local_unified.sh
# Start the entire moonwalking stack: backend (Flask), bridge (Node), frontend (Vite)
#

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

echo "🚀 Starting moonwalking local stack..."
echo ""

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Kill existing processes
echo -e "${YELLOW}🧹 Cleaning up existing processes...${NC}"
pkill -f "python.*app.py" 2>/dev/null || true
pkill -f "node.*server.js" 2>/dev/null || true
pkill -f "vite" 2>/dev/null || true
sleep 2

# Start backend (Flask on 5001)
echo -e "${BLUE}📦 Starting Flask backend on port 5001...${NC}"
cd "$PROJECT_ROOT/backend"
python app.py > "$PROJECT_ROOT/backend.log" 2>&1 &
BACKEND_PID=$!
echo "Backend PID: $BACKEND_PID"
sleep 3

# Verify backend
if curl -sS http://127.0.0.1:5001/api/component/gainers-table > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Backend is running${NC}"
else
    echo -e "${YELLOW}⚠️  Backend may not be ready yet${NC}"
fi

# Start bridge (Node on 5100)
echo -e "${BLUE}🌉 Starting Node.js bridge on port 5100...${NC}"
cd "$PROJECT_ROOT"
node server.js > "$PROJECT_ROOT/bridge.log" 2>&1 &
BRIDGE_PID=$!
echo "Bridge PID: $BRIDGE_PID"
sleep 3

# Verify bridge
if curl -sS http://127.0.0.1:5100/health > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Bridge is running${NC}"
else
    echo -e "${YELLOW}⚠️  Bridge may not be ready yet${NC}"
fi

# Start frontend (Vite on 5173)
echo -e "${BLUE}🎨 Starting Vite frontend on port 5173...${NC}"
cd "$PROJECT_ROOT/frontend"
npx vite --host 127.0.0.1 --port 5173 > "$PROJECT_ROOT/vite.log" 2>&1 &
VITE_PID=$!
echo "Vite PID: $VITE_PID"
sleep 3

# Verify frontend
if lsof -nP -iTCP:5173 -sTCP:LISTEN > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Frontend is running${NC}"
else
    echo -e "${YELLOW}⚠️  Frontend may not be ready yet${NC}"
fi

echo ""
echo -e "${GREEN}🎉 Stack started!${NC}"
echo ""
echo "Services:"
echo "  📦 Backend:  http://127.0.0.1:5001  (Flask)"
echo "  🌉 Bridge:   http://127.0.0.1:5100  (Socket.IO)"
echo "  🎨 Frontend: http://127.0.0.1:5173  (Vite)"
echo ""
echo "Logs:"
echo "  Backend:  tail -f $PROJECT_ROOT/backend.log"
echo "  Bridge:   tail -f $PROJECT_ROOT/bridge.log"
echo "  Frontend: tail -f $PROJECT_ROOT/vite.log"
echo ""
echo "PIDs: Backend=$BACKEND_PID Bridge=$BRIDGE_PID Vite=$VITE_PID"
echo ""
echo "To stop all services:"
echo "  kill $BACKEND_PID $BRIDGE_PID $VITE_PID"
echo "  or run: pkill -f 'python.*app.py'; pkill -f 'node.*server.js'; pkill -f 'vite'"
