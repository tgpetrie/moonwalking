#!/usr/bin/env bash
set -euo pipefail

CSS="frontend/src/index.css"

if [[ ! -f "$CSS" ]]; then
  echo "FAIL: missing $CSS"
  exit 1
fi

if command -v mktemp >/dev/null 2>&1; then
  TMP_CSS="$(mktemp)"
else
  TMP_CSS="/tmp/verify_ui_contract.css"
fi

python3 - <<'PY' "$CSS" > "$TMP_CSS"
import pathlib, re, sys

path = pathlib.Path(sys.argv[1])
data = path.read_text()
print(re.sub(r'/\\*.*?\\*/', '', data, flags=re.S))
PY

trap 'rm -f "$TMP_CSS"' EXIT

PASS=0
FAIL=0

say_ok()  { echo "PASS: $1"; PASS=$((PASS+1)); }
say_no()  { echo "FAIL: $1"; FAIL=$((FAIL+1)); }
say_info(){ echo "INFO: $1"; }

# ---------- 1) Duplicate pseudo-element blocks ----------
after_count="$(rg -n '\.bh-row::after\b' "$TMP_CSS" | wc -l | tr -d ' ')"
before_count="$(rg -n '\.bh-row::before\b' "$TMP_CSS" | wc -l | tr -d ' ')"
say_info ".bh-row::after occurrences: $after_count"
say_info ".bh-row::before occurrences: $before_count"

# Heuristic: we expect far fewer than "wildly duplicated" counts.
# Adjust threshold if your contract intentionally includes multiple blocks.
if [[ "$after_count" -le 6 ]]; then
  say_ok "Pseudo-element duplication seems controlled (after_count <= 6)"
else
  say_no "Too many .bh-row::after occurrences (expected <= 6, found $after_count)"
fi

# ---------- 2) Only data-side selectors control hue ----------
# Legacy gain/loss selector families that should not drive hue.
legacy_hits="$(rg -n '(\.bh-row[^,{]*\b(is-gain|is-loss|bh-row--gain|bh-row--loss)|\.token-row\.table-row[^,{]*\b(is-gain|is-loss))' "$TMP_CSS" || true)"
if [[ -z "$legacy_hits" ]]; then
  say_ok "No legacy gain/loss selector families found"
else
  say_no "Legacy gain/loss selector families still present (should be neutralized or mapped)"
  echo "$legacy_hits" | head -n 40
  [[ "$(echo "$legacy_hits" | wc -l | tr -d ' ')" -gt 40 ]] && echo "… (truncated)"
fi

# Ensure data-side selectors exist
ds_gainer="$(rg -n '\.bh-row\[data-side="gainer"\]' "$TMP_CSS" || true)"
ds_loser="$(rg -n '\.bh-row\[data-side="loser"\]' "$TMP_CSS" || true)"
if [[ -n "$ds_gainer" && -n "$ds_loser" ]]; then
  say_ok "data-side selectors exist for both gainer and loser"
else
  say_no "Missing data-side selectors for gainer and/or loser"
fi

# ---------- 3) Single authoritative hover block near file end ----------
# Heuristic: look for a marker comment. If you adopt a specific marker,
# update the pattern below to match it.
marker_pat='(AUTHORITATIVE|FINAL|CANONICAL)\s+ROW\s+HOVER'
marker="$(tail -n 220 "$CSS" | rg -n "$marker_pat" || true)"

if [[ -n "$marker" ]]; then
  say_ok "Authoritative hover marker found near end of file"
else
  say_no "No authoritative hover marker found near end of file (add a clear marker comment)"
fi

# ---------- 4) Rabbit spotlight linkage ----------
# Must reference emit vars and data-row-hover in CSS.
emitx="$(rg -n -F -- '--emit-x' "$TMP_CSS" || true)"
emity="$(rg -n -F -- '--emit-y' "$TMP_CSS" || true)"
rowhover="$(rg -n 'data-row-hover\s*=\s*"1"|data-row-hover\s*=\s*1|\[data-row-hover(=|~|\\])' "$TMP_CSS" || true)"
rabbit="$(rg -n 'rabbit-bg' "$TMP_CSS" || true)"

if [[ -n "$emitx" && -n "$emity" ]]; then
  say_ok "CSS references --emit-x and --emit-y"
else
  say_no "CSS is missing --emit-x/--emit-y references"
fi

if [[ -n "$rowhover" ]]; then
  say_ok "CSS references data-row-hover gating"
else
  say_no "CSS does not reference data-row-hover gating"
fi

if [[ -n "$rabbit" ]]; then
  say_ok "CSS references rabbit-bg"
else
  say_no "CSS does not reference rabbit-bg"
fi

# ---------- Summary ----------
echo "----"
say_info "Total PASS: $PASS"
say_info "Total FAIL: $FAIL"

if [[ "$FAIL" -eq 0 ]]; then
  exit 0
else
  exit 2
fi
