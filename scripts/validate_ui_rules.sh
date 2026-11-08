#!/usr/bin/env bash
set -euo pipefail

fail() { echo "FAIL: $*" >&2; exit 1; }
ok() { echo "OK: $*"; }

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

CSS="frontend/src/index.css"
COMPONENTS="frontend/src/components"
CONTEXT="frontend/src/context/DataContext.jsx"
FEED="frontend/src/hooks/useDataFeed.js"

test -f "$CSS" || fail "missing $CSS"
if [ -f "frontend/index.css" ]; then
  fail "frontend/index.css should not exist; use frontend/src/index.css"
fi

# Both board banners drive the manual track with requestAnimationFrame.
for banner in "$COMPONENTS/TopBannerScroll.jsx" "$COMPONENTS/VolumeBannerScroll.jsx"; do
  grep -Fq 'className="bh-banner-track bh-banner-track--manual"' "$banner" || fail "$banner must use the manual banner track"
  grep -Eq 'className=.*bh-banner-chip([[:space:]"`]|$)' "$banner" || fail "$banner must use .bh-banner-chip"
  grep -Fq 'requestAnimationFrame(' "$banner" || fail "$banner must animate the banner track"
done
grep -Eq '^\.bh-banner-track--manual[[:space:]]*\{' "$CSS" || fail "missing manual banner track styles"

# Typography hierarchy contract must exist
for class in bh-change bh-price-current bh-price-previous; do
  grep -Eq "\\.${class}([[:space:],{.:]|$)" "$CSS" || fail "missing .$class"
  grep -Eq "className=.*${class}([[:space:]\"$]|$)" "$COMPONENTS/TokenRowUnified.jsx" || fail "board rows must render .$class"
done

# Global color tokens must exist
grep -Eq '^[[:space:]]+--bh-fg:' "$CSS" || fail "missing --bh-fg"
grep -Eq '^[[:space:]]+--bh-mint:' "$CSS" || fail "missing --bh-mint"

# The board's permanent rail is the ::before pseudo-element on the row grid.
awk '
  /^\.board-core \.bh-row\.bh-row-grid::before[[:space:]]*\{/ { rail = 1 }
  rail && /^[[:space:]]*bottom:[[:space:]]*0[[:space:]]*(!important)?;/ { bottom = 1 }
  /^}/ { rail = 0 }
  END { exit !bottom }
' "$CSS" || fail "board row rail must be positioned at bottom: 0"

# Canonical grid must exist
grep -Eq 'grid-template-columns:[[:space:]]*var\(--bh-row-cols' "$CSS" || fail "row grid must use --bh-row-cols"
grep -Fq '"bh-row-grid"' "$COMPONENTS/TokenRowUnified.jsx" || fail "board rows must use .bh-row-grid"

# DataContext owns the live cadence. The compatibility hook reads its snapshot.
node --input-type=module <<'JS'
import assert from "node:assert/strict";
import { deriveDashboardCadence } from "./frontend/src/config/cadence.js";

const { FAST_1M_MS, PUBLISH_3M_MS, PUBLISH_BANNER_MS } = deriveDashboardCadence();
assert.deepEqual(
  [FAST_1M_MS, PUBLISH_3M_MS, PUBLISH_BANNER_MS],
  [3800, 12000, 30000],
  "Unexpected default board polling and publish cadence",
);
JS
grep -Fq 'deriveDashboardCadence(import.meta.env)' "$CONTEXT" || fail "DataContext must use the shared cadence"
grep -Fq 'BACKOFF_1M_MS : FAST_1M_MS' "$CONTEXT" || fail "DataContext must poll at the configured cadence"
grep -Fq 'last3mPublishRef.current >= PUBLISH_3M_MS' "$CONTEXT" || fail "DataContext must throttle 3m publishing"
for banner in Price Volume; do
  grep -Fq "last${banner}BannerPublishRef.current >= PUBLISH_BANNER_MS" "$CONTEXT" || fail "DataContext must throttle $banner banner publishing"
done
grep -Fq 'const ctx = useData()' "$FEED" || fail "useDataFeed must use the shared DataContext"

# Block old labels
if grep -R -nE '3 Min Gainers/Losers|1 hour price %' frontend/src; then
  fail "remove obsolete board labels"
fi

# Validate the canonical snapshot keys at their producer, and volume at its consumer.
for key in gainers_1m losers_3m; do
  grep -Eq "^[[:space:]]+${key}:" "$CONTEXT" || fail "DataContext must publish $key"
done
grep -Fq 'volume_change_1h_pct' "$COMPONENTS/AnomalyStream.jsx" || fail "AnomalyStream must reference volume_change_1h_pct"

ok "UI rules validated."
