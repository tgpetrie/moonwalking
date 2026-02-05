#!/usr/bin/env bash
set -euo pipefail

fail() { echo "[guardrails] FAIL: $*" >&2; exit 1; }
ok() { echo "[guardrails] OK: $*"; }

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# --- Guardrail 1: forbid legacy port 5002 in active code/config ---
# Keep this scoped to executable/config files to avoid noise from markdown history,
# coverage output, vendored deps, and logs.
port_pattern='\\b5002\\b'

common_excludes=(
  --glob '!**/.git/**'
  --glob '!**/node_modules/**'
  --glob '!**/.venv/**'
  --glob '!**/venv/**'
  --glob '!**/__pycache__/**'
  --glob '!backend/htmlcov/**'
  --glob '!moonwalkings_UI_GOOD/**'
  --glob '!files/**'
  --glob '!**/*.log'
  --glob '!**/*.lock'
  --glob '!**/*.min.js'
  --glob '!**/*.map'
  --glob '!**/dist/**'
  --glob '!**/build/**'
)

if command -v rg >/dev/null 2>&1; then
  if rg -n "$port_pattern" \
    --glob '**/*.{sh,py,js,jsx,ts,tsx,json,yml,yaml}' \
    --glob '**/.env*' \
    --glob 'Dockerfile*' \
    --glob 'Procfile' \
    "${common_excludes[@]}" \
    . >/dev/null; then
    echo "[guardrails] Found forbidden '5002' in active code/config:" >&2
    rg -n "$port_pattern" \
      --glob '**/*.{sh,py,js,jsx,ts,tsx,json,yml,yaml}' \
      --glob '**/.env*' \
      --glob 'Dockerfile*' \
      --glob 'Procfile' \
      "${common_excludes[@]}" \
      . | head -n 50 >&2
    fail "remove/quarantine legacy port 5002 references"
  fi
else
  # Fallback: basic grep (less precise)
  if grep -R -n -E "$port_pattern" \
    --exclude-dir .git \
    --exclude-dir node_modules \
    --exclude-dir .venv \
    --exclude-dir venv \
    --exclude-dir __pycache__ \
    --exclude-dir htmlcov \
    --exclude-dir moonwalkings_UI_GOOD \
    --exclude-dir files \
    --exclude '*.log' \
    --exclude '*.lock' \
    --exclude '*.min.js' \
    --exclude '*.map' \
    frontend backend scripts .vscode docker-compose.yml Procfile Dockerfile* .env* 2>/dev/null | head -n 1 >/dev/null; then
    fail "remove/quarantine legacy port 5002 references (grep fallback)"
  fi
fi

ok "no legacy port 5002 references"

# --- Guardrail 2: forbid 'BTC-USD'-style literals in UI copy ---
# MW_SPEC wants display symbols to be base tickers (BTC, ETH), not product IDs.
if command -v rg >/dev/null 2>&1; then
  # Heuristic: flag explicit product-id literals like 'BTC-USD' / "BTC-USD".
  # Ignore comment contexts and URL contexts.
  ui_usd_hits=$(rg -n --pcre2 "\\b[A-Z0-9]{2,12}-USD\\b" frontend/src \
    --glob '!**/node_modules/**' \
    --glob '!**/*.test.*' \
    --glob '!**/__snapshots__/**' \
    | rg -v --pcre2 ':\s*(//|\*)' \
    | rg -v --fixed-strings -e 'http://' -e 'https://' -e 'coinbase.com' -e 'api.coinbase.com' -e 'advanced-trade' -e '/v2/prices/' \
    || true)

  if [[ -n "$ui_usd_hits" ]]; then
    echo "[guardrails] Found forbidden 'BTC-USD'-style literals in likely UI copy:" >&2
    echo "$ui_usd_hits" | head -n 50 >&2
    fail "remove product-id literals (BTC-USD) from UI copy"
  fi
else
  # Fallback: only check HTML for visible literals.
  if grep -R -n -E -- "\\b[A-Z0-9]{2,12}-USD\\b" frontend/src --include='*.html' >/dev/null 2>&1; then
    fail "remove 'BTC-USD' UI strings (grep fallback)"
  fi
fi

ok "no 'BTC-USD' UI literals"

echo "[guardrails] All guardrails passed."
