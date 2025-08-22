#!/usr/bin/env bash
set -euo pipefail

# From repo root
cd "$(dirname "$0")"

# Ensure the helper exists and is executable
if [[ ! -x "./scripts/restart_dev.sh" ]]; then
  echo "Making scripts/restart_dev.sh executable…"
  chmod +x ./scripts/restart_dev.sh
fi

# Restart frontend (Vite) and backend (Flask) dev processes
./scripts/restart_dev.sh