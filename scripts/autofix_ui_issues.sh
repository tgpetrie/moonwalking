#!/usr/bin/env bash
set -euo pipefail

ROOT=$(git rev-parse --show-toplevel 2>/dev/null || echo ".")
cd "$ROOT"

BACKUP_DIR=".autofix_backups"
DRY_RUN=0

usage(){
  cat <<EOF
Usage: $0 [--dry-run] [--backup-dir DIR]
--dry-run    Show what would change but do not write files.
--backup-dir DIR  Directory to store original files (default: $BACKUP_DIR)
EOF
  exit 1
}

while (("$#")); do
  case "$1" in
    --dry-run) DRY_RUN=1; shift ;;
    --backup-dir) BACKUP_DIR="$2"; shift 2 ;;
    -h|--help) usage ;;
    *) echo "Unknown arg: $1"; usage ;;
  esac
done

mkdir -p "$BACKUP_DIR"

echo "[autofix] Scanning for simple autofix candidates..."

# Find files with .replace('-USD' patterns (exclude backups/snapshots)
mapfile -t REPLACE_FILES < <(grep -RIl --exclude-dir=node_modules --exclude='*.backup.*' --exclude-dir=snapshots --include="*.js" --include="*.jsx" --include="*.ts" --include="*.tsx" "\.replace(['\"-USD" frontend || true)

if [[ ${#REPLACE_FILES[@]} -eq 0 ]]; then
  echo "[autofix] No .replace('-USD') occurrences found in tracked frontend files."
else
  # Filter out obvious backup/snapshot files (filenames containing .backup, .bak, .orig)
  FILTERED=()
  for p in "${REPLACE_FILES[@]}"; do
    case "$p" in
      *".backup"*|*".bak"|*"~"|*".orig"*)
        # skip backup-like files
        continue
        ;;
      *) FILTERED+=("$p") ;;
    esac
  done
  REPLACE_FILES=("${FILTERED[@]}")

  echo "[autofix] Files with .replace('-USD'):"
  printf "  %s\n" "${REPLACE_FILES[@]}"
fi

for f in "${REPLACE_FILES[@]}"; do
  echo "\n[autofix] Processing: $f"
  cp "$f" "$BACKUP_DIR/$(echo "$f" | sed 's|/|__|g')" || true
  if [[ $DRY_RUN -eq 1 ]]; then
    echo "DRY RUN: would apply transformations to $f"
    continue
  fi

  # 1) Replace pattern: item.symbol?.replace('-USD', '') -> formatSymbol(item.symbol)
  perl -0777 -pe \
    "s/([A-Za-z0-9_\$\.]+)\?\.replace\(\s*['\"]-USD['\"]\s*,\s*['\"]\s*['\"]\s*\)/formatSymbol(\$1)/g" -i "$f" || true

  # 2) Replace pattern: (row.symbol || '').replace('-USD','') -> formatSymbol(row.symbol)
  perl -0777 -pe \
    "s/\(\s*([A-Za-z0-9_\$\.]+)\s*\|\|\s*['\"]['\"]\s*\)\.replace\(\s*['\"]-USD['\"]\s*,\s*['\"]['\"]\s*\)/formatSymbol(\$1)/g" -i "$f" || true

  # 3) Replace regex .replace(/-USD$/i, '') -> formatSymbol(var)
  perl -0777 -pe \
    "s/([A-Za-z0-9_\$\.]+)\.replace\(\/\\-USD\$\/i\s*,\s*['\"]['\"]\s*\)/formatSymbol(\$1)/g" -i "$f" || true

  # 4) If file now contains formatSymbol but no import, inject a relative import if possible
  if grep -q "formatSymbol" "$f" && ! grep -q "import .*formatSymbol" "$f"; then
    echo "[autofix] Adding import for formatSymbol in $f"
    # Attempt to find a sensible relative path to lib/format.js
    # We'll add a generic import that should work for most frontend files: ../lib/format.js
    perl -0777 -pe "s/^(import [^\n]+\n+)/\$1import formatSymbol from '..\/lib\/format.js';\n/" -i "$f" || true
    # If file didn't have any imports, just prepend
    if ! grep -q "import formatSymbol" "$f"; then
      sed -i "1s;^;import formatSymbol from '../lib/format.js';\n;" "$f"
    fi
  fi
done

echo "\n[autofix] Color-style autofixes (limited, safe replacements)"

# BSD-safe hex color detection pattern
HEX_COLOR_PATTERN='#[0-9A-Fa-f]{3}([^0-9A-Fa-f]|$)|#[0-9A-Fa-f]{6}([^0-9A-Fa-f]|$)'

# Find JSX/TSX files that contain inline color hex literals (exclude backups)
mapfile -t COLOR_FILES < <(grep -E -RIl --exclude-dir=node_modules --exclude='*backup*' --exclude='*.bak' --exclude='*~' --include="*.jsx" --include="*.tsx" "$HEX_COLOR_PATTERN" frontend || true)
for f in "${COLOR_FILES[@]}"; do
  echo "Autofix color in $f"
  cp "$f" "$BACKUP_DIR/$(echo "$f" | sed 's|/|__|g')" || true
  if [[ $DRY_RUN -eq 1 ]]; then
    echo "DRY RUN: would replace inline color in $f"
    continue
  fi
  # Safely replace a few well-known inline color patterns used in the project
  set +e
  grep -E -q "#10B981" "$f"
  if [[ $? -eq 0 ]]; then
    perl -0777 -pe "s/style=\{\{\s*color:\s*['\"]#10B981['\"]\s*\}\}/className=\"text-green-400\"/g" -i "$f" || true
  fi
  # another specific pattern replacement (drop-shadow with #FEA400)
  grep -E -q "#FEA400" "$f"
  if [[ $? -eq 0 ]]; then
    perl -0777 -pe "s/style=\{\{\s*filter:\s*filled\s*\?\s*'drop-shadow\([^']+#FEA400'\)\s*:\s*undefined\s*,?\s*transition:\s*'filter 0\.2s'\s*\}\}//g" -i "$f" || true
  fi
  set -e
done

echo "\n[autofix] Completed. Backups stored in $BACKUP_DIR"
echo "Review changes, run tests, then 'git add' and commit."
exit 0
