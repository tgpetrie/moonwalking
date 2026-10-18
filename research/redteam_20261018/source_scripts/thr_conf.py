"""Confidence cutoffs (85 vs 72) and per-coin persistence, on production signals."""
import glob, os, sqlite3
import numpy as np

HOME = os.path.expanduser("~/.moonwalking")
recon = sqlite3.connect(f"{HOME}/analysis/recon.sqlite")
sig = sqlite3.connect("file:" + sorted(glob.glob(f"{HOME}/prod-backup/*/signal_outcomes.sqlite"))[-1] + "?mode=ro", uri=True)

# ---- attach confidence to the ATR-reconstructed signals ------------------------------
conf = {}
for p, ts, d, lab, c in sig.execute("select product_id, started_ts, direction, read_label, confidence from signal_outcomes "
                                    "where direction in ('up','down')"):
    conf[(p, ts, d, lab)] = c
rows = recon.execute("select kind, product_id, ts, label, direction, netR21, res21, mfe, mae, r24 from recon").fetchall()
S, B = [], []
seen = set()
for kind, p, ts, lab, d, nr, res, mfe, mae, r24 in rows:
    if kind == "base": B.append((p, ts, d, nr, res)); continue
    c = conf.get((p, ts, d, lab))
    if c is None: continue
    k = (p, d, ts // 7200)                      # one signal per coin, direction, 2h block (the first)
    if k in seen: continue
    seen.add(k); S.append((p, ts, d, c, nr, res, mfe, mae, r24))
print(f"ATR-reconstructed signals with confidence: {len(S):,} (de-duplicated to one per coin/direction/2h)")
S = np.array([(0, ts, 1 if d == "up" else -1, c, nr, res) for p, ts, d, c, nr, res, *_ in S], dtype=float)
coins = np.array([x[0] for x in rows if False])  # placeholder (kept simple)
base = {1: np.mean([nr for p, ts, d, nr, res in B if d == "up"]), -1: np.mean([nr for p, ts, d, nr, res in B if d == "down"])}
print(f"baseline net R (2:1): up {base[1]:+.3f}  down {base[-1]:+.3f}\n")

def row(name, m):
    if m.sum() == 0: print(f"{name:26}(none)"); return None
    r = S[m, 4]; n = len(r); mean = r.mean(); se = r.std() / np.sqrt(n)
    ref = np.where(S[m, 2] == 1, base[1], base[-1]).mean()
    print(f"{name:26}{n:>8,}  tgt2:1 {(S[m,5]==1).mean():5.1%}  netR {mean:+.3f}±{se:.3f}  vs baseline {mean-ref:+.3f} (z={(mean-ref)/se:+.1f})")
    return mean, se, n

for dname, ds in (("UP signals", 1), ("DOWN signals", -1)):
    print(f"== {dname}: by confidence bucket (net R, 24h ATR geometry) ==")
    for lo, hi in ((0, 50), (50, 60), (60, 72), (72, 85), (85, 95), (95, 101)):
        row(f"confidence [{lo},{hi})", (S[:, 2] == ds) & (S[:, 3] >= lo) & (S[:, 3] < hi))
    print()
print("== The two lines in question (both directions pooled, difference in net R) ==")
def diff(label, m1, m2):
    a, b = S[m1, 4], S[m2, 4]
    d = a.mean() - b.mean(); se = np.hypot(a.std() / np.sqrt(len(a)), b.std() / np.sqrt(len(b)))
    print(f"{label:46} {d:+.3f} R  (z={d/se:+.1f}; n={len(a):,} vs {len(b):,})")
c = S[:, 3]
diff(">=85  minus  72-84", c >= 85, (c >= 72) & (c < 85))
diff(">=85  minus  <72", c >= 85, c < 72)
diff(">=72  minus  <72", c >= 72, c < 72)
diff(">=65  minus  <65 (held-coin notify line)", c >= 65, c < 65)
print("\n== Cutoff curve: average net R of signals at or above each confidence ==")
print("  cutoff:  " + "".join(f"{x:>8}" for x in range(50, 100, 5)))
for dname, ds in (("up", 1), ("down", -1)):
    vals = []
    for x in range(50, 100, 5):
        m = (S[:, 2] == ds) & (c >= x); vals.append(f"{S[m,4].mean():+8.3f}" if m.sum() > 200 else "     n/a")
    print(f"  {dname:6}   " + "".join(vals))

# ---- live 60-minute returns over the whole history: more data, same question ---------
print("\n== Same question on ALL production history, live 60-minute directional return, net of 0.2% ==")
seen = set(); bk = {}
for p, ts, d, c_, r60, last in sig.execute("select product_id, started_ts, direction, confidence, return_60m, last_ts from signal_outcomes "
                                           "where complete=1 and return_60m is not null and direction in ('up','down') and (last_ts - started_ts) <= 3900"):
    k = (p, d, ts // 7200)
    if k in seen: continue
    seen.add(k)
    b = 0 if c_ < 50 else 1 if c_ < 60 else 2 if c_ < 72 else 3 if c_ < 85 else 4 if c_ < 95 else 5
    bk.setdefault((d, b), []).append(r60 - 0.2)
names = ["<50", "50-59", "60-71", "72-84", "85-94", "95+"]
for d in ("up", "down"):
    print(f"  {d:5}", "  ".join(f"{names[b]}: {np.mean(bk[(d,b)]):+.3f}% (n={len(bk[(d,b)]):,})" for b in range(6) if (d, b) in bk and len(bk[(d, b)]) > 50))
