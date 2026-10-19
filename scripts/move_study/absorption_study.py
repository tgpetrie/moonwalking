"""Study 2c: hourly two-step absorption/exhaustion triggers, and breakdowns at macro lows / VAL.

Design is preregistered in docs/developer/ABSORPTION_STUDY.md (committed before
this script was first run).

  python scripts/move_study/absorption_study.py --daily-dir <daily_all> --archive <archive copy> --out data/move-study
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
import volume_profile_study as vp  # noqa: E402

DAY, HOUR = cs.DAY, 3600
H_FIRST, H_LAST, H_SPLIT = "2025-10-02", "2026-10-10", "2026-04-01"
HORIZON_DAYS = (1, 3, 7)
NEAR = 0.01
SEED = 20261021


# ---------------------------------------------------------------- triggers

def find_triggers(g: pd.DataFrame) -> list[dict]:
    """Two-step triggers for one product's hourly candles (sorted by ts)."""
    ts, o, h, l, c, v = (g[k].values for k in ("ts", "open", "high", "low", "close", "volume"))
    n = len(ts)
    if n < 30:
        return []
    s = pd.Series
    prior_low = s(l).shift(1).rolling(24).min().values
    prior_high = s(h).shift(1).rolling(24).max().values
    prior_vol = s(v).shift(1).rolling(24).median().values
    consec24 = np.zeros(n, bool)
    consec24[24:] = (ts[24:] - ts[:-24]) == 24 * HOUR
    rng_ = h - l
    with np.errstate(invalid="ignore", divide="ignore"):
        pos = np.where(rng_ > 0, (c - l) / rng_, np.nan)
        low_wick = np.where(rng_ > 0, (np.minimum(o, c) - l) / rng_, np.nan)
        up_wick = np.where(rng_ > 0, (h - np.maximum(o, c)) / rng_, np.nan)
    base = consec24 & (rng_ > 0) & (v >= 2 * prior_vol) & (prior_vol > 0)
    bull1 = base & (l < prior_low) & (low_wick >= 0.4) & (pos >= 0.5)
    bear1 = base & (h > prior_high) & (up_wick >= 0.4) & (pos <= 0.5)
    out = []
    for i in np.where(bull1 | bear1)[0]:
        bull = bool(bull1[i])
        for j in range(1, 5):
            k = i + j
            if k >= n or ts[k] - ts[i] != j * HOUR:
                break
            if bull:
                if l[k] <= l[i]:
                    break  # traded through bar 1's low: no trigger
                if l[k] < o[k] and c[k] > o[k] and c[k] > c[i]:
                    out.append({"bar1": int(ts[i]), "ts": int(ts[k]), "direction": "bull", "ref": float(l[i]), "entry": float(c[k])})
                    break
            else:
                if h[k] >= h[i]:
                    break
                if h[k] > o[k] and c[k] < o[k] and c[k] < c[i]:
                    out.append({"bar1": int(ts[i]), "ts": int(ts[k]), "direction": "bear", "ref": float(h[i]), "entry": float(c[k])})
                    break
    kept, last = [], {}
    for t in sorted(out, key=lambda x: x["ts"]):
        if t["direction"] in last and t["ts"] - last[t["direction"]] < 24 * HOUR:
            continue
        last[t["direction"]] = t["ts"]
        kept.append(t)
    return kept


# ---------------------------------------------------------------- outcomes

class Peers:
    """Same-window, same-volatility-quintile average return of liquid coins (hourly closes)."""

    def __init__(self, closes: pd.DataFrame, liquid: pd.DataFrame, vol_q: pd.DataFrame):
        self.c = closes
        self.liquid, self.vol_q = liquid, vol_q
        self.cols = list(closes.columns)

    def rel(self, product: str, t0: int, t1: int, day: int) -> float:
        """Relative return from the close of the candle opening at t0 to the one opening at t1."""
        try:
            a, b = self.c.loc[t0], self.c.loc[t1]
        except KeyError:
            return np.nan
        r = (b / a - 1).replace([np.inf, -np.inf], np.nan)
        if not np.isfinite(r.get(product, np.nan)):
            return np.nan
        try:
            q = self.vol_q.loc[day, product]
            liq = self.liquid.loc[day].reindex(r.index).fillna(False).astype(bool)
            same = (self.vol_q.loc[day].reindex(r.index) == q)
        except KeyError:
            return np.nan
        if not np.isfinite(q):
            return np.nan
        peer = r[liq & same].dropna()
        if len(peer) < 5:
            return np.nan
        lo, hi = peer.quantile([0.01, 0.99])
        return float(np.clip(r[product], lo, hi) - peer.clip(lo, hi).mean())


