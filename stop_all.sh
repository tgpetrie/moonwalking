#!/usr/bin/env bash
set -euo pipefail

echo "[stop] stopping common dev processes"
pkill -f "python app.py --port" 2>/dev/null || true
pkill -f "vite" 2>/dev/null || true
pkill -f "wrangler.*dev" 2>/dev/null || true
pkill -f "wrangler.*pages" 2>/dev/null || true
echo "[stop] done."
