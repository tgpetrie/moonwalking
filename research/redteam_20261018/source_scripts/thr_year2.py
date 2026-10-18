import os, sqlite3, datetime as dt
import numpy as np
c = sqlite3.connect(os.path.expanduser("~/.moonwalking/analysis/replay_year.sqlite"))
rows = c.execute("select product_id, ts, range_pos, momentum, vol_ratio, status, ret24, mae, at_support, btc30 from replay").fetchall()
P = np.array([r[0] for r in rows]); T = np.array([r[1] for r in rows], float)
rp = np.array([r[2] for r in rows], float); mom = np.array([np.nan if r[3] is None else r[3] for r in rows], float)
vr = np.array([np.nan if r[4] is None else r[4] for r in rows], float); st = np.array([r[5] for r in rows])
ret = np.array([r[6] for r in rows], float); mae = np.array([r[7] for r in rows], float); sup = np.array([r[8] for r in rows], float)
b30 = np.array([np.nan if r[9] is None else r[9] for r in rows], float)
coins, inv = np.unique(P, return_inverse=True)
def demean(x): m = np.bincount(inv, x) / np.bincount(inv); return x - m[inv]
xr, xm = demean(ret), demean(mae)
f = lambda t: dt.datetime.fromtimestamp(t, dt.timezone.utc).strftime("%Y-%m-%d")
print(f"{len(rows):,} coin-hours, {len(coins)} coins, {f(T.min())} -> {f(T.max())}")
print("Forward return and drawdown are in ATR, each coin measured against its own average. Lower forward return = better SELL warning.\n")
down = mom < 0
def eff(m_a, m_b):
    a, b = xr[m_a], xr[m_b]
    if len(a) < 100 or len(b) < 100: return None
    d = a.mean() - b.mean(); return d, d / np.hypot(a.std()/np.sqrt(len(a)), b.std()/np.sqrt(len(b))), len(a), len(b)
def show(label, e):
    print(f"   {label:30}" + ("(too few)" if e is None else f"{e[0]:+.3f} ATR (z{e[1]:+.1f})  n={e[2]:,}/{e[3]:,}"))

def line(name, m):
    n = int(m.sum())
    if n < 150: print(f"{name:34}n={n} (too few)"); return
    a, b = xr[m], xm[m]
    print(f"{name:34}{n:>8,}   fwd return {a.mean():+.3f}±{a.std()/np.sqrt(n):.3f}   drawdown {b.mean():+.3f}±{b.std()/np.sqrt(n):.3f}")

print("== A. Engine status (candle part only) ==")
for s_ in ("high", "watch", "clear"): line(f"status = {s_}", st == s_)
print("\n== B. Range bands ==")
for lo, hi in ((0, 15), (15, 40), (40, 60), (60, 85), (85, 101)): line(f"range position [{lo},{hi})", (rp >= lo) & (rp < hi) & (sup == 0))
line("support breach", sup == 1)
print("\n== C. Volume gate (down hours): forward return, volume-bucket ==")
for lo, hi in ((0, 0.75), (0.75, 1.0), (1.0, 1.25), (1.25, 1.5), (1.5, 2.0), (2.0, 3.0), (3.0, 1e9)):
    line(f"volume {lo}x-{hi if hi<1e8 else 'inf'}x", down & (vr >= lo) & (vr < hi))
print("   gate placement (above minus below, down hours):")
for g in (1.0, 1.25, 1.5, 2.0, 3.0): show(f"gate {g}x", eff(down & (vr >= g), down & (vr < g)))

print("\n== D. Does it hold in every part of the year? ==")
q = np.array([(dt.datetime.fromtimestamp(t, dt.timezone.utc).year, (dt.datetime.fromtimestamp(t, dt.timezone.utc).month - 1) // 3 + 1) for t in T])
for yr, qq in sorted({tuple(x) for x in q.tolist()}):
    m = (q[:, 0] == yr) & (q[:, 1] == qq)
    if m.sum() < 3000: continue
    print(f" {yr} Q{qq}  (n={int(m.sum()):,}, coins' average fwd return {ret[m].mean():+.2f} ATR)")
    show("top band >=85 vs rest", eff(m & (rp >= 85) & (sup == 0), m & (rp < 85)))
    show("support band <15 (drawdown)", None if (m & (rp < 15)).sum() < 100 else (xm[m & (rp < 15)].mean() - xm[m & (rp >= 15)].mean(), 0.0, int((m & (rp < 15)).sum()), int((m & (rp >= 15)).sum())))
    show("gate 1.5x (down hours)", eff(m & down & (vr >= 1.5), m & down & (vr < 1.5)))
    show("status high vs clear", eff(m & (st == "high"), m & (st == "clear")))

print("\n== E. Market regime: BTC's trend over the previous 30 days ==")
for name, lo, hi in (("BTC falling (<-10%)", -9, -0.10), ("BTC flat (-10..+10%)", -0.10, 0.10), ("BTC rising (>+10%)", 0.10, 9)):
    m = (b30 >= lo) & (b30 < hi)
    print(f" {name}  (n={int(m.sum()):,}, avg fwd return {ret[m].mean():+.2f} ATR)")
    show("top band >=85 vs rest", eff(m & (rp >= 85) & (sup == 0), m & (rp < 85)))
    show("gate 1.5x (down hours)", eff(m & down & (vr >= 1.5), m & down & (vr < 1.5)))
    show("gate 1.0x (down hours)", eff(m & down & (vr >= 1.0), m & down & (vr < 1.0)))
    show("status high vs clear", eff(m & (st == "high"), m & (st == "clear")))

print("\n== F. Per coin: is the gate effect a property of the coin? ==")
half = T < np.quantile(T, 0.5); res = []
for k, cn in enumerate(coins):
    m = (inv == k) & down; vals = []
    for h in (half, ~half):
        a, b = xr[m & h & (vr >= 1.5)], xr[m & h & (vr < 1.5)]
        vals.append(a.mean() - b.mean() if len(a) >= 15 and len(b) >= 15 else np.nan)
    if not np.isnan(vals).any(): res.append(vals)
x, y = np.array(res).T; rank = lambda v: np.argsort(np.argsort(v))
print(f"   {len(x)} coins. Rank correlation, first half vs second half: {np.corrcoef(rank(x), rank(y))[0,1]:+.2f}  | same sign in both halves: {np.mean(np.sign(x)==np.sign(y)):.0%}")
