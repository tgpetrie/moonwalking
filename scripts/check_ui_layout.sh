#!/usr/bin/env bash
set -euo pipefail

ROOT="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." && pwd )"
cd "$ROOT"

echo "========================================"
echo " UI Layout Invariants Check (1m / 3m / WL)"
echo " Repo: $ROOT"
echo "========================================"
echo
section() {
  echo
  echo "---- $1 ----"
}

ok() {
  echo "[OK]   $1"
}

warn() {
  echo "[WARN] $1"
}

# 1) 1-minute gainers layout invariants
GT1M="frontend/src/components/GainersTable1Min.jsx"
section "GainersTable1Min.jsx layout invariants"

if [ ! -f "$GT1M" ]; then
  warn "$GT1M not found – cannot verify 1m layout."
else
  if grep -q "bh-1m-grid" "$GT1M"; then
    ok "GainersTable1Min uses .bh-1m-grid classes."
  else
    warn "GainersTable1Min does NOT reference .bh-1m-grid – 1m layout may be off."
  fi

  if grep -q "MAX_ROWS_PER_COLUMN" "$GT1M"; then
    ok "GainersTable1Min declares MAX_ROWS_PER_COLUMN (4-slot rule present)."
  else
    warn "MAX_ROWS_PER_COLUMN not found in GainersTable1Min – 4-slot logic might be missing."
  fi

  if grep -q "rows.map" "$GT1M"; then
    warn "Found 'rows.map' in GainersTable1Min – this may be the old single-column mapping; verify chunking logic."
  else
    ok "No raw 'rows.map' in GainersTable1Min – likely using chunked 4+4 layout."
  fi
fi

# 2) 3-minute gainers wiring to useHybridLive
GT3M="frontend/src/components/GainersTable3Min.jsx"
section "GainersTable3Min.jsx wiring to useHybridLive"

if [ ! -f "$GT3M" ]; then
  warn "$GT3M not found – cannot verify 3m layout wiring."
else
  if grep -q "useHybridLive" "$GT3M"; then
    ok "GainersTable3Min references useHybridLive hook."
  else
    warn "GainersTable3Min does NOT reference useHybridLive – expected hybrid data hook missing."
  fi

  if grep -q "../hooks/useHybridLive" "$GT3M"; then
    ok "GainersTable3Min imports useHybridLive from ../hooks/useHybridLive."
  else
    warn "Import for useHybridLive from ../hooks/useHybridLive not found – check import path."
  fi
fi

# 3) Watchlist panel context wiring
WLP="frontend/src/components/WatchlistPanel.jsx"
section "WatchlistPanel.jsx wiring to WatchlistContext"

if [ ! -f "$WLP" ]; then
  warn "$WLP not found – cannot verify watchlist wiring."
else
  if grep -q "WatchlistContext" "$WLP"; then
    ok "WatchlistPanel references WatchlistContext."
  else
    warn "WatchlistPanel does not reference WatchlistContext – check context wiring."
  fi

  if grep -q "useContext" "$WLP" || grep -q "useWatchlistContext" "$WLP"; then
    ok "WatchlistPanel appears to use React context for state."
  else
    warn "No obvious context usage in WatchlistPanel – verify that it still reads from context, not local state."
  fi
fi

echo
echo "========================================"
echo " UI Layout Invariants Check complete."
echo " Fix any [WARN] results before chasing visual ghosts."
echo "========================================"
