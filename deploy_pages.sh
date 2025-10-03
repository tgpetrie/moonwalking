#!/bin/bash
# Deploy moonwalking frontend to Cloudflare Pages
# This script builds locally and deploys to Pages (works without GitHub integration)

set -e

echo "🚀 Building and deploying moonwalking to Cloudflare Pages..."

# Navigate to frontend directory
cd "$(dirname "$0")/frontend"

# Clean build
echo "🧹 Cleaning old build..."
rm -rf node_modules/.vite dist

# Build with production environment variables
echo "📦 Building frontend..."
npm run build

# Copy _worker.js to dist
echo "📄 Adding _worker.js..."
cp ../_worker.js dist/

# Deploy to Cloudflare Pages
echo "☁️  Deploying to Cloudflare Pages..."

# Deploy to production branch (this will be your main deployment)
npx --yes wrangler@4.37.0 pages deploy dist \
  --project-name moonwalking \
  --branch=production \
  --commit-dirty=true

echo ""
echo "✅ Deployment complete!"
echo ""
echo "Production URL: https://production.moonwalking.pages.dev"
echo "Main domain: https://moonwalking.pages.dev (may take a few minutes to update)"
echo ""
echo "⚠️  Note: You may need to:"
echo "  1. Set 'production' as the production branch in Cloudflare Pages settings"
echo "  2. Purge Cloudflare cache for bhabit.net"
echo ""
