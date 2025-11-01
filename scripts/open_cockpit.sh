#!/usr/bin/env bash
set -euo pipefail

# Helper to open the repo in VS Code with the pinned 'cockpit' files
REPO_ROOT="${REPO_ROOT:-$HOME/Documents/moonwalkings}"

code "$REPO_ROOT" \
  docs/ai/AI_INDEX.md \
  frontend/src/components/Dashboard.jsx \
  frontend/src/components/GainersTable1Min.jsx \
  frontend/src/components/GainersTable3Min.jsx \
  frontend/src/components/LosersTable.jsx \
  frontend/src/components/SymbolInfoPanel.jsx \
  frontend/src/components/TopBannerScroll.jsx \
  frontend/src/components/VolumeBannerScroll.jsx

echo "Opened cockpit in VS Code. Pin the tabs once; workspace prevents preview replacement."
