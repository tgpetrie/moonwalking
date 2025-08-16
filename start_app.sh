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

## Start services either in foreground (tmux / macOS Terminal) or fallback to background+tail
print_status "Preparing log files..."
# Truncate previous logs so tail shows fresh output
: > backend.log
: > frontend.log

# Determine foreground mode: prefer tmux, then macOS Terminal.app, else fallback
MODE="fallback"
if command_exists tmux; then
  MODE="tmux"
elif [[ "$(uname)" == "Darwin" ]] && command_exists osascript; then
  MODE="mac_terminal"
fi

# Allow overriding via --foreground flag
if [ "$1" == "--foreground" ]; then
  if command_exists tmux; then
    MODE="tmux"
  elif [[ "$(uname)" == "Darwin" ]] && command_exists osascript; then
    MODE="mac_terminal"
  else
    MODE="fallback"
  fi
fi

if [ "$MODE" = "tmux" ]; then
  SESSION="bhabit"
  print_status "Starting services inside tmux session: $SESSION"
  # Kill existing session to ensure a clean start
  if tmux has-session -t "$SESSION" 2>/dev/null; then
    tmux kill-session -t "$SESSION"
  fi

  # Start backend and frontend in separate panes
  tmux new-session -d -s "$SESSION" -n backend "cd '$(pwd)/backend' && python3 app.py"
  tmux split-window -h -t "$SESSION" "cd '$(pwd)/frontend' && npm run dev"
  tmux select-layout -t "$SESSION" tiled

  print_success "Tmux session created. Attaching to $SESSION (Ctrl+B D to detach)."
  tmux attach -t "$SESSION"
  exit 0
elif [ "$MODE" = "mac_terminal" ]; then
  print_status "Opening separate Terminal windows for backend and frontend (macOS)."
  # Backend window
  osascript -e 'tell application "Terminal" to do script "cd \"'"$(pwd)/backend"\"; python3 app.py"'
  # Frontend window
  osascript -e 'tell application "Terminal" to do script "cd \"'"$(pwd)/frontend"\"; npm run dev"'

  print_success "Terminal windows opened. You should see each service running in its own window."
  print_status "Streaming combined logs here as well (press Ctrl+C to stop):"
  tail -f backend.log frontend.log
  exit 0
else
  # Fallback: previous behavior (background + logs)
  print_status "Starting backend server on http://localhost:5001 (logs -> backend.log)..."
  cd backend
  # use python3 (we checked earlier) and redirect stdout/stderr to a log file
  python3 app.py > ../backend.log 2>&1 &
  BACKEND_PID=$!
  cd ..

  # Wait a moment for backend to start
  sleep 3

  if ! ps -p $BACKEND_PID > /dev/null; then
    print_error "Backend server failed to start! See backend.log for details."
    tail -n +1 backend.log || true
    exit 1
  fi
  print_success "Backend server started successfully (PID: $BACKEND_PID)"

  print_status "Starting frontend development server (logs -> frontend.log)..."
  cd frontend
  # run npm in non-interactive mode and capture output
  npm run dev > ../frontend.log 2>&1 &
  FRONTEND_PID=$!
  cd ..

  # Wait a moment for frontend to start
  sleep 3

  if ! ps -p $FRONTEND_PID > /dev/null; then
    print_error "Frontend server failed to start! See frontend.log for details."
    tail -n +1 frontend.log || true
    exit 1
  fi
  print_success "Frontend server started successfully (PID: $FRONTEND_PID)"

  print_success "🐰 BHABIT CBMOONERS is now running!"
  print_status "Backend API: http://localhost:5001"
  print_status "Frontend App: http://localhost:5173"
  print_status "Press Ctrl+C to stop both servers"

  print_status "Streaming backend and frontend logs (press Ctrl+C to stop):"

  # Stream both logs in the foreground so the user sees live output.
  # When the user presses Ctrl+C this tail will exit and the trap will run cleanup().
  tail -f backend.log frontend.log

  # If tail exits for any reason, wait for background processes to exit as well
  wait
fi
