#!/bin/bash
# Build Docker images for backend and frontend
set -e
docker-compose -f ../../docker-compose.yml build
echo "Docker images built."
