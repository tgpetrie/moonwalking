#!/usr/bin/env bash
# UI rules for the BHABIT / Moonwalking board.
#
# Encodes the tactical-terminal rules agreed on 2026-08-09 and 2026-11-24:
# squared controls (3px CTAs and inputs, 4px panels and cards), Raleway type,
# the BHABIT wordmark with "Profit Buying Impulse" stacked under it, and no
# consumer pill-shaped buttons (round status badges are still fine).
#
# Every check runs; all failures are listed before the script exits non-zero.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

SRC="frontend/src"
CSS="$SRC/index.css"
TOKENS="$SRC/styles/design-tokens.css"
ALIGN="$SRC/styles/bhabit-alignment.css"
SHELL_JSX="$SRC/components/DashboardShell.jsx"

failures=0
fail() { echo "FAIL: $*"; failures=$((failures + 1)); }
ok() { echo "ok:   $*"; }

# need FILE ERE MESSAGE: FILE must contain a line matching ERE.
need() {
  if [ ! -f "$1" ]; then fail "$3 (missing file $1)"
  elif grep -qE -- "$2" "$1"; then ok "$3"
  else fail "$3 ($1)"; fi
}
# need_src ERE MESSAGE: some file under frontend/src must match.
need_src() {
  if grep -rqE -- "$1" "$SRC"; then ok "$2"; else fail "$2"; fi
}
# forbid_src FIXED-STRING MESSAGE: no file under frontend/src may contain it.
forbid_src() {
  local hits
  hits="$(grep -rnF -- "$1" "$SRC" || true)"
  if [ -n "$hits" ]; then fail "$2"; echo "$hits" | sed 's/^/        /'; else ok "$2"; fi
}

echo "== Layout"
if [ -f "$CSS" ]; then ok "stylesheet lives at $CSS"; else fail "missing $CSS"; fi
if [ -f "frontend/index.css" ]; then
  fail "frontend/index.css must not exist; use $CSS"
else
  ok "no stray frontend/index.css"
fi

echo "== Radius tokens (3px controls, 4px surfaces)"
need "$TOKENS" '^[[:space:]]*--r-2:[[:space:]]*3px;' "--r-2 is 3px (buttons, CTAs, inputs)"
need "$TOKENS" '^[[:space:]]*--r-3:[[:space:]]*4px;' "--r-3 is 4px (panels)"
need "$TOKENS" '^[[:space:]]*--r-4:[[:space:]]*4px;' "--r-4 is 4px (cards)"

echo "== Typography"
need "$CSS" "family=Raleway" "Raleway is loaded"
need "$CSS" "^[[:space:]]*--bh-font-sans:[[:space:]]*['\"]Raleway['\"]" "--bh-font-sans leads with Raleway"

echo "== Brand lockup (BHABIT over Profit Buying Impulse)"
need "$SHELL_JSX" 'className="bh-brand__lockup"' "header has the brand lockup"
need "$SHELL_JSX" 'className="bh-brand__wordmark"' "lockup carries the BHABIT wordmark"
need "$SHELL_JSX" 'className="bh-brand__tagline">Profit Buying Impulse<' "tagline reads Profit Buying Impulse"

echo "== Board structure"
need_src "bh-banner-track" "banners use .bh-banner-track"
need_src "bh-banner-chip" "banners use .bh-banner-chip"
need "$CSS" '\.bh-pct' "typography: .bh-pct"
need "$CSS" '\.bh-price-current' "typography: .bh-price-current"
need "$CSS" '\.bh-price-prev' "typography: .bh-price-prev"
need "$CSS" '--bh-mint' "color token --bh-mint"
need "$CSS" '\.bh-row::after' "rows keep the permanent bottom rail (.bh-row::after)"
need "$CSS" '--bh-cols' "canonical grid token --bh-cols"
need_src "bh-row-grid" "rows use .bh-row-grid"
need "$SRC/components/AnomalyStream.jsx" "volume_change_1h_pct" "Intelligence Log reads volume_change_1h_pct"

echo "== Retired copy"
forbid_src "3 Min Gainers/Losers" "no '3 Min Gainers/Losers' label"
forbid_src "1 hour price %" "no '1 hour price %' label"

echo "== Controls: no consumer pill buttons"
PY=""
for candidate in python3 python; do
  # Skip stubs that exist on PATH but can't run (e.g. the Windows Store alias).
  if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c "import sys" >/dev/null 2>&1; then
    PY="$candidate"; break
  fi
done
if [ -z "$PY" ]; then
  fail "python3 is needed for the CSS control scan"
else
  # Prints "FAIL ..." for pill-shaped buttons and "WARN ..." for buttons
  # rounder than the 4px ceiling. Icons and badges inside buttons may be round.
  scan="$("$PY" - "$SRC" <<'PY'
import pathlib, re, sys

root = pathlib.Path(sys.argv[1])
skip = {"legacy", "legacy913", "playground"}
control = re.compile(r"(btn|button|cta)(?![\w-]*(icon|badge|dot))", re.I)
radius = re.compile(r"border-radius\s*:\s*([^;}]+)", re.I)

def as_px(value):
    first = value.strip().split()[0]
    if first.endswith("%"):
        return 9999.0
    for unit, scale in (("px", 1.0), ("rem", 16.0), ("em", 16.0)):
        if first.endswith(unit):
            try:
                return float(first[: -len(unit)]) * scale
            except ValueError:
                return None
    return None

for path in sorted(root.rglob("*.css")):
    if skip & set(path.parts):
        continue
    raw = path.read_text(encoding="utf-8", errors="ignore")
    # Blank out comments but keep their newlines so line numbers stay right.
    text = re.sub(r"/\*.*?\*/", lambda m: "\n" * m.group(0).count("\n"), raw, flags=re.S)
    for rule in re.finditer(r"([^{}]+)\{([^{}]*)\}", text):
        selector = " ".join(rule.group(1).split())
        if not control.search(selector):
            continue
        for decl in radius.finditer(rule.group(2)):
            px = as_px(decl.group(1))
            if px is None or px <= 4:
                continue
            line = text[: rule.start(2) + decl.start()].count("\n") + 1
            level = "FAIL" if px >= 12 else "WARN"
            print(f"{level} {path.as_posix()}:{line}  {selector[:80]}  border-radius: {decl.group(1).strip()}")
PY
)"
  scan_status=$?
  if [ "$scan_status" -ne 0 ]; then
    fail "CSS control scan crashed (exit $scan_status)"
  fi
  pills="$(printf '%s\n' "$scan" | grep '^FAIL' || true)"
  rounded="$(printf '%s\n' "$scan" | grep '^WARN' || true)"
  if [ -n "$pills" ]; then
    fail "pill-shaped buttons found (use var(--r-2), 3px)"
    printf '%s\n' "$pills" | sed 's/^FAIL /        /'
  else
    ok "no pill-shaped buttons"
  fi
  if [ -n "$rounded" ]; then
    echo "warn: buttons rounder than 4px (not failing yet):"
    printf '%s\n' "$rounded" | sed 's/^WARN /        /'
  fi
fi

echo
if [ "$failures" -gt 0 ]; then
  echo "UI rules: $failures check(s) failed."
  exit 1
fi
echo "UI rules validated."
