#!/usr/bin/env bash
set -euo pipefail

# Run both UI check scripts from repo root in a single, repeatable runner
ROOT="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." && pwd )"
cd "$ROOT"

echo "--- RUNNING check_ui_layout.sh ---"
bash scripts/check_ui_layout.sh
echo

echo "--- RUNNING check_ui_wiring.sh ---"
bash scripts/check_ui_wiring.sh
echo

echo "[OK] UI checks complete."
