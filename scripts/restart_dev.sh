#!/usr/bin/env bash
set -euo pipefail

echo "🔄 Restarting development servers..."

# Kill existing processes
echo "Stopping existing processes..."
pkill -f "python.*app.py" || true
pkill -f "vite" || true
pkill -f "npm.*dev" || true

# Wait a moment for processes to stop
sleep 2

# Start backend (Flask)
echo "Starting backend..."
cd backend
python3 app.py &
BACKEND_PID=$!
echo "Backend started with PID $BACKEND_PID"

# Start frontend (Vite)
echo "Starting frontend..."
cd ../frontend
npm run dev &
FRONTEND_PID=$!
echo "Frontend started with PID $FRONTEND_PID"

# Go back to root
cd ..

echo "✅ Development servers started!"
echo "Backend PID: $BACKEND_PID"
echo "Frontend PID: $FRONTEND_PID"
echo ""
echo "Frontend: http://localhost:5173"
echo "Backend: http://localhost:5000"
echo ""
echo "Press Ctrl+C to stop both servers"

# Wait for either process to exit
wait