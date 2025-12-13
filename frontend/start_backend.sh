#!/bin/bash

# Script to start the backend server for BHABIT CB4 frontend

echo "🚀 Starting BHABIT CB4 Backend Server..."
# Resolve script directory so this script can be run from any cwd
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo "📍 Looking for backend server (script dir: $SCRIPT_DIR)"

# Check common candidate locations relative to the script directory
if [ -f "$SCRIPT_DIR/../backend/app.py" ]; then
    echo "✅ Found backend in $SCRIPT_DIR/../backend/"
    cd "$SCRIPT_DIR/../backend"
    # Prefer a venv located inside the backend folder, then try the repo-root venv,
    # otherwise fall back to the system python.
    if [ -x "./.venv/bin/python" ]; then
        ./.venv/bin/python app.py
    elif [ -x "../.venv/bin/python" ]; then
        ../.venv/bin/python app.py
    else
        python app.py
    fi
elif [ -f "$SCRIPT_DIR/../../backend/app.py" ]; then
    echo "✅ Found backend in $SCRIPT_DIR/../../backend/"
    cd "$SCRIPT_DIR/../../backend"
    # Prefer a venv located inside the backend folder, then try the repo-root venv,
    # otherwise fall back to the system python.
    if [ -x "./.venv/bin/python" ]; then
        ./.venv/bin/python app.py
    elif [ -x "../../.venv/bin/python" ]; then
        ../../.venv/bin/python app.py
    else
        python app.py
    fi
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
