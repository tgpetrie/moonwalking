#!/usr/bin/env bash
set -euo pipefail

BASE="${MW_BACKEND_BASE:-${BACKEND_BASE:-http://127.0.0.1:5003}}"

MIN_GAINERS_1M="${MIN_GAINERS_1M:-5}"
MIN_GAINERS_3M="${MIN_GAINERS_3M:-10}"
MIN_LOSERS_3M="${MIN_LOSERS_3M:-10}"

MUST_INCLUDE_PRODUCTS="${MW_MUST_INCLUDE_PRODUCTS:-BTC-USD,ETH-USD,SOL-USD,AMP-USD}"

tmpfile=$(mktemp)
if ! curl -sS --max-time 8 "$BASE/api/data" -o "$tmpfile"; then
    echo "[coverage] FAIL: /api/data request failed" >&2
    rm -f "$tmpfile"
    exit 2
fi
if [ ! -s "$tmpfile" ]; then
    echo "[coverage] FAIL: /api/data returned empty payload" >&2
    rm -f "$tmpfile"
    exit 2
fi

python3 - <<PY
import json,sys,os

with open("$tmpfile", "r") as f:
        d=json.load(f)

def pid(row):
    if not isinstance(row, dict):
        return ""
    p = row.get("product_id") or row.get("symbol") or ""
    p = str(p).strip().upper()
    if p and "-" not in p:
        p = f"{p}-USD"
    return p

def dupes(name, rows):
    rows = rows or []
    pids = [pid(r) for r in rows if pid(r)]
    dup = sorted({p for p in pids if pids.count(p) > 1})
    print(f"[coverage] {name}: rows={len(rows)} dupes={len(dup)} sample={dup[:8]}")
    return dup

lists = {
    "gainers_1m": d.get("gainers_1m") or [],
    "gainers_3m": d.get("gainers_3m") or [],
    "losers_3m": d.get("losers_3m") or [],
}

failed = False
for name, rows in lists.items():
    if dupes(name, rows):
        failed = True

must = [p.strip().upper() for p in os.getenv("MW_MUST_INCLUDE_PRODUCTS", "").split(",") if p.strip()]
if not must:
    must = ["BTC-USD","ETH-USD","SOL-USD","AMP-USD"]

have = {pid(r) for rows in lists.values() for r in rows if pid(r)}
missing = sorted(list(set(must) - have))
print("[coverage] missing_must:", missing)
if missing:
    failed = True

min_g1 = int(os.getenv("MIN_GAINERS_1M", "5"))
min_g3 = int(os.getenv("MIN_GAINERS_3M", "10"))
min_l3 = int(os.getenv("MIN_LOSERS_3M", "10"))

if len(lists["gainers_1m"]) < min_g1:
    print(f"[coverage] FAIL: gainers_1m < {min_g1}")
    failed = True
if len(lists["gainers_3m"]) < min_g3:
    print(f"[coverage] FAIL: gainers_3m < {min_g3}")
    failed = True
if len(lists["losers_3m"]) < min_l3:
    print(f"[coverage] FAIL: losers_3m < {min_l3}")
    failed = True

if failed:
    print("[coverage] FAIL")
    sys.exit(2)

print("[coverage] OK")
PY

rm -f "$tmpfile"
