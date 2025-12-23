#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FRONTEND="$ROOT/frontend"

fail() { echo "FAIL: $1" >&2; exit 1; }
ok() { echo "OK: $1"; }

cd "$ROOT"

# 1) Banner structure guardrails
grep -R --line-number -E '\bbh-banner-track\b' "$FRONTEND/src" >/dev/null \
  && ok "bh-banner-track referenced" \
  || fail "bh-banner-track not found in frontend/src"

grep -R --line-number -E '\bbh-banner-chip\b' "$FRONTEND/src" >/dev/null \
  && ok "bh-banner-chip referenced" \
  || fail "bh-banner-chip not found in frontend/src"

# 2) Token row class guardrail (components must render token-row table-row)
grep -R --line-number -E 'className=.*token-row.*table-row|token-row table-row' "$FRONTEND/src/components" >/dev/null \
  && ok "token-row table-row present in components" \
  || fail "token-row table-row not found in frontend/src/components"

# 3) Font guardrail: only Raleway is referenced as a named font-family
#    This asserts:
#      - Raleway appears at least once
#      - no other quoted font names appear (e.g., "Inter", "Montserrat", "Prosto", etc.)
grep -R --line-number -E 'font-family:\s*"?Raleway"?' "$FRONTEND/src" >/dev/null \
  && ok "Raleway font-family referenced" \
  || fail "Raleway font-family not found"

# find quoted font-family names other than Raleway
OTHER_FONTS="$(grep -R --line-number -E 'font-family:[^;]*"[^"]+' "$FRONTEND/src" | grep -v 'Raleway' || true)"
if [[ -n "$OTHER_FONTS" ]]; then
  echo "$OTHER_FONTS" >&2
  fail "Non-Raleway quoted font-family detected"
fi
ok "No non-Raleway quoted fonts detected"

# 4) Required class names exist AND are referenced
grep -R --line-number -E '\btoken-pct-gain\b' "$FRONTEND/src" >/dev/null \
  && ok "token-pct-gain exists/referenced" \
  || fail "token-pct-gain missing"

grep -R --line-number -E '\btoken-pct-loss\b' "$FRONTEND/src" >/dev/null \
  && ok "token-pct-loss exists/referenced" \
  || fail "token-pct-loss missing"

grep -R --line-number -E '\btr-price-current\b' "$FRONTEND/src" >/dev/null \
  && ok "tr-price-current exists/referenced" \
  || fail "tr-price-current missing"

echo "All UI rule validations passed."

