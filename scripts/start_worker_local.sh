#!/usr/bin/env bash
set -euo pipefail
export BROWSER=none
wrangler dev -c wrangler.worker.toml \
  --local \
  --port 8787 \
  --show-interactive-dev-session=false \
  --log-level=warn

