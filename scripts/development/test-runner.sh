#!/bin/bash
# Run all tests for backend and frontend
set -e
cd ../../backend && pytest
cd ../frontend && npm test
cd ../..
echo "Tests completed."
