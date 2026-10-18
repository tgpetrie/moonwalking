"""Confidence cutoffs, matched on volatility and measured before costs."""
import glob, os, sqlite3
import numpy as np

HOME = os.path.expanduser("~/.moonwalking")
recon = sqlite3.connect(f"{HOME}/analysis/recon.sqlite")
sig = sqlite3.connect("file:" + sorted(glob.glob(f"{HOME}/prod-backup/*/signal_outcomes.sqlite"))[-1] + "?mode=ro", uri=True)
conf = {(p, ts, d, lab): c for p, ts, d, lab, c in
        sig.execute("select product_id, started_ts, direction, read_label, confidence from signal_outcomes where direction in ('up','down')")}

COST = 0.002
S, B, seen = [], [], set()
for kind, p, ts, lab, d, atr, nr, res, r24 in recon.execute(
        "select kind, product_id, ts, label, direction, atr_pct, netR21, res21, r24 from recon"):
    gross = nr + COST / atr                    # undo the cost (S = 1 ATR, so cost in R = cost / atr_pct)
    s = 1 if d == "up" else -1
    if kind == "base": B.append((s, atr, gross, nr, r24)); continue
    c = conf.get((p, ts, d, lab))
    if c is None: continue
    k = (p, d, ts // 7200)
    if k in seen: continue
    seen.add(k); S.append((s, atr, gross, nr, r24, c, ts, p))
Bs = np.array(B); Ss = np.array([x[:7] for x in S], dtype=float)
sp = np.array([x[7] for x in S])
# volatility-matched baseline: mean gross R of unconditional entries in the same direction and ATR% quintile
edges = np.quantile(Bs[:, 1], [0.2, 0.4, 0.6, 0.8])
def cell(atr): return np.searchsorted(edges, atr)
base_gross = {(s, q): Bs[(Bs[:, 0] == s) & (cell(Bs[:, 1]) == q), 2].mean() for s in (1, -1) for q in range(5)}
base_net = {(s, q): Bs[(Bs[:, 0] == s) & (cell(Bs[:, 1]) == q), 3].mean() for s in (1, -1) for q in range(5)}
q = cell(Ss[:, 1])
Ss = np.c_[Ss, [base_gross[(int(s), int(qq))] for s, qq in zip(Ss[:, 0], q)], [base_net[(int(s), int(qq))] for s, qq in zip(Ss[:, 0], q)]]
# columns: 0 s, 1 atr, 2 gross, 3 net, 4 r24, 5 conf, 6 ts, 7 base_gross_cell, 8 base_net_cell
ex_g = Ss[:, 2] - Ss[:, 7]; ex_n = Ss[:, 3] - Ss[:, 8]
c = Ss[:, 5]
print(f"signals {len(Ss):,} | median ATR% of signals {np.median(Ss[:,1])*100:.2f} vs baseline {np.median(Bs[:,1])*100:.2f}")
print("median ATR% by confidence bucket:", {f"{lo}-{hi}": round(float(np.median(Ss[(c>=lo)&(c<hi),1]))*100, 2)
      for lo, hi in ((50,60),(60,72),(72,85),(85,95),(95,101)) if ((c>=lo)&(c<hi)).sum()})
print("\nExcess over a volatility-matched random entry (same direction, same ATR% quintile), in R:")
print(f"{'bucket':14}{'n':>8}  {'gross (no cost)':>22}  {'net of 0.2% cost':>22}")
def line(name, m):
    n = int(m.sum())
    if n < 100: return
    g, gs = ex_g[m].mean(), ex_g[m].std() / np.sqrt(n); nn, ns = ex_n[m].mean(), ex_n[m].std() / np.sqrt(n)
    print(f"{name:14}{n:>8,}  {g:+8.3f} ±{gs:.3f} (z{g/gs:+5.1f})  {nn:+8.3f} ±{ns:.3f} (z{nn/ns:+5.1f})")
for dn, ds in (("UP", 1), ("DOWN", -1)):
    print(f"-- {dn}")
    for lo, hi in ((50,60),(60,72),(72,85),(85,95),(95,101)):
        line(f"[{lo},{hi})", (Ss[:, 0] == ds) & (c >= lo) & (c < hi))
print("-- the two lines (gross, both directions pooled, matched)")
def d_(label, m1, m2):
    a, b = ex_g[m1], ex_g[m2]; d = a.mean() - b.mean(); se = np.hypot(a.std()/np.sqrt(len(a)), b.std()/np.sqrt(len(b)))
    print(f"   {label:40}{d:+.3f} R (z{d/se:+.1f})  n={len(a):,}/{len(b):,}")
d_(">=85 minus 72-84", c >= 85, (c >= 72) & (c < 85)); d_(">=72 minus <72", c >= 72, c < 72); d_("72-84 minus 60-71", (c>=72)&(c<85), (c>=60)&(c<72))

print("\n== Is the step at 72 stable over time? (matched gross excess, >=72 minus <72) ==")
tcut = np.quantile(Ss[:, 6], [1/3, 2/3])
for name, m in (("first third", Ss[:, 6] < tcut[0]), ("middle third", (Ss[:, 6] >= tcut[0]) & (Ss[:, 6] < tcut[1])), ("last third", Ss[:, 6] >= tcut[1])):
    a, b = ex_g[m & (c >= 72)], ex_g[m & (c < 72)]
    print(f"   {name:13}{a.mean()-b.mean():+.3f} R   (n={len(a):,} vs {len(b):,})")

print("\n== Per-coin: does the confidence effect differ by coin, or is that noise? ==")
coins, counts = np.unique(sp, return_counts=True)
big = [cn for cn, k in zip(coins, counts) if k >= 150]
half = Ss[:, 6] < np.quantile(Ss[:, 6], 0.5)
rows = []
for cn in big:
    m = sp == cn
    vals = []
    for h in (half, ~half):
        a, b = ex_g[m & h & (c >= 72)], ex_g[m & h & (c < 72)]
        vals.append(a.mean() - b.mean() if len(a) >= 15 and len(b) >= 15 else np.nan)
    rows.append((cn, vals[0], vals[1], int(m.sum())))
rows = [r for r in rows if not np.isnan(r[1]) and not np.isnan(r[2])]
x = np.array([r[1] for r in rows]); y = np.array([r[2] for r in rows])
rank = lambda v: np.argsort(np.argsort(v))
rho = np.corrcoef(rank(x), rank(y))[0, 1]
print(f"   {len(rows)} coins with enough signals in both halves. Rank correlation of the (>=72 vs <72) effect, first half vs second half: {rho:+.2f}")
print(f"   (about 0 means a coin's effect in one half says nothing about the other, so per-coin tuning would be fitting noise)")
print(f"   share of coins where >=72 beat <72 in BOTH halves: {np.mean((x>0)&(y>0)):.0%} | in neither: {np.mean((x<=0)&(y<=0)):.0%} | split: {np.mean((x>0)!=(y>0)):.0%}")
