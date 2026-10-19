"""Study 2b: fixed-range volume profile levels vs placebo lines.

Design is preregistered in docs/developer/VOLUME_PROFILE_STUDY.md (committed
before this script was first run).

  python scripts/move_study/volume_profile_study.py --daily-dir <daily_all> \
      [--archive <candle archive copy>] --out data/move-study
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import continuation_vs_reversal as cs  # noqa: E402
import level_study as ls  # noqa: E402

DAY = cs.DAY
BINS = 100
VALUE_AREA = 0.70
INTERIOR = (5, 94)  # inclusive bin range for nodes
PLACEBO_RATIOS = ls.PLACEBO_RATIOS
SEED = 20261020


# ---------------------------------------------------------------- legs

def causal_legs(pivots: list[dict]) -> list[dict]:
    """Legs as they existed when drawn: emitted whenever the alternating sequence's last element changes."""
    seq, legs = [], []
    for p in sorted(pivots, key=lambda x: (x["confirmed"], x["week"])):
        if seq and seq[-1]["type"] == p["type"]:
            more = p["price"] > seq[-1]["price"] if p["type"] == "high" else p["price"] < seq[-1]["price"]
            if not more:
                continue
            seq[-1] = p
        else:
            seq.append(p)
        if len(seq) >= 2:
            a, b = seq[-2], seq[-1]
            lo, hi = sorted((a["price"], b["price"]))
            if hi > lo:
                legs.append({"low": lo, "high": hi, "start": a["week"], "end": b["week"] + 6,
                             "from": b["confirmed"], "direction": "up" if b["type"] == "high" else "down"})
    return legs


# ---------------------------------------------------------------- profile

def build_profile(lo_bars: np.ndarray, hi_bars: np.ndarray, vol: np.ndarray, L: float, H: float, bins: int = BINS) -> np.ndarray:
    """Spread each bar's volume uniformly over the part of [low, high] inside [L, H]."""
    edges = L + (H - L) * np.arange(bins + 1) / bins
    prof = np.zeros(bins)
    ok = np.isfinite(lo_bars) & np.isfinite(hi_bars) & np.isfinite(vol) & (vol > 0)
    lo_c, hi_c, v = np.clip(lo_bars[ok], L, H), np.clip(hi_bars[ok], L, H), vol[ok]
    span = hi_c - lo_c
    inside = (hi_bars[ok] >= L) & (lo_bars[ok] <= H)
    full = np.where(hi_bars[ok] > lo_bars[ok], hi_bars[ok] - lo_bars[ok], 0.0)
    for a, b, s, f, vv, ins in zip(lo_c, hi_c, span, full, v, inside):
        if not ins:
            continue
        if s <= 0 or f <= 0:  # a point (or a bar touching only an edge): one bin
            j = min(int((a - L) / (H - L) * bins), bins - 1)
            prof[j] += vv if f <= 0 else 0.0
            continue
        overlap = np.clip(np.minimum(b, edges[1:]) - np.maximum(a, edges[:-1]), 0, None)
        prof += vv * overlap / f  # share of the bar's own range; the part outside [L, H] is dropped
    return prof


def poc_index(prof: np.ndarray) -> int:
    return int(np.argmax(prof))  # lowest bin on ties


def value_area(prof: np.ndarray, share: float = VALUE_AREA) -> tuple[int, int]:
    total = prof.sum()
    lo = hi = poc_index(prof)
    acc = prof[lo]
    while acc < share * total and (lo > 0 or hi < len(prof) - 1):
        up = prof[hi + 1] if hi < len(prof) - 1 else -1.0
        down = prof[lo - 1] if lo > 0 else -1.0
        if up >= down:
            hi += 1; acc += prof[hi]
        else:
            lo -= 1; acc += prof[lo]
    return lo, hi


def nodes(prof: np.ndarray) -> tuple[list[float], list[float]]:
    """HVN and LVN node centres as bin-index midpoints (fractional), interior bins only."""
    p80, p20 = np.percentile(prof, 80), np.percentile(prof, 20)
    a, b = INTERIOR
    hv = np.zeros(len(prof), bool); hv[a:b + 1] = prof[a:b + 1] >= p80
    hv_idx = np.where(hv)[0]
    lv = np.zeros(len(prof), bool)
    if len(hv_idx):
        for j in range(a, b + 1):
            if prof[j] <= p20 and hv_idx.min() < j < hv_idx.max():
                lv[j] = True

    def runs(mask):
        out, j = [], 0
        while j < len(mask):
            if mask[j]:
                k = j
                while k + 1 < len(mask) and mask[k + 1]:
                    k += 1
                out.append((j + k) / 2.0)
                j = k + 1
            else:
                j += 1
        return out

    return runs(hv), runs(lv)


