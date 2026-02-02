#!/usr/bin/env bash
set -euo pipefail

fail() { echo "FAIL: $*" >&2; exit 1; }
ok() { echo "OK: $*"; }

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

CSS="frontend/src/index.css"

test -f "$CSS" || fail "missing $CSS"
if [ -f "frontend/index.css" ]; then
  fail "frontend/index.css should not exist; use frontend/src/index.css"
fi

# Banners must use these classes
grep -R --line-number "bh-banner-track" frontend/src >/dev/null || fail "banners must use .bh-banner-track"
grep -R --line-number "bh-banner-chip" frontend/src >/dev/null || fail "banners must use .bh-banner-chip"

# Banner marquee loop class must exist
grep -R --line-number "bh-banner-track--loop" frontend/src >/dev/null || fail "banners must use .bh-banner-track--loop"

# Typography hierarchy contract must exist
grep -n "\.bh-pct" "$CSS" >/dev/null || fail "missing .bh-pct"
grep -n "\.bh-price-current" "$CSS" >/dev/null || fail "missing .bh-price-current"
grep -n "\.bh-price-prev" "$CSS" >/dev/null || fail "missing .bh-price-prev"

# Global color tokens must exist
grep -n "\-\-bh-white" "$CSS" >/dev/null || fail "missing --bh-white"
grep -n "\-\-bh-mint" "$CSS" >/dev/null || fail "missing --bh-mint"

# Permanent rail must be bottom-based
grep -n "\.bh-row::after" "$CSS" >/dev/null || fail "missing .bh-row::after (permanent rail)"
grep -n "bottom: 0" "$CSS" >/dev/null || fail "rail must be positioned at bottom: 0"

# Canonical grid must exist
grep -n "\-\-bh-cols" "$CSS" >/dev/null || fail "missing --bh-cols"
grep -R --line-number "bh-row-grid" frontend/src >/dev/null || fail "rows must use .bh-row-grid"

# Cadence defaults must exist (8s / 30s / 120s)
grep -n "VITE_FETCH_MS" frontend/src/context/DataContext.jsx >/dev/null || fail "missing VITE_FETCH_MS in DataContext"
grep -n "8000" frontend/src/context/DataContext.jsx >/dev/null || fail "missing 8000 default fetch cadence"
grep -n "VITE_PUBLISH_3M_MS" frontend/src/context/DataContext.jsx >/dev/null || fail "missing VITE_PUBLISH_3M_MS in DataContext"
grep -n "30000" frontend/src/context/DataContext.jsx >/dev/null || fail "missing 30000 default 3m cadence"
grep -n "VITE_PUBLISH_BANNER_MS" frontend/src/context/DataContext.jsx >/dev/null || fail "missing VITE_PUBLISH_BANNER_MS in DataContext"
grep -n "120000" frontend/src/context/DataContext.jsx >/dev/null || fail "missing 120000 default banner cadence"
grep -n "setInterval(fetchOnce, 8000)" frontend/src/hooks/useDataFeed.js >/dev/null || fail "useDataFeed must poll every 8s"
grep -n "last3mRef" frontend/src/hooks/useDataFeed.js >/dev/null || fail "useDataFeed must cache 3m refresh"
grep -n "lastBannersRef" frontend/src/hooks/useDataFeed.js >/dev/null || fail "useDataFeed must cache banner refresh"

# Block old labels
grep -R --line-number "3 Min Gainers/Losers" frontend/src && fail "remove '3 Min Gainers/Losers' text"
grep -R --line-number "1 hour price %" frontend/src && fail "remove '1 hour price %' label"

# AnomalyStream must reference canonical keys
grep -R --line-number "gainers_1m" frontend/src/components/AnomalyStream.jsx >/dev/null || fail "AnomalyStream must reference gainers_1m"
grep -R --line-number "losers_3m" frontend/src/components/AnomalyStream.jsx >/dev/null || fail "AnomalyStream must reference losers_3m"
grep -R --line-number "volume_change_1h_pct" frontend/src/components/AnomalyStream.jsx >/dev/null || fail "AnomalyStream must reference volume_change_1h_pct"

ok "UI rules validated."
