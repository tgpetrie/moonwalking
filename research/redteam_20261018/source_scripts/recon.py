"""Reconstruct ~24h ATR-based outcomes for production signals from archived hourly candles.

Read-only on the candle archive and the production backup. Writes per-row results
to ~/.moonwalking/analysis/recon.sqlite.
"""
import glob, os, sqlite3, sys, time
import numpy as np

H = 3600
NPATH = 23            # candles fully inside ~24h after the entry hour boundary
COST_PCT = 0.002      # 0.2% round trip, same assumption the board store uses
HOME = os.path.expanduser("~/.moonwalking")
cand = sqlite3.connect(f"file:{HOME}/data/candle_archive.sqlite?mode=ro", uri=True)
sigdb = sorted(glob.glob(f"{HOME}/prod-backup/*/signal_outcomes.sqlite"))[-1]
sig = sqlite3.connect(f"file:{sigdb}?mode=ro", uri=True)

# ---- load hourly candles per product -------------------------------------
t0 = time.time()
data = {}
cur = cand.execute(
    "select product_id, ts, open, high, low, close from candles "
    "where granularity=3600 order by product_id, ts")
last, buf = None, []
def flush(p, rows):
    a = np.array(rows, dtype=np.float64)
    data[p] = (a[:, 0].astype(np.int64), a[:, 1], a[:, 2], a[:, 3], a[:, 4])
for p, ts, o, h, l, c in cur:
    if p != last and buf:
        flush(last, buf); buf = []
    last = p; buf.append((ts, o, h, l, c))
if buf: flush(last, buf)
print(f"loaded {len(data)} products in {time.time()-t0:.1f}s", flush=True)
t_min = int(min(v[0][0] for v in data.values())); t_max = int(max(v[0][-1] for v in data.values())) + H
btc = data.get("BTC-USD")

def btc_ctx(entry_ts):
    """BTC return over the last 4 completed hours, or nan."""
    if btc is None: return np.nan
    ts, o, h, l, c = btc
    j = np.searchsorted(ts, entry_ts - H, side="right") - 1
    if j < 4 or ts[j] - ts[j - 4] != 4 * H: return np.nan
    return c[j] / c[j - 4] - 1.0

def evaluate(prod, entry_ts, entry, s):
    """Return a tuple of outcome fields or None if candles are incomplete."""
    d = data.get(prod)
    if d is None: return None
    ts, o, h, l, c = d
    tb = -(-entry_ts // H) * H                      # ceil to the next hour boundary
    i0 = np.searchsorted(ts, tb)
    if i0 + NPATH > len(ts) or ts[i0 + NPATH - 1] - ts[i0] != (NPATH - 1) * H or ts[i0] != tb:
        return None
    j = np.searchsorted(ts, entry_ts - H, side="right") - 1   # last completed candle
    if j < 14 or ts[j] - ts[j - 14] != 14 * H: return None
    hh, ll, cc = h[j - 13:j + 1], l[j - 13:j + 1], c[j - 14:j + 1]
    tr = np.maximum(hh - ll, np.maximum(np.abs(hh - cc[:-1]), np.abs(ll - cc[:-1])))
    atr = float(tr.mean())
    if not atr > 0 or not entry > 0: return None
    base = float(c[j - 13:j + 1].mean())
    ext = s * (entry - base) / atr
    H_, L_, C_ = h[i0:i0 + NPATH], l[i0:i0 + NPATH], c[i0:i0 + NPATH]
    if s > 0: fav, adv, ret = (H_ - entry) / atr, (entry - L_) / atr, (C_ - entry) / atr
    else:     fav, adv, ret = (entry - L_) / atr, (H_ - entry) / atr, (entry - C_) / atr
    cost_atr = COST_PCT * entry / atr
    out = [atr / entry, ext, btc_ctx(entry_ts) * s, float(fav.max()), float(adv.max()),
           float(ret[2]), float(ret[10]), float(ret[22])]
    for T, S in ((1.0, 1.0), (2.0, 1.0)):
        ft = np.nonzero(fav >= T)[0]; at = np.nonzero(adv >= S)[0]
        tT = ft[0] if len(ft) else 99; tS = at[0] if len(at) else 99
        if tT < tS:      res, r = 1, T / S
        elif tS < 99:    res, r = -1, -1.0
        else:            res, r = 0, float(np.clip(ret[22] / S, -1.0, T / S))
        amb = 1 if (tT == tS and tT < 99) else 0
        out += [res, amb, r - cost_atr / S]
    return tuple(out)

FIELDS = ("atr_pct", "ext", "btc4h", "mfe", "mae", "r4", "r12", "r24",
          "res11", "amb11", "netR11", "res21", "amb21", "netR21")

os.makedirs(f"{HOME}/analysis", exist_ok=True)
dst = sqlite3.connect(f"{HOME}/analysis/recon.sqlite")
dst.execute("drop table if exists recon")
dst.execute("create table recon (kind text, product_id text, ts integer, label text, direction text, "
            "s integer, " + ", ".join(f"{f} real" for f in FIELDS) + ")")

# ---- signals ----------------------------------------------------------------
t0 = time.time(); n = ok = 0; batch = []
q = sig.execute("select product_id, started_ts, start_price, read_label, direction from signal_outcomes "
                "where complete=1 and direction in ('up','down') and started_ts between ? and ?",
                (t_min + 16 * H, t_max - 26 * H))
for prod, ts_, px, lab, dr in q:
    n += 1
    s = 1 if dr == "up" else -1
    r = evaluate(prod, ts_, px, s)
    if r is None: continue
    ok += 1
    batch.append(("sig", prod, ts_, lab, dr, s) + r)
    if len(batch) >= 20000:
        dst.executemany("insert into recon values (" + ",".join("?" * 20) + ")", batch); batch = []
    if n % 100000 == 0: print(f"  signals {n:,} (usable {ok:,}) {time.time()-t0:.0f}s", flush=True)
if batch: dst.executemany("insert into recon values (" + ",".join("?" * 20) + ")", batch)
dst.commit()
print(f"signals: {n:,} considered, {ok:,} usable ({ok/max(n,1):.1%}) in {time.time()-t0:.0f}s", flush=True)

# ---- baseline: every (product, hour) for products that had signals, both directions -------
t0 = time.time(); sigprods = {r[0] for r in dst.execute("select distinct product_id from recon")}
batch = []; nb = 0
for prod in sigprods:
    ts, o, h, l, c = data[prod]
    for i in range(15, len(ts) - NPATH - 1):
        if ts[i] - ts[i - 14] != 14 * H: continue
        entry_ts = int(ts[i]) + H; entry = float(c[i])
        for s, dr in ((1, "up"), (-1, "down")):
            r = evaluate(prod, entry_ts, entry, s)
            if r is None: continue
            nb += 1
            batch.append(("base", prod, entry_ts, "BASELINE", dr, s) + r)
    if len(batch) >= 20000:
        dst.executemany("insert into recon values (" + ",".join("?" * 20) + ")", batch); batch = []
if batch: dst.executemany("insert into recon values (" + ",".join("?" * 20) + ")", batch)
dst.commit()
print(f"baseline rows: {nb:,} in {time.time()-t0:.0f}s", flush=True)
print("saved", f"{HOME}/analysis/recon.sqlite")