def leg_levels(leg: dict, prof: np.ndarray) -> list[dict]:
    if prof.sum() <= 0:
        return []
    L, H = leg["low"], leg["high"]
    w = (H - L) / len(prof)
    mid = lambda j: L + (j + 0.5) * w
    lo, hi = value_area(prof)
    base = {"from": leg["from"], "until": 10**9, "pivot_type": leg["direction"], "ratio": None}
    out = [{**base, "family": "poc", "placebo": False, "price": mid(poc_index(prof))},
           {**base, "family": "vah", "placebo": False, "price": L + (hi + 1) * w},
           {**base, "family": "val", "placebo": False, "price": L + lo * w}]
    hvn, lvn = nodes(prof)
    out += [{**base, "family": "hvn", "placebo": False, "price": mid(j)} for j in hvn]
    out += [{**base, "family": "lvn", "placebo": False, "price": mid(j)} for j in lvn]
    out += [{**base, "family": "range_placebo", "placebo": True, "ratio": r, "price": L + r * (H - L)} for r in PLACEBO_RATIOS]
    return out


# ---------------------------------------------------------------- tests

def run_tests(ar: pd.DataFrame, periods: dict, rng) -> tuple[list, int]:
    first = ar[ar.touch == 1]
    fam = lambda f, side: first[(first.family == f) & (first.side == side)]
    tests = []
    for side in ("below", "above"):
        for k in ls.HORIZONS:
            tests.append(("VP1_poc", side, k, fam("poc", side), fam("range_placebo", side), f"react{k}"))
    for k in ls.HORIZONS:
        tests.append(("VP2_vah", "below", k, fam("vah", "below"), fam("range_placebo", "below"), f"react{k}"))
        tests.append(("VP2_val", "above", k, fam("val", "above"), fam("range_placebo", "above"), f"react{k}"))
    for side in ("below", "above"):
        tests.append(("VP3_break", side, 1, fam("lvn", side), fam("hvn", side), "broke_f"))
        for k in (1, 3):
            tests.append(("VP3_continuation", side, k, fam("lvn", side), fam("hvn", side), f"cont{k}"))
    out = []
    for name, side, k, real, plac, col in tests:
        row = {"name": name, "side": side, "horizon": k, "metric": col}
        for pname, per in periods.items():
            row[pname] = ls.diff_boot(real, plac, col, per, k, rng)
        out.append(row)
    n = len(out)
    surv = 0
    for t in out:
        d = t["discovery"]
        if "p_raw" in d:
            d["p_bonferroni"] = round(min(1.0, d["p_raw"] * n), 4)
            surv += d["p_bonferroni"] < 0.05
    for t in out:
        d, s = t["discovery"], t["test"]
        if "p_raw" in s:
            s["p_bonferroni"] = round(min(1.0, s["p_raw"] * max(1, surv)), 4)
        t["replicates"] = bool("p_bonferroni" in d and "p_bonferroni" in s and d["p_bonferroni"] < 0.05
                               and s["p_bonferroni"] < 0.05 and np.sign(d["diff_pct"]) == np.sign(s["diff_pct"]))
    return out, surv


