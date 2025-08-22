#!/usr/bin/env bash
set -euo pipefail

echo "🚀 Starting BHABIT CBMOONERS Development Environment"
echo "=================================================="

# From repo root
cd "$(dirname "$0")"

# Kill any existing processes
echo "🔄 Cleaning up existing processes..."
pkill -f "python.*app.py" || true
pkill -f "vite" || true  
pkill -f "npm.*dev" || true
sleep 2

# Check directories exist
if [[ ! -d "backend" ]]; then
    echo "❌ Backend directory not found"
    exit 1
fi

if [[ ! -d "frontend" ]]; then
    echo "❌ Frontend directory not found"
    exit 1
fi

# Start Backend
echo "🐍 Starting Backend (Flask)..."
cd backend
python3 app.py &
BACKEND_PID=$!
echo "   ✅ Backend running on http://127.0.0.1:5000 (PID: $BACKEND_PID)"

# Start Frontend  
echo "⚛️  Starting Frontend (Vite)..."
cd ../frontend
npm run dev -- --port 5173 &
FRONTEND_PID=$!
echo "   ✅ Frontend running on http://127.0.0.1:5173 (PID: $FRONTEND_PID)"

cd ..

echo ""
echo "🎉 Development servers started successfully!"
echo "=================================================="
echo "🌐 Frontend: http://localhost:5173"
echo "🔧 Backend:  http://localhost:5000"
echo "🩺 Health:   http://localhost:5000/api/health"
echo ""
echo "💡 Press Ctrl+C to stop both servers"
echo ""

# Function to cleanup on exit
cleanup() {
    echo ""
    echo "🛑 Shutting down servers..."
    kill $BACKEND_PID $FRONTEND_PID 2>/dev/null || true
    pkill -f "python.*app.py" || true
    pkill -f "vite" || true
    echo "✅ Cleanup complete"
    exit 0
}

# Set up signal handlers
trap cleanup SIGINT SIGTERM

# Wait for both processes
wait