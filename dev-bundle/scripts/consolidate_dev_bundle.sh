#!/usr/bin/env bash
set -euo pipefail

# Consolidate a minimal dev bundle under ./dev-bundle
# It copies only the files/directories listed below. Run from repo root.

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT_DIR="$ROOT_DIR/dev-bundle"

echo "Creating dev bundle at: $OUT_DIR"
rm -rf "$OUT_DIR"
mkdir -p "$OUT_DIR"

# Backend files (minimal)
mkdir -p "$OUT_DIR/backend"
for f in app.py requirements.txt start.sh start_backend.sh stop_backend.sh logging_config.py utils.py; do
  if [[ -f "$ROOT_DIR/backend/$f" ]]; then
    cp "$ROOT_DIR/backend/$f" "$OUT_DIR/backend/"
    echo "copied backend/$f"
  fi
done

# Frontend: copy package.json, src, public, scripts (including our wrapper)
mkdir -p "$OUT_DIR/frontend"
for f in package.json index.html vite.config.js tsconfig.json tsconfig.node.json start.sh start_dev.sh; do
  if [[ -f "$ROOT_DIR/frontend/$f" ]]; then
    cp "$ROOT_DIR/frontend/$f" "$OUT_DIR/frontend/"
    echo "copied frontend/$f"
  fi
done

for d in src public scripts; do
  if [[ -d "$ROOT_DIR/frontend/$d" ]]; then
    cp -R "$ROOT_DIR/frontend/$d" "$OUT_DIR/frontend/"
    echo "copied frontend/$d/"
  fi
done

# Top-level scripts
mkdir -p "$OUT_DIR/scripts"
for f in restart_dev.sh smoke_test.sh consolidate_dev_bundle.sh; do
  if [[ -f "$ROOT_DIR/scripts/$f" ]]; then
    cp "$ROOT_DIR/scripts/$f" "$OUT_DIR/scripts/"
    echo "copied scripts/$f"
  fi
done

# VS Code helpers
mkdir -p "$OUT_DIR/.vscode"
for f in tasks.json keybindings.json settings.json; do
  if [[ -f "$ROOT_DIR/.vscode/$f" ]]; then
    cp "$ROOT_DIR/.vscode/$f" "$OUT_DIR/.vscode/"
    echo "copied .vscode/$f"
  fi
done

echo "Bundle created. Summary:"; echo
du -sh "$OUT_DIR" || true
ls -R "$OUT_DIR" | sed -n '1,200p'

echo
echo "To use the bundle locally:"
echo "  cd dev-bundle/frontend && npm install && npm run dev -- --strictPort --port 5173"
echo "  cd dev-bundle/backend && python app.py  # or use start.sh"
