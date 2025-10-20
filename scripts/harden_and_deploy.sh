#!/usr/bin/env bash
set -euo pipefail

# Script to ensure _redirects contains SSE redirect, disable Pages Functions catch-all,
# build the frontend, and deploy Pages. Safe with literal [[path]] filename.

cd "$(dirname "$0")/.."
PWD=$(pwd)
echo "Working dir: $PWD"

echo "1) ensure frontend/public/_redirects contains SSE redirect"
mkdir -p frontend/public
REDIRECTS=frontend/public/_redirects
LINE='/api/events  https://moonwalking-worker.tgpetrie.workers.dev/api/events  200'
if ! ( [ -f "$REDIRECTS" ] && grep -Fxq "$LINE" "$REDIRECTS" ); then
  echo "$LINE" >> "$REDIRECTS"
  echo "Added SSE redirect to $REDIRECTS"
else
  echo "SSE redirect already present in $REDIRECTS"
fi

echo "_redirects preview (first 40 lines):"
head -n 40 "$REDIRECTS" || true

echo "\n2) disable Pages Functions catch-all if present"
# Use escaped filename to avoid shell globbing at invocation time
PATHFILE=frontend/functions/api/\[\[path\]\].js
if [ -f "$PATHFILE" ]; then
  mv "$PATHFILE" "$PATHFILE.bak"
  echo "Renamed $PATHFILE -> $PATHFILE.bak"
else
  echo "No catch-all Pages Function found or already disabled."
fi

echo "\n3) build frontend"
# Prefer clean install if lockfile present; run ci to use lockfile
if [ -f frontend/package-lock.json ] || [ -f frontend/yarn.lock ]; then
  npm --prefix frontend ci --silent || npm --prefix frontend install
else
  npm --prefix frontend install --silent
fi
npm --prefix frontend run build

echo "dist listing (first 200 lines):"
ls -la frontend/dist | sed -n '1,200p' || true

echo "\n4) deploy Pages"
# Deploy Pages using wrangler
npx wrangler@latest pages deploy frontend/dist --project-name moonwalking --commit-dirty=true

echo "Done."
