#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/frontend"
export BASE_URL="${BASE_URL:-http://127.0.0.1:5173}"
echo "[i] BASE_URL=$BASE_URL"
npm run smoke
