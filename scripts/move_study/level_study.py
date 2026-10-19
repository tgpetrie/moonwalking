"""Study 2: arrival at confirmed highs/lows and macro ratios vs placebo levels.

Design is preregistered in docs/developer/LEVEL_STUDY.md (committed before
this script was first run). Reads the daily pull written by fetch_daily_all.py.

  python scripts/move_study/level_study.py --daily-dir <daily_all> --out data/move-study
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import continuation_vs_reversal as cs  # noqa: E402

DAY = cs.DAY
FIRST, LAST, SPLIT = "2022-01-03", "2026-10-17", "2025-01-01"
HORIZONS = (1, 3, 7, 14)
FIB = (0.5, 0.618, 0.786)
PLACEBO_RATIOS = (0.37, 0.44, 0.56, 0.67, 0.73, 0.83)
SEED = 20261019
BOOT = 4000


def day_of(text: str) -> int:
    return int(pd.Timestamp(text, tz="UTC").timestamp() // DAY)


# ---------------------------------------------------------------- pivots

def weekly_bars(close: pd.Series, high: pd.Series, low: pd.Series) -> pd.DataFrame:
    """Complete Monday weeks (all 7 days traded) from one product's daily series."""
    df = pd.DataFrame({"close": close, "high": high, "low": low}).dropna()
    if df.empty:
        return df
    df["week"] = ((df.index.values + 3) // 7) * 7 - 3  # Monday's day number
    g = df.groupby("week")
    w = pd.DataFrame({"high": g.high.max(), "low": g.low.min(), "n": g.close.size()})
    return w[w.n == 7]


def confirmed_pivots(weeks: pd.DataFrame, left: int = 2, right: int = 2) -> list[dict]:
    """Strict weekly swing highs/lows with contiguous neighbours, as in Codex's engine."""
    out, idx = [], weeks.index.values
    H, L = weeks.high.values, weeks.low.values
    for i in range(left, len(weeks) - right):
        win = idx[i - left: i + right + 1]
        if not np.all(np.diff(win) == 7):
            continue
        peers = [j for j in range(i - left, i + right + 1) if j != i]
        hi, lo = all(H[i] > H[j] for j in peers), all(L[i] < L[j] for j in peers)
        if hi == lo:  # neither, or both (ambiguous)
            continue
        out.append({"type": "high" if hi else "low", "price": float(H[i] if hi else L[i]),
                    "week": int(idx[i]), "confirmed": int(idx[i + right] + 7)})
    return out


def macro_versions(pivots: list[dict]) -> list[dict]:
    """As-of macro range: highest confirmed high, then lowest confirmed low after it."""
    versions, seen = [], []
    for p in sorted(pivots, key=lambda x: (x["confirmed"], x["week"])):
        seen.append(p)
        highs = [q for q in seen if q["type"] == "high"]
        if not highs:
            continue
        h = max(highs, key=lambda q: (q["price"], -q["week"]))
        lows = [q for q in seen if q["type"] == "low" and q["week"] > h["week"]]
        if not lows:
            continue
        l = min(lows, key=lambda q: (q["price"], q["week"]))
        if l["price"] >= h["price"]:
            continue
        key = (h["week"], l["week"])
        if versions and versions[-1]["key"] == key:
            continue
        versions.append({"key": key, "high": h["price"], "low": l["price"], "from": p["confirmed"]})
    for a, b in zip(versions, versions[1:]):
        a["until"] = b["from"]
    if versions:
        versions[-1]["until"] = 10**9
    return versions


def build_levels(pivots: list[dict], rng: np.random.Generator) -> list[dict]:
    levels = []
    for p in pivots:
        levels.append({"family": "pivot", "placebo": False, "ratio": None, "price": p["price"], "from": p["confirmed"], "until": 10**9, "pivot_type": p["type"]})
        u = rng.uniform(0.03, 0.15) * rng.choice([-1.0, 1.0])
        levels.append({"family": "pivot", "placebo": True, "ratio": None, "price": p["price"] * (1 + u), "from": p["confirmed"], "until": 10**9, "pivot_type": p["type"]})
    for v in macro_versions(pivots):
        span = v["high"] - v["low"]
        for r in (0.0, 1.0):
            levels.append({"family": "anchor", "placebo": False, "ratio": r, "price": v["low"] + r * span, "from": v["from"], "until": v["until"], "pivot_type": None})
        for r in FIB:
            levels.append({"family": "fib", "placebo": False, "ratio": r, "price": v["low"] + r * span, "from": v["from"], "until": v["until"], "pivot_type": None})
        for r in PLACEBO_RATIOS:
            levels.append({"family": "fib", "placebo": True, "ratio": r, "price": v["low"] + r * span, "from": v["from"], "until": v["until"], "pivot_type": None})
    return levels


# ---------------------------------------------------------------- arrivals

def arrivals_for(product: str, levels: list[dict], days: np.ndarray, hi: np.ndarray, lo: np.ndarray) -> list[dict]:
    """Daily bars t with t-1 consecutive; from below High[t-1] < level <= High[t]; from above Low[t-1] > level >= Low[t]."""
    if not levels:
        return []
    price = np.array([lv["price"] for lv in levels])[:, None]
    start = np.array([lv["from"] for lv in levels])[:, None]
    stop = np.array([lv["until"] for lv in levels])[:, None]
    ok_prev = np.isfinite(hi[:-1]) & np.isfinite(hi[1:])
    d = days[1:][None, :]
    live = (d >= start) & (d < stop) & ok_prev[None, :]
    below = live & (hi[:-1][None, :] < price) & (hi[1:][None, :] >= price)
    above = live & (lo[:-1][None, :] > price) & (lo[1:][None, :] <= price)
    out = []
    for i, lv in enumerate(levels):
        hit = np.where(below[i] | above[i])[0]
        for n, j in enumerate(hit, 1):
            out.append({"product": product, "day": int(days[j + 1]), "side": "below" if below[i, j] else "above",
                        "family": lv["family"], "placebo": lv["placebo"], "ratio": lv["ratio"], "level": float(price[i, 0]),
                        "touch": n, "pivot_type": lv["pivot_type"]})
    return out


# ---------------------------------------------------------------- stats

def diff_boot(real: pd.DataFrame, plac: pd.DataFrame, col: str, period: tuple[int, int], k: int, rng) -> dict:
    a, b = period
    r = real[(real.day >= a) & (real.day + k <= b) & real[col].notna()]
    p = plac[(plac.day >= a) & (plac.day + k <= b) & plac[col].notna()]
    if len(r) < 20 or len(p) < 20:
        return {"n_real": int(len(r)), "n_placebo": int(len(p)), "note": "too few"}
    n = b - a + 1

    def daily(x):
        idx = x.day.values - a
        return np.bincount(idx, weights=x[col].values, minlength=n), np.bincount(idx, minlength=n).astype(float)

    rs, rc = daily(r)
    ps, pc = daily(p)
    obs = rs.sum() / rc.sum() - ps.sum() / pc.sum()
    B = cs.BLOCK
    nb = int(np.ceil(n / B))
    st = rng.integers(0, max(1, n - B + 1), size=(BOOT, nb))
    ix = (st[:, :, None] + np.arange(B)[None, None, :]).reshape(BOOT, -1)[:, :n]
    rr, rcc, pp, pcc = rs[ix].sum(1), rc[ix].sum(1), ps[ix].sum(1), pc[ix].sum(1)
    ok = (rcc > 0) & (pcc > 0)
    bd = rr[ok] / rcc[ok] - pp[ok] / pcc[ok]
    lo, hi = np.percentile(bd, [2.5, 97.5])
    pval = 2 * min((bd <= 0).mean(), (bd >= 0).mean())
    return {"n_real": int(len(r)), "n_placebo": int(len(p)), "real_mean_pct": round(float(r[col].mean()) * 100, 2),
            "placebo_mean_pct": round(float(p[col].mean()) * 100, 2), "diff_pct": round(float(obs) * 100, 2),
            "ci95_pct": [round(lo * 100, 2), round(hi * 100, 2)], "p_raw": round(max(float(pval), 1 / BOOT), 5)}


def describe(x: pd.DataFrame, col: str) -> dict:
    v = x[col].dropna()
    return {"n": int(len(v)), "mean_pct": round(float(v.mean()) * 100, 2) if len(v) else None,
            "median_pct": round(float(v.median()) * 100, 2) if len(v) else None}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--daily-dir", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    cs.HORIZONS = HORIZONS
    d = cs.load_daily_dir(Path(args.daily_dir), FIRST, LAST)
    frames: dict = {}
    _, days, _ = cs.build_panel(d, frames)
    close, high, low = frames["close"], frames["high"], frames["low"]
    rng = np.random.default_rng(SEED)

    rows, n_pivots, n_levels = [], 0, 0
    for product in close.columns:
        w = weekly_bars(close[product], high[product], low[product])
        if len(w) < 6:
            continue
        piv = confirmed_pivots(w)
        n_pivots += len(piv)
        levels = build_levels(piv, rng)
        n_levels += len(levels)
        rows += arrivals_for(product, levels, days, high[product].values, low[product].values)
    ar = pd.DataFrame(rows)

    # outcomes and conditions
    pos = {p: i for i, p in enumerate(close.columns)}
    di = (ar.day.values - days[0]).astype(int)
    ci = ar["product"].map(pos).values
    get = lambda frame: frame.values[di, ci]
    ar["liquid"] = get(frames["liquid"]).astype(bool)
    ar["med20"] = get(frames["med20"])
    ar["vol_ratio"] = get(frames["vol_ratio"])
    ar["ret1"] = get(frames["ret1"])
    ar["btc"] = frames["btc_ret"].values[di]
    c_t = get(close)
    sign = np.where(ar.side == "below", -1.0, 1.0)
    for k in HORIZONS:
        ar[f"react{k}"] = sign * get(frames["fwd_vm"][k])
        fut = close.shift(-k).values[di, ci]
        ar[f"react_lvl{k}"] = sign * (fut / ar.level.values - 1 - get(frames["peer"][k]))
    ar["broke"] = np.where(ar.side == "below", c_t > ar.level, c_t < ar.level)
    ar["shock"] = np.where(ar.side == "below", (ar.ret1 >= 0.10) & (ar.vol_ratio >= 5) & (ar.ret1 - ar.btc >= 0.15),
                           (ar.ret1 <= -0.10) & (ar.vol_ratio >= 5) & (ar.btc - ar.ret1 >= 0.15))
    ar = ar[ar.liquid].copy()

    split = day_of(SPLIT)
    periods = {"discovery": (int(days[0]), split - 1), "test": (split, int(days[-1]))}
    first = ar[ar.touch == 1]
    fam = {
        "P1_pivot": (lambda s: first[(first.family == "pivot") & ~first.placebo & (first.side == s)],
                     lambda s: first[(first.family == "pivot") & first.placebo & (first.side == s)]),
        "P2_fib": (lambda s: first[(first.family == "fib") & ~first.placebo & (first.side == s)],
                   lambda s: first[(first.family == "fib") & first.placebo & (first.side == s)]),
        "P3_anchor": (lambda s: first[(first.family == "anchor") & (first.side == s) & (first.ratio == (1.0 if s == "below" else 0.0))],
                      lambda s: first[(first.family == "pivot") & first.placebo & (first.side == s)]),
    }
    tests = []
    for name, (real_f, plac_f) in fam.items():
        for side in ("below", "above"):
            for k in HORIZONS:
                row = {"family": name, "side": side, "horizon": k}
                for pname, per in periods.items():
                    row[pname] = diff_boot(real_f(side), plac_f(side), f"react{k}", per, k, rng)
                tests.append(row)
    n_tests = len(tests)
    surv = 0
    for t in tests:
        dsc = t["discovery"]
        if "p_raw" in dsc:
            dsc["p_bonferroni"] = round(min(1.0, dsc["p_raw"] * n_tests), 4)
            surv += dsc["p_bonferroni"] < 0.05
    for t in tests:
        dsc, tst = t["discovery"], t["test"]
        if "p_raw" in tst:
            tst["p_bonferroni"] = round(min(1.0, tst["p_raw"] * max(1, surv)), 4)
        t["replicates"] = bool("p_bonferroni" in dsc and "p_bonferroni" in tst and dsc["p_bonferroni"] < 0.05
                               and tst["p_bonferroni"] < 0.05 and np.sign(dsc["diff_pct"]) == np.sign(tst["diff_pct"]))

    # secondary, descriptive
    sec = {}
    real = ar[~ar.placebo]
    for label, sub in {"pivot first touch": real[(real.family == "pivot") & (real.touch == 1)],
                       "pivot retest (2+)": real[(real.family == "pivot") & (real.touch >= 2)],
                       "pivot placebo first touch": ar[(ar.family == "pivot") & ar.placebo & (ar.touch == 1)],
                       "fib first touch": real[(real.family == "fib") & (real.touch == 1)],
                       "fib placebo first touch": ar[(ar.family == "fib") & ar.placebo & (ar.touch == 1)]}.items():
        sec[label] = {side: {"break_rate": round(float(g.broke.mean()), 3) if len(g) else None,
                             **{f"react{k}": describe(g, f"react{k}") for k in (1, 7)},
                             "react7_from_level_price": describe(g, "react_lvl7")}
                      for side, g in sub.groupby("side")}
    pv = real[(real.family == "pivot") & (real.touch == 1)]
    sec["pivot first touch by arrival type"] = {f"{side}, {'shock' if sh else 'grind'}": describe(g, "react7")
                                                for (side, sh), g in pv.groupby(["side", "shock"])}
    sec["pivot first touch by liquidity"] = {f"{side}, {'<$1M' if lq else '>=$1M'}": describe(g, "react7")
                                             for (side, lq), g in pv.assign(thin=pv.med20 < 1e6).groupby(["side", "thin"])}

    out = {"design": "docs/developer/LEVEL_STUDY.md (preregistered)", "pivots": n_pivots, "levels": n_levels,
           "liquid_arrivals": int(len(ar)), "first_touch_arrivals": int(len(first)), "tests": n_tests,
           "discovery_survivors": int(surv), "reaction_sign": "positive = price turned back away from the level",
           "primary": tests, "secondary": sec}
    (Path(args.out) / "level_study.json").write_text(json.dumps(out, indent=1, default=float) + "\n", encoding="utf-8", newline=cs.LF)
    print({k: out[k] for k in ("pivots", "levels", "liquid_arrivals", "first_touch_arrivals", "tests", "discovery_survivors")})
    for t in tests:
        a, b = t["discovery"], t["test"]
        print(t["family"], t["side"], t["horizon"], "| disc", a.get("n_real"), a.get("real_mean_pct"), a.get("placebo_mean_pct"), a.get("diff_pct"), a.get("p_bonferroni"),
              "| test", b.get("n_real"), b.get("diff_pct"), b.get("ci95_pct"), b.get("p_bonferroni"), "REPL" if t["replicates"] else "")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
