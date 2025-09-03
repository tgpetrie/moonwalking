#!/bin/bash
# Run basic security audit for backend and frontend
set -e
cd ../../backend && pip install safety && safety check
cd ../frontend && npm audit
cd ../..
echo "Security audit complete."
