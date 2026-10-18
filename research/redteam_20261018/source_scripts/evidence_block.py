# Executed at the end of matched_control.py (shares its variables).
# EVIDENCE STATEMENT: effect estimate, calendar-week interval, match counts, balance.
import collections
print("\n== EVIDENCE: net R excess over matched same-coin controls, with calendar-week intervals ==")
T975 = {1: 12.71, 2: 4.30, 3: 3.18, 4: 2.78, 5: 2.57, 6: 2.45, 7: 2.36, 8: 2.31, 9: 2.26, 10: 2.23, 11: 2.20}
unm = collections.Counter((l, d) for _, l, d, _ in unmatched)
MIXED = "MIXED — NO CLEAR EDGE"
rows_cnt = np.array([r[13] for r in rows], float)

def evidence(name, m, key=None):
    n = int(m.sum()); x = R[m, 0] - R[m, 1]
    wk = [x[winv[m] == w].mean() for w in np.unique(winv[m]) if (winv[m] == w).sum() >= 30]
    k = len(wk); mean = x.mean()
    se = np.std(wk, ddof=1) / np.sqrt(k) if k > 1 else float("nan")
    t = T975.get(k - 1, 1.96); lo, hi = mean - t * se, mean + t * se
    sb = np.bincount(dinv[m], x, len(days)); kb = np.bincount(dinv[m], None, len(days)).astype(float); bs = []
    for _ in range(400):
        ix = rng.integers(0, len(days), len(days)); kk = kb[ix].sum()
        if kk > 0: bs.append(sb[ix].sum() / kk)
    dl, dh = np.percentile(bs, [2.5, 97.5])
    gap = np.log(SA[m]) - np.log(CA[m])
    smd = (np.log(SA[m]).mean() - np.log(CA[m]).mean()) / np.sqrt((np.log(SA[m]).var() + np.log(CA[m]).var()) / 2)
    un = unm[key] if key else sum(v for (l_, d_), v in unm.items() if l_ in (("QUIET FLOW BUILDING", MIXED) if name.startswith("both") else (l_,)))
    print(f"{name:32} matched {n:>6,} / unmatched {un:>5,} | excess {mean:+.3f} R")
    print(f"{'':32} week-block 95% CI [{lo:+.3f}, {hi:+.3f}] over {k} weeks | day-block 95% CI [{dl:+.3f}, {dh:+.3f}]")
    print(f"{'':32} balance: signal ATR vs control ATR {np.mean(gap)*100:+.1f}% (log gap), standardised diff {smd:+.2f}; "
          f"median controls {int(np.median(rows_cnt[m]))}")

for l, d in (("QUIET FLOW BUILDING", "up"), ("QUIET FLOW BUILDING", "down"), (MIXED, "up"), (MIXED, "down")):
    evidence(f"{l[:20]} {d}", (lab == l) & (dr == d), (l, d))
evidence("both demoted reads, pooled", np.isin(lab, ["QUIET FLOW BUILDING", MIXED]))
evidence("ALL signals, pooled", np.ones(len(R), bool))
print("\nHow to read it: a useful advantage would be roughly +0.10 R or more per signal before realistic costs. "
      "An interval whose upper end is below that rules a useful advantage out; one that spans it means the data cannot decide.")
