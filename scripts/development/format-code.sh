#!/bin/bash
# Format code for backend and frontend
set -e
cd ../../backend && black .
cd ../frontend && npm run format
cd ../..
echo "Code formatted."
