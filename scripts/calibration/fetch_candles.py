"""Pull ~1y of completed hourly candles for liquid Coinbase USD spot pairs."""
import json, os, time, urllib.request, urllib.error, datetime as dt

OUT = "/home/claude/calib/candles"
os.makedirs(OUT, exist_ok=True)
UA = {"User-Agent": "moonwalking-calibration/1.0"}
BASE = "https://api.exchange.coinbase.com"

def get(url, tries=5):
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=25) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code in (429, 502, 503, 504):
                time.sleep(1.5 * (i + 1)); continue
            raise
        except Exception:
            time.sleep(1.0 * (i + 1))
    return None

def universe(n=40):
    prods = get(f"{BASE}/products") or []
    usd = [p for p in prods
           if p.get("quote_currency") == "USD"
           and not p.get("trading_disabled") and p.get("status") == "online"
           and not p.get("limit_only") and not p.get("cancel_only")
           and p.get("id", "").split("-")[0] not in
           {"USDT","USDC","DAI","PYUSD","EUROC","GUSD","WBTC","CBETH","LSETH","PAX","BUSD"}]
    stats = []
    for p in usd:
        s = get(f"{BASE}/products/{p['id']}/stats")
        time.sleep(0.12)
        if not s: continue
        try:
            vol = float(s.get("volume") or 0) * float(s.get("last") or 0)
        except (TypeError, ValueError):
            continue
        if vol > 0:
            stats.append((vol, p["id"]))
    stats.sort(reverse=True)
    return [pid for _, pid in stats[:n]]

def candles(pid, days=365, gran=3600):
    end = dt.datetime.utcnow().replace(minute=0, second=0, microsecond=0)
    start_all = end - dt.timedelta(days=days)
    rows, cur = {}, end
    while cur > start_all:
        s = max(start_all, cur - dt.timedelta(hours=300))
        url = (f"{BASE}/products/{pid}/candles?granularity={gran}"
               f"&start={s.isoformat()}Z&end={cur.isoformat()}Z")
        d = get(url)
        time.sleep(0.22)
        if not d:
            cur = s; continue
        for r in d:
            if isinstance(r, list) and len(r) >= 6:
                rows[int(r[0])] = [float(x) for x in r[:6]]
        cur = s
    return [rows[k] for k in sorted(rows)]

if __name__ == "__main__":
    uni = universe(40)
    print("universe:", len(uni), uni[:10], flush=True)
    json.dump(uni, open("/home/claude/calib/universe.json", "w"))
    for i, pid in enumerate(uni, 1):
        path = f"{OUT}/{pid}.json"
        if os.path.exists(path):
            continue
        c = candles(pid)
        json.dump(c, open(path, "w"))
        print(f"[{i}/{len(uni)}] {pid}: {len(c)} candles", flush=True)
    print("done", flush=True)
