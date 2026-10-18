"""Try to kill the sell-side findings: market-neutral returns, day-clustered error bars,
and placebo shuffles. Usage: python ctrl_tests.py <replay.sqlite>"""
import os, sqlite3, sys
import numpy as np

path = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser("~/.moonwalking/analysis/candle_replay.sqlite")
H = 3600
rows = sqlite3.connect(path).execute(
    "select product_id, ts, range_pos, momentum, vol_ratio, status, atr_pct, ret24, mae, at_support from replay").fetchall()
P = np.array([r[0] for r in rows]); T = np.array([r[1] for r in rows], np.int64)
rp = np.array([r[2] for r in rows], float); mom = np.array([np.nan if r[3] is None else r[3] for r in rows], float)
vr = np.array([np.nan if r[4] is None else r[4] for r in rows], float); st = np.array([r[5] for r in rows])
atr = np.array([r[6] for r in rows], float); ret = np.array([r[7] for r in rows], float); mae = np.array([r[8] for r in rows], float)
sup = np.array([r[9] for r in rows], float)

# BTC forward 24h return at each timestamp (the market control)
cand = sqlite3.connect("file:" + os.path.expanduser("~/.moonwalking/data/candle_archive.sqlite") + "?mode=ro", uri=True)
btc = {int(t): float(c) for t, c in cand.execute("select ts, close from candles where product_id='BTC-USD' and granularity=3600")}
fwd = np.array([btc[t + 23 * H] / btc[t] - 1 if (t in btc and t + 23 * H in btc) else np.nan for t in T])
ok = ~np.isnan(fwd)
P, T, rp, mom, vr, st, atr, ret, mae, sup, fwd = (a[ok] for a in (P, T, rp, mom, vr, st, atr, ret, mae, sup, fwd))
neutral = ret - fwd / atr                       # coin's 24h move minus BTC's, in the coin's own ATR
coins, inv = np.unique(P, return_inverse=True)
def demean(x): m = np.bincount(inv, x) / np.bincount(inv); return x - m[inv]
Xr, Xn, Xm = demean(ret), demean(neutral), demean(mae)
day = (T // 86400); days, dinv = np.unique(day, return_inverse=True)
print(f"{len(P):,} coin-hours, {len(coins)} coins, {len(days)} days\n")

def tests(rp, mom, vr, st, sup):
    down = mom < 0
    return {
        "top band >=85  (fwd return, vs rest)":      (((rp >= 85) & (sup == 0)), (rp < 85), "ret"),
        "'Protect now' status vs clear":              (st == "high", st == "clear", "ret"),
        "vol gate 1.5x, down hours":                  (down & (vr >= 1.5), down & (vr < 1.5), "ret"),
        "vol gate 1.0x, down hours":                  (down & (vr >= 1.0), down & (vr < 1.0), "ret"),
        "near support <15 (drawdown, vs rest)":       ((rp < 15) & (sup == 0), (rp >= 15), "mae"),
    }
def diff(a, b, x): return x[a].mean() - x[b].mean() if a.sum() >= 50 and b.sum() >= 50 else np.nan

obs = tests(rp, mom, vr, st, sup)
rng = np.random.default_rng(7)
print(f"{'finding':40}{'raw':>9}{'BTC-neutral':>13}{'  day-cluster z (raw)':>22}{'   placebo p':>13}")
results = []
for name, (a, b, kind) in obs.items():
    x = Xr if kind == "ret" else Xm
    raw = diff(a, b, x); neu = diff(a, b, Xn) if kind == "ret" else np.nan
    # day-clustered bootstrap: resample whole days
    sa = np.bincount(dinv, np.where(a, x, 0.0), len(days)); na = np.bincount(dinv, a.astype(float), len(days))
    sb = np.bincount(dinv, np.where(b, x, 0.0), len(days)); nb = np.bincount(dinv, b.astype(float), len(days))
    bs = []
    for _ in range(400):
        ix = rng.integers(0, len(days), len(days))
        if na[ix].sum() < 50 or nb[ix].sum() < 50: continue
        bs.append(sa[ix].sum() / na[ix].sum() - sb[ix].sum() / nb[ix].sum())
    z = raw / np.std(bs) if bs else np.nan
    # placebo: shuffle each coin's conditions across its own hours, keep outcomes where they are
    null = []
    for _ in range(150):
        idx = np.arange(len(P))
        for k in range(len(coins)):
            members = np.nonzero(inv == k)[0]
            idx[members] = rng.permutation(members)
        t2 = tests(rp[idx], mom[idx], vr[idx], st[idx], sup[idx])
        a2, b2, _k = t2[name]
        d = diff(a2, b2, x)
        if not np.isnan(d): null.append(d)
    p = (np.sum(np.abs(null) >= abs(raw)) + 1) / (len(null) + 1)
    results.append((name, raw, neu, z, p, np.std(null)))
    print(f"{name:40}{raw:>+9.3f}{neu:>+13.3f}{z:>+22.1f}{p:>13.3f}")
print("\nplacebo noise (std of the effect when conditions are randomly reassigned):",
      {r[0].split('(')[0].strip(): round(r[5], 3) for r in results})
# Benjamini-Hochberg over the five tests (treating placebo p as the p-value)
ps = np.array([r[4] for r in results]); order = np.argsort(ps); m = len(ps)
bh = [(i, ps[i] <= (rank + 1) / m * 0.05) for rank, i in enumerate(order)]
print("survives false-discovery control at 5% (Benjamini-Hochberg across these 5):",
      {results[i][0].split('(')[0].strip(): ok for i, ok in bh})
