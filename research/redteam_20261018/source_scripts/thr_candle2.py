import os, sqlite3
import numpy as np
c = sqlite3.connect(os.path.expanduser("~/.moonwalking/analysis/candle_replay.sqlite"))
rows = c.execute("select product_id, ts, range_pos, momentum, vol_ratio, status, score, atr_pct, ret24, mae, mfe, at_support from replay").fetchall()
P = np.array([r[0] for r in rows]); T = np.array([r[1] for r in rows], float)
rp = np.array([r[2] for r in rows], float); mom = np.array([np.nan if r[3] is None else r[3] for r in rows], float)
vr = np.array([np.nan if r[4] is None else r[4] for r in rows], float); st = np.array([r[5] for r in rows])
sc = np.array([r[6] for r in rows], float); ret = np.array([r[8] for r in rows], float); mae = np.array([r[9] for r in rows], float)
sup = np.array([r[11] for r in rows], float)
# remove each coin's own average so coin-level drift is not mistaken for a signal effect
coins, inv = np.unique(P, return_inverse=True)
def demean(x):
    m = np.bincount(inv, x) / np.bincount(inv); return x - m[inv]
xr, xm = demean(ret), demean(mae)
print(f"{len(rows):,} coin-hours over {len(coins)} coins. Average forward 24h return {ret.mean():+.2f} ATR, average worst drawdown {mae.mean():.2f} ATR.")
print("Reading guide: for a SELL-side warning, a good flag means lower forward return (negative) and deeper drawdown (positive) than that coin's norm.\n")

def line(name, m, se_only=False):
    n = int(m.sum())
    if n < 150: print(f"{name:34}n={n} (too few)"); return None
    a, b = xr[m], xm[m]
    print(f"{name:34}{n:>7,}   fwd return {a.mean():+.3f}±{a.std()/np.sqrt(n):.3f} ATR   drawdown {b.mean():+.3f}±{b.std()/np.sqrt(n):.3f} ATR")
    return a.mean(), a.std() / np.sqrt(n), n

print("== A. The engine's own 'top risk' status (candle part only; the live-signal points are not reproducible historically) ==")
for s_ in ("high", "watch", "clear"): line(f"status = {s_}", st == s_)
print("\n== B. Range position: the 15 / 85 bands ==")
for lo, hi in ((0, 15), (15, 40), (40, 60), (60, 85), (85, 101)): line(f"range position [{lo},{hi})", (rp >= lo) & (rp < hi) & (sup == 0))
line("price at/below support (breach)", sup == 1)
print("   finer around the top band:")
for lo, hi in ((70, 80), (80, 85), (85, 90), (90, 95), (95, 101)): line(f"   range position [{lo},{hi})", (rp >= lo) & (rp < hi) & (sup == 0))

print("\n== C. The 1.5x volume gate (last hourly candle down, volume vs median of prior 48 hours) ==")
down = mom < 0
for lo, hi in ((0, 0.75), (0.75, 1.0), (1.0, 1.25), (1.25, 1.5), (1.5, 2.0), (2.0, 3.0), (3.0, 1e9)):
    line(f"down hour, volume {lo}x-{hi if hi<1e8 else 'inf'}x", down & (vr >= lo) & (vr < hi))
print("   contrast: UP hours on high volume")
line("up hour, volume >= 1.5x", (mom >= 0) & (vr >= 1.5))
print("\n   Where to put the gate? difference in forward return, above gate minus below gate (down hours); more negative = better warning")
for g in (1.0, 1.25, 1.5, 2.0, 3.0):
    a, b = xr[down & (vr >= g)], xr[down & (vr < g)]
    d = a.mean() - b.mean(); se = np.hypot(a.std()/np.sqrt(len(a)), b.std()/np.sqrt(len(b)))
    d2 = xm[down & (vr >= g)].mean() - xm[down & (vr < g)].mean()
    print(f"   gate {g:>4}x   forward return {d:+.3f} ATR (z{d/se:+.1f})   drawdown {d2:+.3f} ATR   n above/below = {int((down&(vr>=g)).sum()):,}/{int((down&(vr<g)).sum()):,}")

print("\n== D. Stable over time? (down hours, volume >= 1.5x minus < 1.5x, forward return in ATR) ==")
q = np.quantile(T, [1/3, 2/3])
for name, m in (("first third", T < q[0]), ("middle third", (T >= q[0]) & (T < q[1])), ("last third", T >= q[1])):
    a, b = xr[m & down & (vr >= 1.5)], xr[m & down & (vr < 1.5)]
    print(f"   {name:13}{a.mean()-b.mean():+.3f} ATR  (n={len(a):,}/{len(b):,})")

print("\n== E. Per-coin: does the gate effect differ by coin, or is it noise? ==")
half = T < np.quantile(T, 0.5); res = []
for k, cn in enumerate(coins):
    m = (inv == k) & down
    vals = []
    for h in (half, ~half):
        a, b = xr[m & h & (vr >= 1.5)], xr[m & h & (vr < 1.5)]
        vals.append(a.mean() - b.mean() if len(a) >= 12 and len(b) >= 12 else np.nan)
    if not np.isnan(vals).any(): res.append(vals)
x, y = np.array(res).T
rank = lambda v: np.argsort(np.argsort(v))
print(f"   {len(x)} coins with enough hours in both halves. Rank correlation of the effect, first half vs second half: {np.corrcoef(rank(x), rank(y))[0,1]:+.2f}")
print(f"   same sign in both halves: {np.mean(np.sign(x)==np.sign(y)):.0%} of coins (50% would be a coin flip)")
