#!/usr/bin/env bash
set -euo pipefail

# Deploy wrapper: builds the SPA and deploys the frontend/dist to Cloudflare Pages.
# Usage: ./scripts/deploy_pages.sh
# Environment variables:
#  PROJECT_NAME (default: moonwalking)
#  WRANGLER_BIN (default: npx --yes wrangler@4.37.0)
#  PAGES_TOML (default: wrangler.toml – Pages CLI requires the default path)
#  COMMIT_DIRTY (set to "false" to omit --commit-dirty flag)

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FRONTEND_DIR="$ROOT_DIR/frontend"
DIST_DIR="$FRONTEND_DIR/dist"

PROJECT_NAME="${PROJECT_NAME:-moonwalking}"
WRANGLER_BIN="${WRANGLER_BIN:-npx --yes wrangler@4.37.0}"
# Wrangler's Pages CLI ignores custom --config paths, so we rely on the
# standard wrangler.toml at the repo root. Allow callers to opt out, but default
# to the conventional location.
PAGES_TOML="${PAGES_TOML:-wrangler.toml}"
COMMIT_DIRTY="${COMMIT_DIRTY:-true}"

echo "Building frontend in $FRONTEND_DIR..."
cd "$FRONTEND_DIR"
npm ci
npm run build

if [ ! -d "$DIST_DIR" ]; then
  echo "Error: build output not found at $DIST_DIR" >&2
  exit 1
fi

cd "$ROOT_DIR"
echo "Deploying $DIST_DIR to Cloudflare Pages (project: $PROJECT_NAME)..."

COMMIT_FLAG=""
if [ "$COMMIT_DIRTY" = "true" ]; then
  COMMIT_FLAG="--commit-dirty=true"
fi

# Pages does not support custom config paths; ensure we call it from the repo
# root so the default wrangler.toml is discovered automatically.
if [ "$PAGES_TOML" != "wrangler.toml" ]; then
  echo "[deploy_pages] Warning: Pages CLI ignores custom config paths. Set PAGES_TOML=wrangler.toml or copy your config to wrangler.toml." >&2
fi

eval "$WRANGLER_BIN pages deploy \"$DIST_DIR\" --project-name \"$PROJECT_NAME\" $COMMIT_FLAG"

echo "Deploy finished. Check Wrangler output for the Pages URL." 
