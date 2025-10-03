#!/usr/bin/env bash
set -euo pipefail

# Deploy wrapper: builds the SPA and deploys the frontend/dist to Cloudflare Pages.
# Usage: ./scripts/deploy_pages.sh [--no-install] [--no-build] [--commit-dirty=(true|false)] [--project-name NAME]
# Environment variables override flags: PROJECT_NAME, WRANGLER_BIN, PAGES_TOML

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FRONTEND_DIR="$ROOT_DIR/frontend"
DIST_DIR="$FRONTEND_DIR/dist"

# Defaults (can be overridden via env)
PROJECT_NAME="${PROJECT_NAME:-moonwalking}"
WRANGLER_BIN="${WRANGLER_BIN:-npx --yes wrangler@4.37.0}"
PAGES_TOML="${PAGES_TOML:-wrangler.toml}"
COMMIT_DIRTY="${COMMIT_DIRTY:-true}"

# CLI flags
NO_INSTALL=0
NO_BUILD=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --no-install) NO_INSTALL=1; shift ;;
    --no-build) NO_BUILD=1; shift ;;
    --commit-dirty=*) COMMIT_DIRTY="${1#*=}"; shift ;;
    --project-name) PROJECT_NAME="$2"; shift 2 ;;
    --wrangler) WRANGLER_BIN="$2"; shift 2 ;;
    --help|-h) echo "Usage: $0 [--no-install] [--no-build] [--commit-dirty=(true|false)] [--project-name NAME]"; exit 0 ;;
    *) echo "Unknown arg: $1" >&2; exit 2 ;;
  esac
done

echo "Deploy script: project=$PROJECT_NAME, wrangler=$WRANGLER_BIN, commit_dirty=$COMMIT_DIRTY"

echo "Building frontend in $FRONTEND_DIR..."
cd "$FRONTEND_DIR"

if [ "$NO_BUILD" -eq 1 ]; then
  echo "Skipping install/build as requested (--no-build)"
else
  if [ "$NO_INSTALL" -eq 0 ]; then
    # detect package manager / lockfile
    if [ -f package-lock.json ]; then
      echo "Detected package-lock.json → running npm ci"
      npm ci
    elif [ -f pnpm-lock.yaml ]; then
      echo "Detected pnpm lock → running pnpm install"
      pnpm install
    elif [ -f yarn.lock ]; then
      echo "Detected yarn.lock → running yarn install"
      yarn install --frozen-lockfile || yarn install
    else
      echo "No lockfile found → running npm install"
      npm install
    fi
  else
    echo "Skipping install as requested (--no-install)"
  fi

  echo "Running build"
  npm run build
fi

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

echo "Running: $WRANGLER_BIN pages deploy \"$DIST_DIR\" --project-name \"$PROJECT_NAME\" $COMMIT_FLAG"
eval "$WRANGLER_BIN pages deploy \"$DIST_DIR\" --project-name \"$PROJECT_NAME\" $COMMIT_FLAG"

echo "Deploy finished. Check Wrangler output for the Pages URL." 
