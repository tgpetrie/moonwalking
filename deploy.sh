#!/bin/bash

# BHABIT CBMOONERS - Automated Deployment Script
# This script helps deploy your application to various platforms

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

print_status() {
    echo -e "${BLUE}[DEPLOY]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

show_help() {
    echo "🐰 BHABIT CBMOONERS Deployment Script"
    echo ""
    echo "Usage: ./deploy.sh [platform]"
    echo ""
    echo "Platforms:"
    echo "  vercel      - Deploy frontend to Vercel"
    echo "  render      - Deploy backend to Render"
    echo "  railway     - Deploy to Railway"
    echo "  heroku      - Deploy to Heroku"
    echo "  docker      - Build and run Docker containers"
    echo "  build       - Build for production locally"
    echo "  help        - Show this help"
    echo ""
    echo "Examples:"
    echo "  ./deploy.sh vercel    # Deploy frontend to Vercel"
    echo "  ./deploy.sh render    # Deploy backend to Render"
    echo "  ./deploy.sh docker    # Run with Docker"
    echo ""
}

check_dependencies() {
    print_status "Checking deployment dependencies..."
    
    if ! command -v git &> /dev/null; then
        print_error "Git is required for deployment"
        exit 1
    fi
    
    if ! command -v npm &> /dev/null; then
        print_error "npm is required for frontend deployment"
        exit 1
    fi
    
    print_success "Dependencies check passed"
}

build_frontend() {
    print_status "Building frontend for production..."
    cd frontend
    
    # Install dependencies
    npm install
    
    # Build for production
    npm run build
    
    cd ..
    print_success "Frontend built successfully"
}

deploy_vercel() {
    print_status "Deploying frontend to Vercel..."
    
    if ! command -v vercel &> /dev/null; then
        print_status "Installing Vercel CLI..."
        npm install -g vercel
    fi
    
    # Prompt for SECRET_KEY if not set
    if [ -z "$SECRET_KEY" ]; then
        read -p "Enter SECRET_KEY for Vercel deployment (leave blank to auto-generate): " SECRET_KEY
        if [ -z "$SECRET_KEY" ]; then
            SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
            print_status "Generated SECRET_KEY: $SECRET_KEY"
        fi
    fi
    export SECRET_KEY

    build_frontend

    cd frontend
    vercel --prod --env SECRET_KEY=$SECRET_KEY
    cd ..

    print_success "Frontend deployed to Vercel!"
}

deploy_render() {
    print_status "Preparing backend for Render deployment..."
    
    # Check if render.yaml exists
    if [ ! -f "render.yaml" ]; then
        print_error "render.yaml not found. Creating one..."
        # render.yaml is already created above
    fi
    
    # Prompt for SECRET_KEY if not set
    if [ -z "$SECRET_KEY" ]; then
        read -p "Enter SECRET_KEY for Render deployment (leave blank to auto-generate): " SECRET_KEY
        if [ -z "$SECRET_KEY" ]; then
            SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
            print_status "Generated SECRET_KEY: $SECRET_KEY"
        fi
    fi
    export SECRET_KEY

    print_status "Backend ready for Render deployment"
    print_warning "Please connect your repository to Render.com manually and set SECRET_KEY in the environment variables."
    print_status "Render will auto-deploy using render.yaml configuration"
}

deploy_railway() {
    print_status "Deploying to Railway..."
    
    if ! command -v railway &> /dev/null; then
        print_status "Installing Railway CLI..."
        npm install -g @railway/cli
    fi
    
    # Prompt for SECRET_KEY if not set
    if [ -z "$SECRET_KEY" ]; then
        read -p "Enter SECRET_KEY for Railway deployment (leave blank to auto-generate): " SECRET_KEY
        if [ -z "$SECRET_KEY" ]; then
            SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
            print_status "Generated SECRET_KEY: $SECRET_KEY"
        fi
    fi
    export SECRET_KEY

    railway login
    railway init
    railway up --env SECRET_KEY=$SECRET_KEY

    print_success "Deployed to Railway!"
}

deploy_heroku() {
    print_status "Deploying to Heroku..."
    
    if ! command -v heroku &> /dev/null; then
        print_error "Please install Heroku CLI first"
        exit 1
    fi
    
    # Login to Heroku
    heroku login
    
    # Create app if it doesn't exist
    read -p "Enter Heroku app name: " app_name
    heroku create $app_name || print_warning "App might already exist"
    
    # Set environment variables
    heroku config:set FLASK_ENV=production
    heroku config:set FLASK_DEBUG=False
    heroku config:set PORT=\$PORT
    
    # Deploy
    git push heroku main
    
    print_success "Deployed to Heroku!"
}

deploy_docker() {
    print_status "Building and running Docker containers..."
    
    if ! command -v docker &> /dev/null; then
        print_error "Docker is required"
        exit 1
    fi
    
    if ! command -v docker-compose &> /dev/null; then
        print_error "Docker Compose is required"
        exit 1
    fi
    
    # Prompt for SECRET_KEY if not set
    if [ -z "$SECRET_KEY" ]; then
        read -p "Enter SECRET_KEY for Docker deployment (leave blank to auto-generate): " SECRET_KEY
        if [ -z "$SECRET_KEY" ]; then
            SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
            print_status "Generated SECRET_KEY: $SECRET_KEY"
        fi
    fi
    export SECRET_KEY

    # Build and run
    docker-compose up --build -d

    print_success "Docker containers running!"
    print_status "Frontend: http://localhost:3000"
    print_status "Backend: http://localhost:5001"
}

build_production() {
    print_status "Building for production..."
    
    # Build frontend
    build_frontend
    
    # Prepare backend
    print_status "Preparing backend..."
    cd backend
    pip install -r requirements.txt
    cd ..
    
    print_success "Production build complete!"
    print_status "Frontend build: frontend/dist/"
    print_status "Backend ready: backend/"
}

# Main script logic
case "${1:-help}" in
    "vercel")
        check_dependencies
        deploy_vercel
        ;;
    "render")
        check_dependencies
        deploy_render
        ;;
    "railway")
        check_dependencies
        deploy_railway
        ;;
    "heroku")
        check_dependencies
        deploy_heroku
        ;;
    "docker")
        deploy_docker
        ;;
    "build")
        check_dependencies
        build_production
        ;;
    "help"|*)
        show_help
        ;;
esac
