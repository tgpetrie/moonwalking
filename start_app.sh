#!/bin/bash

# BHABIT CBMOONERS - Application Startup Script
# This script starts both the backend Flask server and frontend Vite development server

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[BHABIT]${NC} $1"
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

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to wait for an HTTP 200 from a URL (readiness probe)
wait_for_http_200() {
    local url="$1"
    local timeout="${2:-30}"
    local interval="${3:-0.5}"
    local end=$((SECONDS + timeout))
    # Avoid exiting the whole script on curl failure inside this loop
    set +e
    while (( SECONDS < end )); do
        # Only treat HTTP 200 as ready; suppress output
        local code
        code=$(curl -s -o /dev/null -w "%{http_code}" "$url" 2>/dev/null)
        if [ "$code" = "200" ]; then
            set -e
            return 0
        fi
        sleep "$interval"
    done
    set -e
    return 1
}

# Function to cleanup background processes on exit
cleanup() {
    print_status "Shutting down servers..."
    if [ ! -z "$BACKEND_PID" ]; then
        kill $BACKEND_PID 2>/dev/null || true
    fi
    if [ ! -z "$FRONTEND_PID" ]; then
        kill $FRONTEND_PID 2>/dev/null || true
    fi
    print_success "Servers stopped."
}

# Set up cleanup trap
trap cleanup EXIT INT TERM

print_status "Starting BHABIT CBMOONERS Application..."

# Load root .env if present (export all vars)
if [ -f ".env" ]; then
    print_status "Loading environment from .env"
    set -a
    # shellcheck disable=SC1091
    source .env
    set +a
fi

# 1‑minute movers thresholds (defaults if not provided)
: "${ONE_MIN_ENTER_PCT:=0.15}"
: "${ONE_MIN_STAY_PCT:=0.05}"
: "${ONE_MIN_SEED_PCT:=0.02}"
: "${ONE_MIN_SEED_COUNT:=6}"
export ONE_MIN_ENTER_PCT ONE_MIN_STAY_PCT ONE_MIN_SEED_PCT ONE_MIN_SEED_COUNT

print_status "1‑min thresholds:"
echo "  ENTER_PCT=${ONE_MIN_ENTER_PCT}%  STAY_PCT=${ONE_MIN_STAY_PCT}%  SEED_PCT=${ONE_MIN_SEED_PCT}%  SEED_COUNT=${ONE_MIN_SEED_COUNT}"

# Check required commands
if ! command_exists python3; then
    print_error "Python 3 is not installed. Please install Python 3.13+ to continue."
    exit 1
fi

if ! command_exists npm; then
    print_error "Node.js/npm is not installed. Please install Node.js 22.17+ to continue."
    exit 1
fi

if ! command_exists curl; then
    print_error "curl is required for readiness checks. Please install curl."
    exit 1
fi

# Check if backend exists
if [ ! -f "backend/app.py" ]; then
    print_error "Backend server not found! Please ensure 'backend/app.py' exists."
    exit 1
fi

# Check if frontend exists
if [ ! -d "frontend" ]; then
    print_error "Frontend directory not found! Please ensure 'frontend/' directory exists."
    exit 1
fi

# Activate virtual environment if it exists
if [ -d ".venv" ]; then
    print_status "Activating Python virtual environment..."
    source .venv/bin/activate
    print_success "Virtual environment activated."
else
    print_warning "No virtual environment found. Consider creating one with: python3 -m venv .venv"
fi

# Install backend dependencies if needed
if [ -f "backend/requirements.txt" ]; then
    print_status "Checking backend dependencies..."
    pip install --upgrade pip setuptools
    cd backend
    pip install -q -r requirements.txt
    cd ..
    print_success "Backend dependencies verified."
fi

# Install frontend dependencies if needed
print_status "Checking frontend dependencies..."
cd frontend
if [ ! -d "node_modules" ]; then
    print_status "Installing frontend dependencies..."
    npm install
fi
cd ..
print_success "Frontend dependencies verified."

# Start backend server
print_status "Starting backend server on http://localhost:5001..."
cd backend
if [ -x "../.venv/bin/python" ]; then
    ../.venv/bin/python app.py &
else
    python app.py &
fi
BACKEND_PID=$!
cd ..

# Readiness: wait until backend reports HTTP 200
# Allow overrides via env if needed
: "${BACKEND_READY_URL:=http://localhost:5001/api/server-info}"
: "${READY_TIMEOUT_SEC:=30}"
print_status "Waiting for backend readiness at ${BACKEND_READY_URL} (timeout ${READY_TIMEOUT_SEC}s)..."
if ! wait_for_http_200 "${BACKEND_READY_URL}" "${READY_TIMEOUT_SEC}"; then
    print_error "Backend failed readiness check at ${BACKEND_READY_URL} within ${READY_TIMEOUT_SEC}s"
    exit 1
fi

# Check if backend is running
if ! ps -p $BACKEND_PID > /dev/null; then
    print_error "Backend server failed to start!"
    exit 1
fi
print_success "Backend server started successfully (PID: $BACKEND_PID)"

# Start frontend server
print_status "Starting frontend development server..."
cd frontend
npm run dev &
FRONTEND_PID=$!
cd ..

# Readiness: wait until frontend dev server responds with HTTP 200
: "${FRONTEND_READY_URL:=http://localhost:5173}"
print_status "Waiting for frontend readiness at ${FRONTEND_READY_URL} (timeout ${READY_TIMEOUT_SEC}s)..."
if ! wait_for_http_200 "${FRONTEND_READY_URL}" "${READY_TIMEOUT_SEC}"; then
    print_error "Frontend failed readiness check at ${FRONTEND_READY_URL} within ${READY_TIMEOUT_SEC}s"
    exit 1
fi

# Check if frontend is running
if ! ps -p $FRONTEND_PID > /dev/null; then
    print_error "Frontend server failed to start!"
    exit 1
fi
print_success "Frontend server started successfully (PID: $FRONTEND_PID)"

print_success "🐰 BHABIT CBMOONERS is now running!"
print_status "Backend API: http://localhost:5001"
print_status "Frontend App: http://localhost:5173"
print_status "Press Ctrl+C to stop both servers"

# Wait for user interrupt
wait
