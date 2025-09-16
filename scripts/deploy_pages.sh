#!/usr/bin/env bash
set -euo pipefail

# Deploy wrapper: builds the SPA and deploys the frontend/dist to Cloudflare Pages.
# Usage: ./scripts/deploy_pages.sh
# Environment variables:
#  PROJECT_NAME (default: moonwalking)
#  WRANGLER_BIN (default: npx --yes wrangler@4.37.0)
#  PAGES_TOML (default: wrangler.pages.toml)
#  COMMIT_DIRTY (set to "false" to omit --commit-dirty flag)

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FRONTEND_DIR="$ROOT_DIR/frontend"
DIST_DIR="$FRONTEND_DIR/dist"

PROJECT_NAME="${PROJECT_NAME:-moonwalking}"
WRANGLER_BIN="${WRANGLER_BIN:-npx --yes wrangler@4.37.0}"
PAGES_TOML="${PAGES_TOML:-wrangler.pages.toml}"
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

# Use explicit directory to avoid toml parsing/version differences
eval "$WRANGLER_BIN pages deploy \"$DIST_DIR\" --project-name \"$PROJECT_NAME\" $COMMIT_FLAG --config \"$PAGES_TOML\""

echo "Deploy finished. Check Wrangler output for the Pages URL." 
