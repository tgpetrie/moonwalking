#!/bin/bash
# Build and test the entire project
set -e
cd ../../frontend && npm run build
cd ../backend && pytest
cd ../..
echo "Build and test complete."
