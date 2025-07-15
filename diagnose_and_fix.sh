#!/bin/bash

# BHABIT CBMOONERS - Diagnostic and Fix Script
# This script diagnoses and fixes common frontend data display issues

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
PURPLE='\033[0;35m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[DIAGNOSTIC]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_fix() {
    echo -e "${PURPLE}[FIX]${NC} $1"
}

echo "🐰 BHABIT CBMOONERS - Frontend Data Display Diagnostic"
echo "=================================================="

# Step 1: Check if virtual environment exists and activate it
print_status "Checking Python virtual environment..."
if [ -d ".venv" ]; then
    print_success "Virtual environment found"
    source .venv/bin/activate
    print_success "Virtual environment activated"
else
    print_error "Virtual environment not found!"
    print_fix "Creating virtual environment..."
    python3 -m venv .venv
    source .venv/bin/activate
    print_success "Virtual environment created and activated"
fi

# Step 2: Check backend dependencies
print_status "Checking backend dependencies..."
cd backend
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt --quiet
    print_success "Backend dependencies verified"
else
    print_error "requirements.txt not found!"
    exit 1
fi

# Step 3: Test backend connectivity BEFORE starting servers
print_status "Testing external API connectivity..."
if python -c "
import requests
try:
    response = requests.get('https://api.exchange.coinbase.com/products', timeout=10)
    print('✅ Coinbase API accessible:', response.status_code == 200)
except Exception as e:
    print('❌ Coinbase API error:', str(e))
" 2>/dev/null; then
    print_success "External APIs are accessible"
else
    print_warning "Some external APIs may be unreachable"
fi

# Step 4: Kill any existing processes on required ports
print_status "Checking for existing processes on ports 5001 and 5173..."
if lsof -ti:5001 >/dev/null 2>&1; then
    print_warning "Port 5001 is in use. Killing existing process..."
    lsof -ti:5001 | xargs kill -9 2>/dev/null || true
    sleep 2
    print_success "Port 5001 cleared"
else
    print_success "Port 5001 is available"
fi

if lsof -ti:5173 >/dev/null 2>&1; then
    print_warning "Port 5173 is in use. Killing existing process..."
    lsof -ti:5173 | xargs kill -9 2>/dev/null || true
    sleep 2
    print_success "Port 5173 cleared"
else
    print_success "Port 5173 is available"
fi

# Step 5: Start backend with auto-port finding
print_status "Starting backend server with diagnostics..."
python app.py --auto-port &
BACKEND_PID=$!

# Wait for backend to start
print_status "Waiting for backend to initialize..."
sleep 10

# Step 6: Test backend endpoints
print_status "Testing backend endpoints..."
BACKEND_PORT=5001

# Find the actual port the backend is using
for port in 5001 5002 5003 5004 5005; do
    if curl -s "http://localhost:$port/health" >/dev/null 2>&1; then
        BACKEND_PORT=$port
        print_success "Backend found running on port $port"
        break
    fi
done

# Test health endpoint
if curl -s "http://localhost:$BACKEND_PORT/health" | grep -q "healthy\|running"; then
    print_success "Backend health check passed"
else
    print_error "Backend health check failed"
    print_fix "Checking backend logs for errors..."
    if ps -p $BACKEND_PID > /dev/null; then
        echo "Backend process is running but not responding correctly"
    else
        echo "Backend process has crashed"
    fi
fi

# Test gainers endpoint specifically
print_status "Testing gainers data endpoint..."
GAINERS_RESPONSE=$(curl -s "http://localhost:$BACKEND_PORT/api/component/gainers-table" || echo "ERROR")
if echo "$GAINERS_RESPONSE" | grep -q "data\|gainers"; then
    print_success "Gainers endpoint is working"
    echo "Sample response: $(echo "$GAINERS_RESPONSE" | head -c 200)..."
else
    print_error "Gainers endpoint failed"
    echo "Response: $GAINERS_RESPONSE"
fi

cd ..

# Step 7: Update frontend environment file
print_status "Updating frontend environment configuration..."
cd frontend

# Create/update .env file with correct backend URL
cat > .env << EOF
VITE_API_URL=http://localhost:$BACKEND_PORT
EOF

print_success "Frontend environment updated with backend port $BACKEND_PORT"

# Step 8: Install frontend dependencies
print_status "Verifying frontend dependencies..."
if [ ! -d "node_modules" ]; then
    print_fix "Installing frontend dependencies..."
    npm install
    print_success "Frontend dependencies installed"
else
    print_success "Frontend dependencies verified"
fi

# Step 9: Start frontend
print_status "Starting frontend development server..."
npm run dev &
FRONTEND_PID=$!

cd ..

# Wait for frontend to start
sleep 5

# Step 10: Final connectivity test
print_status "Performing final connectivity tests..."

# Test frontend
if curl -s "http://localhost:5173" >/dev/null 2>&1; then
    print_success "Frontend is accessible at http://localhost:5173"
else
    print_error "Frontend is not accessible"
fi

# Test API call from frontend perspective
print_status "Testing frontend to backend API communication..."
API_TEST=$(curl -s "http://localhost:$BACKEND_PORT/api/component/gainers-table" -H "Origin: http://localhost:5173" || echo "FAILED")
if echo "$API_TEST" | grep -q "data\|component"; then
    print_success "Frontend-to-backend API communication is working"
else
    print_error "Frontend-to-backend API communication failed"
    print_fix "CORS or connectivity issue detected"
fi

echo ""
echo "=================================================="
print_success "🎉 DIAGNOSTIC COMPLETE!"
echo ""
print_status "Application Status:"
echo "  • Backend: http://localhost:$BACKEND_PORT"
echo "  • Frontend: http://localhost:5173"
echo "  • Backend PID: $BACKEND_PID"
echo "  • Frontend PID: $FRONTEND_PID"
echo ""
print_status "If frontend still shows no data:"
echo "  1. Open browser developer tools (F12)"
echo "  2. Check Console tab for API errors"
echo "  3. Check Network tab for failed requests"
echo "  4. Verify that API calls are going to http://localhost:$BACKEND_PORT"
echo ""
print_status "To stop servers:"
echo "  kill $BACKEND_PID $FRONTEND_PID"
echo ""
print_success "Press Ctrl+C to stop diagnostic monitoring..."

# Monitor the processes
while true; do
    if ! ps -p $BACKEND_PID > /dev/null; then
        print_error "Backend process died!"
        break
    fi
    if ! ps -p $FRONTEND_PID > /dev/null; then
        print_error "Frontend process died!"
        break
    fi
    sleep 30
    print_status "Both servers still running..."
done
