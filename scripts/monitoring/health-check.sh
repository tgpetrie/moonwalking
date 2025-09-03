#!/bin/bash
# Health check for backend and frontend
set -e
curl -f http://localhost:5000/health || exit 1
curl -f http://localhost:3000 || exit 1
echo "Health checks passed."
