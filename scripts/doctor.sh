#!/usr/bin/env bash
set -euo pipefail
# non-destructive diagnostics to help find nested duplicate folders and confirm locations
echo "[doctor] pwd: $(pwd)"
echo "[doctor] top-level listing:"
ls -la | sed -n '1,200p'

# Check for nested backend/backend
if [ -d backend/backend ]; then
  echo "\n[doctor] Found nested backend/backend"
  echo "backend/:"
  ls -la backend | sed -n '1,200p'
  echo "backend/backend/:"
  ls -la backend/backend | sed -n '1,200p'
  echo "To merge nested files into the parent (non-destructive):"
  echo "  rsync -av backend/backend/ backend/"
  echo "After confirming the sync, remove the empty nested folder: rmdir backend/backend"
fi

# Check for nested frontend/frontend
if [ -d frontend/frontend ]; then
  echo "\n[doctor] Found nested frontend/frontend"
  echo "frontend/:"
  ls -la frontend | sed -n '1,200p'
  echo "frontend/frontend/:"
  ls -la frontend/frontend | sed -n '1,200p'
  echo "To merge nested files into the parent (non-destructive):"
  echo "  rsync -av frontend/frontend/ frontend/"
  echo "After confirming the sync, remove the empty nested folder: rmdir frontend/frontend"
fi

if [ ! -d backend/backend ] && [ ! -d frontend/frontend ]; then
  echo "\n[doctor] No obvious nested backend/backend or frontend/frontend directories found."
fi

echo "\n[doctor] No destructive actions taken. Use the rsync commands above if you confirm the contents."
