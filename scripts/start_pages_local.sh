#!/usr/bin/env bash
set -euo pipefail
export BROWSER=none
# Serve the built frontend and wire the proxy functions from ./functions
wrangler pages dev frontend/dist \
  --show-interactive-dev-session=false \
  --live-reload=false \
  --log-level=warn \
  --port 8789 \
  --env-file .env.pages.local
