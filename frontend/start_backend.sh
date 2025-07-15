#!/bin/bash

# Script to start the backend server for BHABIT CB4 frontend

echo "🚀 Starting BHABIT CB4 Backend Server..."
echo "📍 Looking for backend server..."

# Check if backend exists in parent directory
if [ -f "../backend/app.py" ]; then
    echo "✅ Found backend in ../backend/"
    cd ../backend
    python app.py
elif [ -f "../../backend/app.py" ]; then
    echo "✅ Found backend in ../../backend/"
    cd ../../backend
    python app.py
else
    echo "❌ Backend server not found!"
    echo "Please make sure the backend directory with app.py exists"
    echo "Expected locations:"
    echo "  - ../backend/app.py"
    echo "  - ../../backend/app.py"
    echo ""
    echo "📄 The frontend is currently running with fallback demo data"
    echo "🌐 Frontend is available at: http://localhost:5173"
    echo "🔌 Backend should run on: http://localhost:5001"
    exit 1
fi