def hourly_frames(archive: Path) -> dict:
    conn = sqlite3.connect(f"file:{archive.as_posix()}?mode=ro", uri=True)
    h = pd.read_sql_query("SELECT product_id, ts, high, low, volume FROM candles WHERE granularity=3600", conn)
    conn.close()
    return {p: g.sort_values("ts") for p, g in h.groupby("product_id")}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--daily-dir", required=True)
    ap.add_argument("--archive", default=None)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    cs.HORIZONS = ls.HORIZONS
    d = cs.load_daily_dir(Path(args.daily_dir), ls.FIRST, ls.LAST)
    frames: dict = {}
    _, days, _ = cs.build_panel(d, frames)
    close, high, low = frames["close"], frames["high"], frames["low"]
    vol = d.pivot(index="day", columns="product_id", values="vol").reindex(days)
    rng = np.random.default_rng(SEED)

    hourly = hourly_frames(Path(args.archive)) if args.archive else {}
    h_lo, h_hi = ls.day_of("2025-10-02"), ls.day_of("2026-10-10")

    rows, hrows, n_legs, n_hlegs = [], [], 0, 0
    for product in close.columns:
        w = ls.weekly_bars(close[product], high[product], low[product])
        if len(w) < 6:
            continue
        legs = causal_legs(ls.confirmed_pivots(w))
        n_legs += len(legs)
        lo_a, hi_a, v_a = low[product].values, high[product].values, vol[product].values
        levels, hlevels = [], []
        for leg in legs:
            i0, i1 = leg["start"] - days[0], leg["end"] - days[0]
            if i1 < 0 or i0 >= len(days):
                continue
            sl = slice(max(i0, 0), min(i1, len(days) - 1) + 1)
            levels += leg_levels(leg, build_profile(lo_a[sl], hi_a[sl], v_a[sl], leg["low"], leg["high"]))
            if product in hourly and leg["start"] >= h_lo and leg["end"] <= h_hi:
                g = hourly[product]
                m = (g.ts >= leg["start"] * DAY) & (g.ts < (leg["end"] + 1) * DAY)
                if m.sum() >= 24:
                    n_hlegs += 1
                    hl = leg_levels(leg, build_profile(g.low.values[m], g.high.values[m], g.volume.values[m], leg["low"], leg["high"]))
                    dl = leg_levels(leg, build_profile(lo_a[sl], hi_a[sl], v_a[sl], leg["low"], leg["high"]))
                    hlevels += [{**x, "profile": "hourly"} for x in hl if x["family"] in ("poc", "vah", "val", "range_placebo")]
                    hlevels += [{**x, "profile": "daily"} for x in dl if x["family"] in ("poc", "vah", "val")]
        rows += ls.arrivals_for(product, levels, days, hi_a, lo_a)
        for prof_kind in ("hourly", "daily"):
            sub = [x for x in hlevels if x["profile"] == prof_kind]
            for a in ls.arrivals_for(product, sub, days, hi_a, lo_a):
                hrows.append({**a, "profile": prof_kind})

    ar = ls.attach_outcomes(pd.DataFrame(rows), frames, days)
    for k in ls.HORIZONS:
        ar[f"cont{k}"] = -ar[f"react{k}"]
    ar["broke_f"] = ar.broke.astype(float)

    split = ls.day_of(ls.SPLIT)
    periods = {"discovery": (int(days[0]), split - 1), "test": (split, int(days[-1]))}
    tests, surv = run_tests(ar, periods, rng)

    # secondary
    sec = {}
    first = ar[ar.touch == 1]
    for fam_name in ("poc", "vah", "val", "hvn", "lvn", "range_placebo"):
        g = first[first.family == fam_name]
        sec[f"{fam_name} first touch"] = {side: {"n": int(len(x)), "break_rate": round(float(x.broke.mean()), 3) if len(x) else None,
                                                 "react7": ls.describe(x, "react7"), "cont1": ls.describe(x, "cont1")}
                                          for side, x in g.groupby("side")}
    poc = ar[ar.family == "poc"]
    sec["poc retest (2+)"] = {side: ls.describe(x, "react7") for side, x in poc[poc.touch >= 2].groupby("side")}
    for fam_name, side in (("vah", "below"), ("val", "above")):
        for lbl, g in (("real", first[(first.family == fam_name) & (first.side == side)]),
                       ("placebo", first[(first.family == "range_placebo") & (first.side == side)])):
            sec[f"{fam_name} {lbl} by close"] = {("closed beyond" if b else "closed back inside"): ls.describe(x, "react7")
                                                 for b, x in g.groupby("broke")}
    pf = first[first.family == "poc"]
    sec["poc by arrival type"] = {f"{s}, {'shock' if sh else 'grind'}": ls.describe(x, "react7") for (s, sh), x in pf.groupby(["side", "shock"])}
    sec["poc by liquidity"] = {f"{s}, {'<$1M' if th else '>=$1M'}": ls.describe(x, "react7")
                               for (s, th), x in pf.assign(thin=pf.med20 < 1e6).groupby(["side", "thin"])}

    hourly_check = None
    if hrows:
        har = ls.attach_outcomes(pd.DataFrame(hrows), frames, days)
        hf = har[har.touch == 1]
        hourly_check = {"legs": n_hlegs}
        for prof_kind in ("hourly", "daily"):
            g = hf[hf.profile == prof_kind]
            hourly_check[prof_kind] = {f"{f} {s}": ls.describe(x, "react7") for (f, s), x in g.groupby(["family", "side"])}
        plac = hf[(hf.profile == "hourly") & (hf.family == "range_placebo")]
        hourly_check["placebo"] = {s: ls.describe(x, "react7") for s, x in plac.groupby("side")}
        a, b = ls.day_of("2025-10-02"), int(days[-1])
        hourly_check["diff_vs_placebo_7d"] = {
            f"{prof_kind} {f} {s}": ls.diff_boot(hf[(hf.profile == prof_kind) & (hf.family == f) & (hf.side == s)],
                                                 plac[plac.side == s], "react7", (a, b), 7, rng)
            for prof_kind in ("hourly", "daily") for f, s in (("poc", "below"), ("poc", "above"), ("vah", "below"), ("val", "above"))}

    out = {"design": "docs/developer/VOLUME_PROFILE_STUDY.md (preregistered)", "legs": n_legs,
           "liquid_arrivals": int(len(ar)), "first_touches": int((ar.touch == 1).sum()), "tests": len(tests),
           "discovery_survivors": int(surv), "reaction_sign": "positive = price turned back away from the level",
           "primary": tests, "secondary": sec, "hourly_check": hourly_check}
    (Path(args.out) / "volume_profile_study.json").write_text(json.dumps(out, indent=1, default=float) + "\n", encoding="utf-8", newline=cs.LF)
    print({k: out[k] for k in ("legs", "liquid_arrivals", "first_touches", "tests", "discovery_survivors")})
    for t in tests:
        a, b = t["discovery"], t["test"]
        print(t["name"], t["side"], t["horizon"], "| disc", a.get("n_real"), a.get("n_placebo"), a.get("real_mean_pct"), a.get("placebo_mean_pct"),
              a.get("diff_pct"), a.get("p_bonferroni"), "| test", b.get("n_real"), b.get("diff_pct"), b.get("ci95_pct"), b.get("p_bonferroni"),
              "REPL" if t["replicates"] else "")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
