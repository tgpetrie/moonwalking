#!/usr/bin/env bash
set -euo pipefail

ROOT=$(git rev-parse --show-toplevel 2>/dev/null || echo ".")
cd "$ROOT"

errors=0
echo "[ui-rules] Running UI validation checks..."

# 1) Banner rails: ensure structure classes are present in CSS and used by banner components
echo "Checking banner structure classes..."
if ! grep -q "bh-banner-track" frontend/index.css 2>/dev/null; then
  echo "ERROR: .bh-banner-track not found in frontend/index.css."
  errors=$((errors+1))
else
  echo "OK: .bh-banner-track present in index.css."
fi

if ! grep -q "bh-banner-chip" frontend/index.css 2>/dev/null; then
  echo "ERROR: .bh-banner-chip not found in frontend/index.css."
  errors=$((errors+1))
else
  echo "OK: .bh-banner-chip present in index.css."
fi

if ! grep -RIn --include="*.js" --include="*.jsx" --include="*.ts" --include="*.tsx" "bh-banner-wrap" frontend/src/components/TopBannerScroll.* frontend/src/components/VolumeBannerScroll.* 2>/dev/null | sed -n '1p' >/dev/null; then
  echo "ERROR: .bh-banner-wrap not used in TopBannerScroll / VolumeBannerScroll."
  errors=$((errors+1))
else
  echo "OK: .bh-banner-wrap used in banner components."
fi

# 2) Token rows: shared grid + key classes
echo "Checking token row classes..."
if ! grep -q "token-row.table-row" frontend/index.css 2>/dev/null; then
  echo "ERROR: .token-row.table-row not defined in frontend/index.css."
  errors=$((errors+1))
else
  echo "OK: .token-row.table-row defined in index.css."
fi

if ! grep -RInE "token-row[^\\n]*table-row" frontend/src/components 2>/dev/null | sed -n '1p' >/dev/null; then
  echo "ERROR: token-row table-row class not used in React components."
  errors=$((errors+1))
else
  echo "OK: token-row table-row used in components."
fi

for cls in token-pct-gain token-pct-loss tr-price-current; do
  if ! grep -q "$cls" frontend/index.css 2>/dev/null; then
    echo "ERROR: .$cls not found in frontend/index.css."
    errors=$((errors+1))
  elif ! grep -RIn "$cls" frontend/src 2>/dev/null | sed -n '1p' >/dev/null; then
    echo "ERROR: .$cls not referenced in frontend/src."
    errors=$((errors+1))
  else
    echo "OK: .$cls present and referenced."
  fi
done

# 3) Font family: enforce Raleway only
echo "Checking font families..."
if ! grep -RIn "Raleway" frontend/index.css frontend/src/index.css 2>/dev/null | sed -n '1p' >/dev/null; then
  echo "ERROR: Raleway font not referenced in core styles."
  errors=$((errors+1))
else
  echo "OK: Raleway referenced."
fi

for forbidden in "Fragment Mono" "Prosto One" "FragmentMono" "ProstoOne"; do
  if grep -RIn --exclude-dir=dist "$forbidden" frontend 2>/dev/null | sed -n '1p' >/dev/null; then
    echo "ERROR: Forbidden font found: $forbidden"
    errors=$((errors+1))
  fi
done

if [[ "$errors" -gt 0 ]]; then
  echo
  echo "UI rules validation FAILED: $errors issue(s) detected."
  exit 1
fi

echo
echo "UI rules validation PASSED."
exit 0
