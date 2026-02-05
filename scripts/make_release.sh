#!/usr/bin/env bash
set -euo pipefail
PROJECT_NAME="${PROJECT_NAME:-moonwalkings}"
STAMP="$(date +%Y-%m-%d-%H%M%S)"
OUTDIR="dist/release_${STAMP}"
mkdir -p "$OUTDIR"

# build frontend
( cd frontend && npm ci || npm i; npm run build )

# copy minimal runtime files
RUNTIME=".release_stage"
rm -rf "$RUNTIME"; mkdir -p "$RUNTIME"
rsync -a --exclude '.git' --exclude 'node_modules' ./ "$RUNTIME/"
mkdir -p "$RUNTIME/frontend"
rm -rf "$RUNTIME/frontend/dist"
cp -a frontend/dist "$RUNTIME/frontend/dist"

zip -qr9 "$OUTDIR/${PROJECT_NAME}_release_${STAMP}.zip" "$RUNTIME"/*
rm -rf "$RUNTIME"

echo "✅ Release zip → $OUTDIR"
ls -lh "$OUTDIR" | sed '1d'
