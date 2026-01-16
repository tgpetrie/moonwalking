#!/usr/bin/env bash
set -euo pipefail

BASE="${MW_BACKEND_BASE:-${BACKEND_BASE:-http://127.0.0.1:5003}}"

echo "[verify] base: $BASE"

echo
echo "[verify] /api/data meta + movers counts"
curl -sS "$BASE/api/data" | python3 -c 'import json,sys; d=json.load(sys.stdin); m=d.get("meta") or {};
def count_comp(x):
    return len((x.get("data") or [])) if isinstance(x, dict) else (len(x) if isinstance(x, list) else 0)
print("warming_1m:", m.get("warming_1m"), "warming_3m:", m.get("warming_3m"), "staleSeconds:", m.get("staleSeconds"))
print("gainers_1m_rows:", count_comp(d.get("gainers_1m")))
print("gainers_3m_rows:", count_comp(d.get("gainers_3m")))
print("losers_3m_rows :", count_comp(d.get("losers_3m")))
print("alerts_rows   :", len(d.get("alerts") or []))'

echo
echo "[verify] /api/config impulse keys"
curl -sS "$BASE/api/config" | python3 -c 'import json,sys; d=json.load(sys.stdin); cfg=d.get("config") or {};
print("ALERT_IMPULSE_1M_PCT =", d.get("ALERT_IMPULSE_1M_PCT", cfg.get("ALERT_IMPULSE_1M_PCT")))
print("ALERT_IMPULSE_3M_PCT =", d.get("ALERT_IMPULSE_3M_PCT", cfg.get("ALERT_IMPULSE_3M_PCT")))'

echo
echo "[verify] /api/alerts/recent count + sample"
curl -sS "$BASE/api/alerts/recent" | python3 -c 'import json,sys; j=json.load(sys.stdin); a=j.get("alerts") or []; print("alerts_len:", len(a));
print("sample:", {k:a[0].get(k) for k in ("ts","type","symbol","severity","message","trade_url") if k in a[0]}) if a else None'

echo
echo "[verify] done"
