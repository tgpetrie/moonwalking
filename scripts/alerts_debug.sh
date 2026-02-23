#!/usr/bin/env bash
set -euo pipefail

URL="${1:-http://127.0.0.1:5003/api/alerts?limit=120&active_ttl_s=300}"
OUT="${2:-/tmp/alerts.json}"

echo "[1] Fetching alerts -> $OUT"
curl -sS -D /tmp/alerts.headers "$URL" -o "$OUT"
sed -n '1,20p' /tmp/alerts.headers

echo
echo "[2] Strict JSON validation"
python3 -m json.tool "$OUT" >/dev/null
echo "JSON OK"

echo
echo "[3] Distribution"
python3 - <<'PY'
import json, collections
p="/tmp/alerts.json"
j=json.load(open(p))

def summarize(items, name):
    print(f"{name}: {len(items)}")
    types=collections.Counter((a.get("type_key") or a.get("type") or "unknown") for a in items)
    syms=collections.Counter((a.get("symbol") or a.get("product_id") or "??").upper() for a in items)
    print(" top types:", types.most_common(8))
    print(" top syms :", syms.most_common(8))

summarize(j.get("active", []), "active")
summarize(j.get("recent", []), "recent")
PY
