#!/usr/bin/env bash
set -euo pipefail

pkill -f "wrangler pages dev" 2>/dev/null || true
pkill -f "wrangler dev" 2>/dev/null || true
pkill -f miniflare 2>/dev/null || true

for p in 8787 8788 8789; do
  lsof -ti tcp:$p | xargs -r kill -9 2>/dev/null || true
done
echo "[kill] cleaned wrangler/miniflare and freed :8787/:8789"
