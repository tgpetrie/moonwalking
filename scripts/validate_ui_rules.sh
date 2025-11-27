#!/usr/bin/env bash
set -euo pipefail

ROOT=$(git rev-parse --show-toplevel 2>/dev/null || echo ".")
cd "$ROOT"

errors=0
echo "[ui-rules] Running UI validation checks..."

# 1) Trim -USD: fail if direct .replace('-USD' patterns exist in frontend code
echo "Checking for raw '-USD' replace usages..."
bad_replace=$(grep -RIn --exclude-dir=node_modules --exclude='*backup*' --exclude='*.bak' --exclude-dir=snapshots --include="*.js" --include="*.jsx" --include="*.ts" --include="*.tsx" "\\.replace(['\"]-USD" frontend || true)
if [[ -n "$bad_replace" ]]; then
  echo "ERROR: Found raw .replace('-USD' usage(s):"
  echo "$bad_replace"
  errors=$((errors+1))
else
  echo "OK: No raw .replace('-USD' patterns found."
fi

# 2) Dashboard mounted: ensure Dashboard file exists
echo "Checking Dashboard component exists..."
if [[ ! -f frontend/src/Dashboard.jsx && ! -f frontend/src/Dashboard.tsx ]]; then
  echo "ERROR: Dashboard component not found at frontend/src/Dashboard.jsx or .tsx"
  errors=$((errors+1))
else
  echo "OK: Dashboard component present."
fi

# 3) Banner structure: ensure .bh-banner-track exists in CSS and banners use .bh-banner-wrap
echo "Checking banner CSS and usage..."
if ! grep -q "bh-banner-track" frontend/index.css 2>/dev/null; then
  echo "ERROR: .bh-banner-track not found in frontend/index.css; required for banner rails."
  errors=$((errors+1))
else
  echo "OK: .bh-banner-track present in index.css."
fi

if ! grep -RIn "bh-banner-wrap" frontend/src/components/TopBannerScroll.jsx frontend/src/components/VolumeBannerScroll.jsx 2>/dev/null | sed -n '1p' >/dev/null; then
  echo "ERROR: .bh-banner-wrap not used in TopBannerScroll.jsx and VolumeBannerScroll.jsx."
  errors=$((errors+1))
else
  echo "OK: .bh-banner-wrap used in both banner components."
fi

# 4) Color tokens: fail if inline hex color strings appear inside JSX style attributes
echo "Checking for inline hex colors inside JSX style attributes..."
hex_inline=$(grep -RInE --exclude-dir=node_modules --exclude='*backup*' --exclude='*.bak' --exclude-dir=snapshots --include="*.jsx" --include="*.tsx" "style=\{\{[^}]*#[0-9A-Fa-f]{3,6}" frontend || true)
if [[ -n "$hex_inline" ]]; then
  echo "ERROR: Found inline hex colors inside JSX style attributes (prefer CSS tokens/classes):"
  echo "$hex_inline"
  errors=$((errors+1))
else
  echo "OK: No inline hex colors found in JSX style attributes."
fi

# 5) Token row + headers: ensure canonical row and section-head variants are used
echo "Checking for canonical token row and section headers..."
if ! grep -q "token-row.table-row" frontend/index.css 2>/dev/null; then
  echo "ERROR: .token-row.table-row not defined in frontend/index.css."
  errors=$((errors+1))
else
  echo "OK: .token-row.table-row defined in index.css."
fi

if ! grep -RIn "token-row table-row" frontend/src/components 2>/dev/null | sed -n '1p' >/dev/null; then
  echo "ERROR: token-row table-row class not used in React components (1m/3m/watchlist)."
  errors=$((errors+1))
else
  echo "OK: token-row table-row used in components."
fi

if ! grep -RIn "section-head-gain" frontend/src 2>/dev/null | sed -n '1p' >/dev/null; then
  echo "ERROR: .section-head-gain not referenced in any header render."
  errors=$((errors+1))
else
  echo "OK: .section-head-gain used in a header."
fi

if ! grep -RIn "section-head-loss" frontend/src 2>/dev/null | sed -n '1p' >/dev/null; then
  echo "ERROR: .section-head-loss not referenced in any header render."
  errors=$((errors+1))
else
  echo "OK: .section-head-loss used in a header."
fi

if [[ "$errors" -gt 0 ]]; then
  echo "\nUI rules validation FAILED: $errors issue(s) detected."
  exit 1
fi

echo "\nUI rules validation PASSED."
exit 0