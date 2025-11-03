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

# 3) Gainers 2-column behavior: check OneMinGainersColumns.jsx has lg:grid-cols-2
echo "Checking 1m gainers two-column layout class..."
if ! grep -Eq "lg:grid-cols-2" frontend/src/components/OneMinGainersColumns.jsx 2>/dev/null; then
  echo "ERROR: OneMinGainersColumns.jsx does not contain 'lg:grid-cols-2' class to support 2-column layout."
  errors=$((errors+1))
else
  echo "OK: Two-column layout class present."
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

# 5) Hover line: ensure .row-hover-line exists somewhere in frontend
echo "Checking for .row-hover-line usage..."
if ! grep -RIn --exclude='*backup*' "row-hover-line" frontend 2>/dev/null | sed -n '1,5p' >/dev/null; then
  echo "ERROR: .row-hover-line not found in frontend; required for hover underline behavior."
  errors=$((errors+1))
else
  echo "OK: .row-hover-line usage found."
fi

if [[ "$errors" -gt 0 ]]; then
  echo "\nUI rules validation FAILED: $errors issue(s) detected."
  exit 1
fi

echo "\nUI rules validation PASSED."
exit 0
