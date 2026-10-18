"""Matched same-coin control: each production signal vs OTHER hours of the SAME coin,
same direction, similar volatility, same BTC trend bucket, 1-7 days away (so the 24h
outcome windows never overlap). Read-only. Uses recon.sqlite built from the candle archive."""
import glob, os, sqlite3
import numpy as np

HOME = os.path.expanduser("~/.moonwalking")
recon = sqlite3.connect(f"{HOME}/analysis/recon.sqlite")
sig = sqlite3.connect("file:" + sorted(glob.glob(f"{HOME}/prod-backup/*/signal_outcomes.sqlite"))[-1] + "?mode=ro", uri=True)
conf = {(p, ts, d, lab): c for p, ts, d, lab, c in
        sig.execute("select product_id, started_ts, direction, read_label, confidence from signal_outcomes where direction in ('up','down')")}
COST = 0.002
def bucket(b):  # BTC 4h move in the trade direction
    return 0 if b < -0.005 else 2 if b > 0.005 else 1

# controls: every (coin, hour, direction) from the unconditional table
ctrl = {}
for p, ts, d, atr, b, nr, r24, mfe, mae in recon.execute(
        "select product_id, ts, direction, atr_pct, btc4h, netR21, r24, mfe, mae from recon where kind='base' and btc4h is not null"):
    ctrl.setdefault((p, d), []).append((ts, atr, bucket(b), nr, r24, mfe, mae))
C = {}
for k, v in ctrl.items():
    a = np.array(sorted(v)); C[k] = a
S, seen = [], set()
for p, ts, lab, d, atr, b, nr, r24, mfe, mae in recon.execute(
        "select product_id, ts, label, direction, atr_pct, btc4h, netR21, r24, mfe, mae from recon where kind='sig' and btc4h is not null"):
    k = (p, d, lab, ts // 14400)
    if k in seen: continue
    seen.add(k); S.append((p, ts, lab, d, atr, bucket(b), nr, r24, mfe, mae))
print(f"signals {len(S):,} (de-duplicated); control pool {sum(len(v) for v in C.values()):,} coin-hours")

rows, unmatched, quality = [], [], []
for p, ts, lab, d, atr, bk, nr, r24, mfe, mae in S:
    a = C.get((p, d))
    if a is None: unmatched.append((p, lab, d, atr)); continue
    lo, hi = np.searchsorted(a[:, 0], [ts - 7 * 86400, ts + 7 * 86400])
    w = a[lo:hi]
    if len(w) == 0: unmatched.append((p, lab, d, atr)); continue
    m = (np.abs(w[:, 0] - ts) >= 86400) & (w[:, 1] >= atr * 0.75) & (w[:, 1] <= atr / 0.75) & (w[:, 2] == bk)
    if m.sum() < 3: unmatched.append((p, lab, d, atr)); continue
    c = w[m]
    quality.append((abs(np.log(c[:, 1] / atr)).mean(), int(m.sum())))
    rows.append((p, ts, lab, d, conf.get((p, ts, d, lab)), nr, c[:, 3].mean(), r24, c[:, 4].mean(), mfe, c[:, 5].mean(), mae, c[:, 6].mean(), int(m.sum())))
print(f"matched: {len(rows):,} signals with >=3 controls ({len(rows)/len(S):.0%}); median controls per signal {int(np.median([r[-1] for r in rows]))}\n")
R = np.array([(r[5], r[6], r[7], r[8], r[9], r[10], r[11], r[12]) for r in rows], float)
lab = np.array([r[2] for r in rows]); dr = np.array([r[3] for r in rows]); cf = np.array([np.nan if r[4] is None else r[4] for r in rows], float)
day = np.array([r[1] // 86400 for r in rows]); days, dinv = np.unique(day, return_inverse=True)
week = np.array([r[1] // (7 * 86400) for r in rows]); weeks, winv = np.unique(week, return_inverse=True)
rng = np.random.default_rng(3)

def excess(m, col_sig, col_ctl, label, width=40):
    n = int(m.sum())
    if n < 150: return
    x = R[m, col_sig] - R[m, col_ctl]
    s = np.bincount(dinv[m], x, len(days)); k = np.bincount(dinv[m], None, len(days)).astype(float)
    bs = []
    for _ in range(300):
        ix = rng.integers(0, len(days), len(days)); kk = k[ix].sum()
        if kk > 0: bs.append(s[ix].sum() / kk)
    se = np.std(bs)
    sw = np.bincount(winv[m], x, len(weeks)); kw = np.bincount(winv[m], None, len(weeks)).astype(float)
    bw = []
    for _ in range(300):
        ix = rng.integers(0, len(weeks), len(weeks)); kk = kw[ix].sum()
        if kk > 0: bw.append(sw[ix].sum() / kk)
    zw = x.mean() / np.std(bw) if np.std(bw) > 0 else float('nan')
    print(f"{label:{width}}{n:>7,}  signal {R[m,col_sig].mean():+.3f}  control {R[m,col_ctl].mean():+.3f}  excess {x.mean():+.3f} (z by day {x.mean()/se:+.1f}, by week {zw:+.1f} over {len(weeks)} weeks)")

print("== Net R (1 ATR stop / 2 ATR target, after 0.2% cost): signal minus its matched same-coin controls ==")
for d in ("up", "down"):
    excess(dr == d, 0, 1, f"ALL {d} signals")
print()
cnt = {}
for l, d in zip(lab, dr): cnt[(l, d)] = cnt.get((l, d), 0) + 1
for (l, d), n in sorted(cnt.items(), key=lambda kv: -kv[1])[:10]:
    excess((lab == l) & (dr == d), 0, 1, f"{str(l)[:28]} {d}")
print("\n== By confidence bucket (net R excess over matched controls) ==")
for d in ("up", "down"):
    for lo, hi in ((50, 60), (60, 72), (72, 85), (85, 95), (95, 101)):
        excess((dr == d) & (cf >= lo) & (cf < hi), 0, 1, f"{d} confidence [{lo},{hi})")
print("\n== Forward 24h return in ATR (signal direction), excess over matched controls ==")
for d in ("up", "down"):
    excess(dr == d, 2, 3, f"ALL {d} signals (24h return)")
print("\n== Best / worst excursion in ATR (MFE, MAE) ==")
excess(np.ones(len(R), bool), 4, 5, "ALL signals: max favourable move")
excess(np.ones(len(R), bool), 6, 7, "ALL signals: max adverse move")

import collections
print("\n== Match quality ==")
q = np.array(quality)
print(f"unmatched signals: {len(unmatched):,} of {len(S):,} ({len(unmatched)/len(S):.1%}); most common unmatched reads: "
      f"{collections.Counter((l, d) for _, l, d, _ in unmatched).most_common(3)}")
print(f"unmatched signals' median ATR%: {np.median([u[3] for u in unmatched])*100:.2f}  (all signals' median {np.median([s_[4] for s_ in S])*100:.2f})")
print(f"average volatility gap between a signal and its controls: {q[:,0].mean()*100:.1f}% (log-ratio); controls per signal: median {int(np.median(q[:,1]))}, 10th percentile {int(np.percentile(q[:,1],10))}")
print("BTC trend bucket is identical by construction; controls are 1-7 days away from the signal, on the same coin and direction.")
