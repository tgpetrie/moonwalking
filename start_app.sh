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

# --- Robust port probing (lsof -> nc -> actual bind) ---
is_port_free() {
  local p="$1"
  if command -v lsof >/dev/null 2>&1; then
    # busy if any PID is listening
    if lsof -ti ":${p}" >/dev/null 2>&1; then
      return 1  # busy
    else
      return 0  # free
    fi
  elif command -v nc >/dev/null 2>&1; then
    # nc returns 0 if something accepts the connection (busy)
    if nc -z -w 1 127.0.0.1 "$p" >/dev/null 2>&1; then
      return 1  # busy
    else
      return 0  # free
    fi
  else
    # final sanity: try to bind with Python
    python3 - <<PY >/dev/null 2>&1
import socket, sys
s = socket.socket()
try:
    s.bind(("127.0.0.1", $p))
    s.close()
    sys.exit(0)  # free
except OSError:
    sys.exit(1)  # busy
PY
    return $?
  fi
}

pick_port() {
  local start="$1"
  local end="$2"
  for ((p=start; p<=end; p++)); do
    if is_port_free "$p"; then
      echo "$p"
      return 0
    fi
  done
  return 1
}

# Function to cleanup background processes on exit
cleanup() {
  print_status "Shutting down servers..."
  # concurrently handles its children; nothing to kill here
  print_success "Servers stopped."
}

# Set up cleanup trap
trap cleanup EXIT INT TERM

print_status "Starting BHABIT CBMOONERS Application..."

# Optional: kill default dev ports before starting
if [[ "$1" == "--clean" ]]; then
  print_status "Cleaning default ports :5001 and :5173..."
  lsof -ti :5001 | xargs kill -9 2>/dev/null || true
  lsof -ti :5173 | xargs kill -9 2>/dev/null || true
fi

# Check required commands
if ! command_exists python3; then
  print_error "Python 3 is not installed. Please install Python 3.13+ to continue."
  exit 1
fi

if ! command_exists npm; then
  print_error "Node.js/npm is not installed. Please install Node.js 22.17+ to continue."
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

print_status "Selecting ports..."
BACKEND_PORT=$(pick_port 5001 5010 || true)
FRONTEND_PORT=$(pick_port 5173 5183 || true)

if [[ -z "$BACKEND_PORT" || -z "$FRONTEND_PORT" ]]; then
  print_error "Could not find free ports for backend (5001-5010) or frontend (5173-5183)."
  exit 1
fi

API_BASE="http://localhost:${BACKEND_PORT}"
SOCKET_URL="ws://localhost:${BACKEND_PORT}"

# Final check in case port got occupied between probe and start
if ! is_port_free "$BACKEND_PORT"; then
  ALT=$(pick_port $((BACKEND_PORT+1)) 5010 || true)
  if [[ -n "$ALT" ]]; then
    print_warning "Port ${BACKEND_PORT} became busy; switching backend to :${ALT}"
    BACKEND_PORT="$ALT"
    API_BASE="http://localhost:${BACKEND_PORT}"
    SOCKET_URL="ws://localhost:${BACKEND_PORT}"
  else
    print_error "No free backend port available (5001–5010)."
    exit 1
  fi
fi

print_status "Backend API will target: ${API_BASE}"
print_status "WebSockets will target:  ${SOCKET_URL}"
print_status "Frontend dev server will run on http://localhost:${FRONTEND_PORT} (and call backend/WebSockets on :${BACKEND_PORT})"

print_status "Launching backend and frontend..."
npx concurrently \
  --kill-others \
  --names "backend,frontend" \
  --prefix-colors "magenta,cyan" \
  "cd backend && python3 app.py --port ${BACKEND_PORT}" \
  "cd frontend && VITE_API_URL=${API_BASE} VITE_WS_URL=${SOCKET_URL} npm run dev -- --port ${FRONTEND_PORT}"

