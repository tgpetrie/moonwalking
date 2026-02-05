#!/usr/bin/env bash
set -euo pipefail

# Resolve repo root based on this script's location
ROOT="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." && pwd )"
cd "$ROOT"

echo "========================================"
echo " UI Wiring Check (components/hooks/styles)"
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

# 1) Hooks: useHybridLive existence / duplicates
section "Hooks: useHybridLive.* in frontend/src/hooks"

USE_HYBRID_COUNT=$(ls frontend/src/hooks/useHybridLive.* 2>/dev/null | wc -l | tr -d ' ')
if [ "$USE_HYBRID_COUNT" = "0" ]; then
  warn "No useHybridLive.* hook found in frontend/src/hooks (GainersTable3Min will fail to import)."
elif [ "$USE_HYBRID_COUNT" = "1" ]; then
  ok "Found exactly one useHybridLive hook:"
  ls -1 frontend/src/hooks/useHybridLive.* 2>/dev/null || true
else
  warn "Found multiple useHybridLive.* files (possible wiring fork):"
  ls -1 frontend/src/hooks/useHybridLive.* 2>/dev/null || true
fi

# 2) 1-minute table components: look for stray copies
section "Components: GainersTable1Min*.jsx in frontend/src/components"

GAINERS_1M_COUNT=$(ls frontend/src/components/GainersTable1Min*.jsx 2>/dev/null | wc -l | tr -d ' ')
if [ "$GAINERS_1M_COUNT" = "0" ]; then
  warn "No GainersTable1Min*.jsx files found – 1m board will be missing."
elif [ "$GAINERS_1M_COUNT" -le 2 ]; then
  ok "GainersTable1Min set looks sane (<=2 files, e.g. main + .clean):"
  ls -1 frontend/src/components/GainersTable1Min*.jsx 2>/dev/null || true
else
  warn "More than 2 GainersTable1Min*.jsx files found (check for old/copy variants):"
  ls -1 frontend/src/components/GainersTable1Min*.jsx 2>/dev/null || true
fi

# 3) TokenRow variants – surface any suspicious *_old / *copy
section "Components: TokenRow* variants"

if ls frontend/src/components/TokenRow*.jsx >/dev/null 2>&1; then
  ls -1 frontend/src/components/TokenRow*.jsx
  # flag anything that looks like an accidental duplicate
  SUSPECT=$(ls frontend/src/components/TokenRow*.jsx 2>/dev/null | grep -Ei 'old|copy|bak' || true)
  if [ -n "$SUSPECT" ]; then
    warn "Suspicious TokenRow variants (old/copy/bak):"
    echo "$SUSPECT"
  else
    ok "No obviously duplicated TokenRow* (old/copy/bak) variants."
  fi
else
  warn "No TokenRow*.jsx files found – that would be very odd."
fi

# 4) 1m grid style definitions – check not obviously duplicated
section "Styles: .bh-1m-grid definitions in frontend/src/index.css"

if [ -f frontend/src/index.css ]; then
  # Count only style block definitions (lines starting with selector), not all mentions
  DEFS=$(grep -c "^\s*\.bh-1m-grid" frontend/src/index.css 2>/dev/null || echo 0)
  TOTAL=$(grep -c ".bh-1m-grid" frontend/src/index.css 2>/dev/null || echo 0)

  if [ "$TOTAL" -eq 0 ]; then
    warn "No .bh-1m-grid occurrences in index.css (1m grid styles might be missing)."
  else
    ok "Found $TOTAL mentions of .bh-1m-grid ($DEFS style blocks) in index.css."
    # Legitimate layered styling: base + media queries + variants + overrides = 8-12 is normal
    if [ "$TOTAL" -gt 15 ]; then
      warn "$TOTAL occurrences of .bh-1m-grid seems high – check for duplicated style blocks."
    fi
  fi
else
  warn "frontend/src/index.css not found – cannot verify .bh-1m-grid styles."
fi

# 5) Quick reminder of git status (to see what’s dirty)
section "Git status (summary)"

git status --short || warn "git status failed (are we in a git repo?)"

echo
echo "========================================"
echo " UI Wiring Check complete."
echo " If you see only [OK] lines, wiring is probably clean."
echo "========================================"
