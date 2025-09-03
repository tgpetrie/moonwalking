#!/bin/bash
# Install all project dependencies
set -e
cd ../../backend && pip install -r requirements.txt
cd ../frontend && npm install
cd ../..
echo "Dependencies installed."