def winsorise(x: pd.Series) -> pd.Series:
    lo, hi = x.quantile([0.01, 0.99])
    return x.clip(lo, hi)


def bootstrap_mean(ev: pd.DataFrame, col: str, period: tuple[int, int], k: int, days: np.ndarray, rng) -> dict:
    out = cs.summarise(ev.rename(columns={col: f"z{k}"}), days, k, period, rng, "z")
    return {key: out.get(key) for key in ("events", "mean_excess_pct", "ci95_pct", "median_excess_pct", "p_raw", "note")}


# ---------------------------------------------------------------- levels per product

def product_levels(w: pd.DataFrame, rng) -> dict:
    piv = ls.confirmed_pivots(w)
    lv = ls.build_levels(piv, rng)  # same call order as Study 2, so pivot shadows match it
    return {"piv": piv, "levels": lv}


def classify(trig: dict, day: int, lv: list[dict], legs: list[dict]) -> str:
    """'real', 'placebo', 'open' or 'both' for a trigger's reference price on a day."""
    p, bull = trig["ref"], trig["direction"] == "bull"
    near = lambda x: abs(p / x - 1) <= NEAR
    real = plac = False
    want_type = "low" if bull else "high"
    for x in lv:
        if x["from"] > day or x["family"] != "pivot" or x["pivot_type"] != want_type:
            continue
        if near(x["price"]):
            if x["placebo"]:
                plac = True
            else:
                real = True
    latest = None
    for leg in legs:
        if leg["from"] > day:
            continue
        latest = leg
        for x in leg["levels"]:
            fam = x["family"]
            if fam == ("val" if bull else "vah") and near(x["price"]):
                real = True
            elif fam == "range_placebo" and near(x["price"]):
                plac = True
    if latest is not None and latest["levels"]:
        L, H = latest["low"], latest["high"]
        val = next((x["price"] for x in latest["levels"] if x["family"] == "val"), None)
        vah = next((x["price"] for x in latest["levels"] if x["family"] == "vah"), None)
        if bull and latest["direction"] == "up" and val is not None:
            lo, hi = H - 0.886 * (H - L), H - 0.705 * (H - L)
            if hi < val and lo * (1 - NEAR) <= p <= hi * (1 + NEAR):
                real = True
        if not bull and latest["direction"] == "down" and vah is not None:
            lo, hi = L + 0.705 * (H - L), L + 0.886 * (H - L)
            if lo > vah and lo * (1 - NEAR) <= p <= hi * (1 + NEAR):
                real = True
    return "both" if real and plac else "real" if real else "placebo" if plac else "open"


