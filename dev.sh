#!/bin/bash

# BHABIT CBMOONERS - Development Utility Script
# Provides common development tasks

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[DEV]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

show_help() {
    echo "🐰 BHABIT CBMOONERS Development Utility"
    echo ""
    echo "Usage: ./dev.sh [command]"
    echo ""
    echo "Commands:"
    echo "  setup        - Run full development environment setup"
    echo "  start        - Start both backend and frontend servers"
    echo "  backend      - Start only the backend server"
    echo "  frontend     - Start only the frontend server"
    echo "  test         - Run all backend tests (pytest)"
    echo "  smoke        - Run backend smoke test against a base URL"
    echo "  test-backend - Run backend tests only"
    echo "  build        - Build frontend for production"
    echo "  clean        - Clean build artifacts and caches"
    echo "  install      - Install/update dependencies"
    echo "  health       - Check application health"
    echo "  logs         - Show backend logs"
    echo "  diagnose     - Diagnose and fix data display issues"
    echo "  deploy       - Show deployment options"
    echo "  help         - Show this help message"
    echo ""
    echo "Examples:"
    echo "  ./dev.sh setup        # First time setup"
    echo "  ./dev.sh start        # Start development servers"
    echo "  ./dev.sh diagnose     # Fix frontend data issues"
    echo "  ./dev.sh deploy       # View deployment options"
    echo "  ./dev.sh test         # Run tests"
    echo ""
}

activate_venv() {
    if [ -d ".venv" ]; then
        source .venv/bin/activate
    else
        print_error "Virtual environment not found. Run './dev.sh setup' first."
        exit 1
    fi
}

case "${1:-help}" in
    "setup")
        print_status "Running development environment setup..."
        ./setup_dev.sh
        ;;
    
    "start")
        print_status "Starting BHABIT CBMOONERS..."
        ./start_app.sh
        ;;
    
    "backend")
        print_status "Starting backend server only..."
        activate_venv
        cd backend
        python app.py
        ;;
    
    "frontend")
        print_status "Starting frontend server only..."
        cd frontend
        npm run dev
        ;;
    
        "test")
        print_status "Running all tests..."
        activate_venv
        cd backend
                python -m pytest -q || print_error "Backend tests failed"
        cd ../frontend
        if [ -f "package.json" ] && grep -q "test" package.json; then
            npm test
        else
            print_status "No frontend tests configured."
        fi
        cd ..
        ;;
    
        "smoke")
                print_status "Running backend smoke test..."
                activate_venv
                BASE_URL=${2:-"http://127.0.0.1:5001"}
                SMOKE_START_DELAY=${SMOKE_START_DELAY:-0}
                SMOKE_BASE_URL="$BASE_URL" SMOKE_START_DELAY="$SMOKE_START_DELAY" \
                    python backend/smoke_test.py
                ;;
    
    "test-backend")
        print_status "Running backend tests..."
        activate_venv
        cd backend
        if [ -f "test_app.py" ]; then
            python -m pytest test_app.py -v
        else
            print_error "Backend tests not found!"
        fi
        cd ..
        ;;
    
    "build")
        print_status "Building frontend for production..."
        cd frontend
        npm run build
        print_success "Frontend built successfully!"
        cd ..
        ;;
    
    "clean")
        print_status "Cleaning build artifacts and caches..."
        # Clean frontend
        if [ -d "frontend/dist" ]; then
            rm -rf frontend/dist
            print_status "Removed frontend/dist"
        fi
        if [ -d "frontend/node_modules/.cache" ]; then
            rm -rf frontend/node_modules/.cache
            print_status "Removed frontend cache"
        fi
        # Clean backend
        if [ -d "backend/__pycache__" ]; then
            rm -rf backend/__pycache__
            print_status "Removed backend/__pycache__"
        fi
        if [ -d "backend/.pytest_cache" ]; then
            rm -rf backend/.pytest_cache
            print_status "Removed backend/.pytest_cache"
        fi
        print_success "Cleanup completed!"
        ;;
    
    "install")
        print_status "Installing/updating dependencies..."
        activate_venv
        cd backend
        pip install --upgrade pip
        pip install -r requirements.txt
        cd ../frontend
        npm install
        cd ..
        print_success "Dependencies updated!"
        ;;
    
    "health")
        print_status "Checking application health..."
        
        # Check if virtual environment exists
        if [ -d ".venv" ]; then
            print_success "Virtual environment: OK"
        else
            print_error "Virtual environment: Missing"
        fi
        
        # Check backend dependencies
        activate_venv
        cd backend
        if pip check >/dev/null 2>&1; then
            print_success "Backend dependencies: OK"
        else
            print_error "Backend dependencies: Issues found"
        fi
        cd ..
        
        # Check frontend dependencies
        cd frontend
        if [ -d "node_modules" ]; then
            print_success "Frontend dependencies: OK"
        else
            print_error "Frontend dependencies: Missing"
        fi
        cd ..
        
        # Check if ports are available
        if ! lsof -i :5001 >/dev/null 2>&1; then
            print_success "Port 5001 (backend): Available"
        else
            print_error "Port 5001 (backend): In use"
        fi
        
        if ! lsof -i :5173 >/dev/null 2>&1; then
            print_success "Port 5173 (frontend): Available"
        else
            print_error "Port 5173 (frontend): In use"
        fi
        ;;
    
    "logs")
        print_status "Showing backend logs..."
        if [ -f "backend/logs/app.log" ]; then
            tail -f backend/logs/app.log
        elif [ -f "backend/app.log" ]; then
            tail -f backend/app.log
        else
            print_error "No log files found. Start the backend server to generate logs."
        fi
        ;;
    
    "diagnose")
        print_status "Running comprehensive diagnostic for frontend data issues..."
        ./diagnose_and_fix.sh
        ;;
    
    "deploy")
        print_status "Deployment options for BHABIT CBMOONERS..."
        echo ""
        echo "🚀 Quick Deployment Commands:"
        echo ""
        echo "Frontend (Vercel):"
        echo "  ./deploy.sh vercel"
        echo ""
        echo "Backend (Render):"
        echo "  ./deploy.sh render"
        echo ""
        echo "Full Stack (Docker):"
        echo "  ./deploy.sh docker"
        echo ""
        echo "Other platforms:"
        echo "  ./deploy.sh railway    # Railway deployment"
        echo "  ./deploy.sh heroku     # Heroku deployment"
        echo "  ./deploy.sh build      # Build for production"
        echo ""
        echo "For detailed instructions, see the Deployment section in README.md"
        ;;
    
    "help"|*)
        show_help
        ;;
esac