def bonferroni(tests: list[dict]) -> int:
    n, surv = len(tests), 0
    for t in tests:
        d = t["discovery"]
        if d.get("p_raw") is not None:
            d["p_bonferroni"] = round(min(1.0, d["p_raw"] * n), 4)
            surv += d["p_bonferroni"] < 0.05
    for t in tests:
        d, s = t["discovery"], t["test"]
        if s.get("p_raw") is not None:
            s["p_bonferroni"] = round(min(1.0, s["p_raw"] * max(1, surv)), 4)
        dd, sd = d.get("mean_excess_pct", d.get("diff_pct")), s.get("mean_excess_pct", s.get("diff_pct"))
        t["replicates"] = bool(d.get("p_bonferroni", 1) < 0.05 and s.get("p_bonferroni", 1) < 0.05
                               and dd is not None and sd is not None and np.sign(dd) == np.sign(sd))
    return surv


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--daily-dir", required=True)
    ap.add_argument("--archive", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    rng = np.random.default_rng(SEED)

    # daily panel (liquidity, volatility quintiles, levels, Part 2)
    cs.HORIZONS = ls.HORIZONS
    d = cs.load_daily_dir(Path(args.daily_dir), ls.FIRST, ls.LAST)
    frames: dict = {}
    ev_daily, days, _ = cs.build_panel(d, frames)
    close, high, low = frames["close"], frames["high"], frames["low"]
    vol = d.pivot(index="day", columns="product_id", values="vol").reindex(days)
    liquid = frames["liquid"]
    vol20 = frames["ret1"].shift(1).rolling(20, min_periods=15).std()
    vol_q = np.floor(vol20.where(liquid).rank(axis=1, pct=True).clip(upper=0.9999) * 5)

    shadow_rng = np.random.default_rng(ls.SEED)
    levels_by, legs_by = {}, {}
    p2_rows = []
    for product in close.columns:
        w = ls.weekly_bars(close[product], high[product], low[product])
        if len(w) < 6:
            continue
        pl = product_levels(w, shadow_rng)
        levels_by[product] = pl["levels"]
        lo_a, hi_a, v_a = low[product].values, high[product].values, vol[product].values
        legs = []
        for leg in vp.causal_legs(pl["piv"]):
            i0, i1 = leg["start"] - days[0], leg["end"] - days[0]
            if i1 < 0 or i0 >= len(days):
                continue
            sl = slice(max(i0, 0), min(i1, len(days) - 1) + 1)
            leg = {**leg, "levels": vp.leg_levels(leg, vp.build_profile(lo_a[sl], hi_a[sl], v_a[sl], leg["low"], leg["high"]))}
            legs.append(leg)
        legs_by[product] = legs
        # Part 2 levels: macro low + VAL (real), pivot shadows + range placebos (placebo)
        p2 = [x for x in pl["levels"] if (x["family"] == "anchor" and x["ratio"] == 0.0) or (x["family"] == "pivot" and x["placebo"])]
        p2 += [x for leg in legs for x in leg["levels"] if x["family"] in ("val", "range_placebo")]
        p2_rows += ls.arrivals_for(product, p2, days, hi_a, lo_a)

    # ---------------- Part 2
    ar = ls.attach_outcomes(pd.DataFrame(p2_rows), frames, days)
    ar["family2"] = np.where((ar.family == "anchor") | (ar.family == "val"), "real", "placebo")
    first = ar[(ar.touch == 1) & (ar.side == "above")]
    split = ls.day_of(ls.SPLIT)
    periods = {"discovery": (int(days[0]), split - 1), "test": (split, int(days[-1]))}
    part2 = {}
    for broke in (True, False):
        sub = first[first.broke == broke]
        key = "breakdown (closed below)" if broke else "held (closed above)"
        part2[key] = {f"{k}d": {pn: ls.diff_boot(sub[sub.family2 == "real"], sub[sub.family2 == "placebo"], f"react{k}", per, k, rng)
                                for pn, per in periods.items()} for k in (7, 14)}
    prim = part2["breakdown (closed below)"]["14d"]
    part2["primary_passes"] = bool(all(prim[p].get("p_raw", 1) < 0.05 for p in periods)
                                   and np.sign(prim["discovery"].get("diff_pct", 0)) == np.sign(prim["test"].get("diff_pct", 0)) != 0)
    part2["by_family"] = {f: {"n": int(len(x)), **ls.describe(x, "react14")}
                          for f, x in first[first.broke].groupby("family")}

    # ---------------- Part 1: hourly
    conn = sqlite3.connect(f"file:{Path(args.archive).as_posix()}?mode=ro", uri=True)
    hq = pd.read_sql_query("SELECT product_id, ts, open, high, low, close, volume FROM candles WHERE granularity=3600", conn)
    conn.close()
    t_lo, t_hi = ls.day_of(H_FIRST) * DAY, (ls.day_of(H_LAST) + 1) * DAY
    hq = hq[(hq.ts >= t_lo - 30 * HOUR) & (hq.ts < t_hi)].sort_values(["product_id", "ts"])
    closes = hq.pivot(index="ts", columns="product_id", values="close")
    peers = Peers(closes, liquid, vol_q)

    trig_rows = []
    for product, g in hq.groupby("product_id"):
        for t in find_triggers(g):
            if t["ts"] < t_lo:
                continue
            t["product"], t["day"] = product, int(t["ts"] // DAY)
            trig_rows.append(t)
    tr = pd.DataFrame(trig_rows)
    tr = tr[tr.apply(lambda r: bool(liquid.at[r.day, r["product"]]) if r.day in liquid.index and r["product"] in liquid.columns else False, axis=1)].copy()
    sign = np.where(tr.direction == "bull", 1.0, -1.0)
    for k in HORIZON_DAYS:
        tr[f"o{k}"] = sign * winsorise(pd.Series([peers.rel(r["product"], r.ts, r.ts + 24 * k * HOUR, r.day) for _, r in tr.iterrows()], index=tr.index))
    tr["zone"] = [classify(r, r["day"], levels_by.get(r["product"], []), legs_by.get(r["product"], [])) for r in tr.to_dict("records")]

    h_split = ls.day_of(H_SPLIT)
    hp = {"discovery": (ls.day_of(H_FIRST), h_split - 1), "test": (h_split, ls.day_of(H_LAST))}
    tests = []
    for dirn in ("bull", "bear"):
        sub = tr[tr.direction == dirn]
        for k in HORIZON_DAYS:
            tests.append({"name": "A1_edge", "direction": dirn, "horizon_days": k,
                          **{pn: bootstrap_mean(sub, f"o{k}", per, k, days, rng) for pn, per in hp.items()}})
        for k in HORIZON_DAYS:
            for other in ("placebo", "open"):
                tests.append({"name": f"A2_real_minus_{other}", "direction": dirn, "horizon_days": k,
                              **{pn: ls.diff_boot(sub[sub.zone == "real"], sub[sub.zone == other], f"o{k}", per, k, rng) for pn, per in hp.items()}})

    # A3: shock days, bearish trigger in the 48h after the close
    shocks = ev_daily[(ev_daily.direction == "up") & (ev_daily.vol_ratio >= 5) & ((ev_daily.ret1 - ev_daily.btc_ret) >= 0.15)]
    shocks = shocks[(shocks.day >= ls.day_of(H_FIRST)) & (shocks.day <= ls.day_of(H_LAST))]
    bear = tr[tr.direction == "bear"]
    a3 = []
    for _, s in shocks.iterrows():
        t_close = (int(s.day) + 1) * DAY - HOUR  # last hourly candle of the shock day
        cand = bear[(bear["product"] == s["product"]) & (bear.ts > t_close) & (bear.ts <= t_close + 48 * HOUR)]
        if cand.empty:
            a3.append({"day": int(s.day), "product": s["product"], "trigger": False})
            continue
        t = cand.iloc[0]
        row = {"day": int(s.day), "product": s["product"], "trigger": True, "hours_after_close": int((t.ts - t_close) // HOUR)}
        for k in (3, 7):
            end_ok = (t_close + 24 * k * HOUR) in closes.index
            row[f"adv{k}"] = peers.rel(s["product"], t_close, int(t.ts), int(s.day)) if end_ok else np.nan
        a3.append(row)
    a3 = pd.DataFrame(a3)
    with_t = a3[a3.trigger] if len(a3) else a3
    for k in (3, 7):
        tests.append({"name": "A3_timing", "direction": "bear", "horizon_days": k,
                      **{pn: bootstrap_mean(with_t, f"adv{k}", per, k, days, rng) for pn, per in hp.items()}})
    surv = bonferroni(tests)

    out = {
        "design": "docs/developer/ABSORPTION_STUDY.md (preregistered)",
        "part1": {"triggers": int(len(tr)), "by_direction": tr.direction.value_counts().to_dict(),
                  "by_zone": tr.groupby(["direction", "zone"]).size().unstack(fill_value=0).to_dict(),
                  "tests": len(tests), "discovery_survivors": int(surv), "primary": tests,
                  "a3_shock_days": int(len(a3)), "a3_with_trigger": int(a3.trigger.sum()) if len(a3) else 0,
                  "outcome_sign": "positive = the trigger was right (bull: relative rise; bear: relative fall)"},
        "part2": part2,
    }
    (Path(args.out) / "absorption_study.json").write_text(json.dumps(out, indent=1, default=float) + "\n", encoding="utf-8", newline=cs.LF)
    print("part1", {k: out["part1"][k] for k in ("triggers", "by_direction", "by_zone", "discovery_survivors", "a3_shock_days", "a3_with_trigger")})
    for t in tests:
        a, b = t["discovery"], t["test"]
        g = lambda x, *ks: next((x.get(kk) for kk in ks if x.get(kk) is not None), None)
        print(t["name"], t["direction"], t["horizon_days"], "| disc", g(a, "events", "n_real"), g(a, "mean_excess_pct", "diff_pct"), a.get("ci95_pct"), a.get("p_bonferroni"),
              "| test", g(b, "events", "n_real"), g(b, "mean_excess_pct", "diff_pct"), b.get("ci95_pct"), b.get("p_bonferroni"), "REPL" if t["replicates"] else "")
    print("part2", json.dumps({k: v for k, v in part2.items()}, default=float)[:3000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
