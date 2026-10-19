"""Study 2d: daily profile shapes (P / b), three-day balance breakouts, volume ledges.

Design is preregistered in docs/developer/PROFILE_SHAPE_STUDY.md (committed
before this script was first run). Local data only.

  python scripts/move_study/profile_shape_study.py --daily-dir <daily_all> --archive <archive copy> --out data/move-study
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

DAY = cs.DAY
DAY_BINS = 20
H_FIRST, H_LAST, H_SPLIT = "2025-10-02", "2026-10-10", "2026-04-01"
COOLDOWN = 7
SEED = 20261023
BOOT = 4000


def cooldown(df: pd.DataFrame, days: int = COOLDOWN) -> pd.DataFrame:
    keep, last = [], {}
    for idx, r in df.sort_values("day").iterrows():
        key = (r["product"], r["etype"])
        if key in last and r["day"] - last[key] <= days:
            continue
        last[key] = r["day"]
        keep.append(idx)
    return df.loc[keep]


def wdiff_boot(real: pd.DataFrame, ctrl: pd.DataFrame, col: str, period: tuple[int, int], k: int, rng) -> dict:
    """Mean(real) - weighted mean(control), block bootstrap over calendar days. Control rows carry a 'w' column."""
    a, b = period
    r = real[(real.day >= a) & (real.day + k <= b) & real[col].notna()]
    c = ctrl[(ctrl.day >= a) & (ctrl.day + k <= b) & ctrl[col].notna() & (ctrl.w > 0)]
    if len(r) < 20 or len(c) < 20:
        return {"n_real": int(len(r)), "n_placebo": int(len(c)), "note": "too few"}
    n = b - a + 1
    rs = np.bincount(r.day.values - a, weights=r[col].values, minlength=n)
    rc = np.bincount(r.day.values - a, minlength=n).astype(float)
    cs_ = np.bincount(c.day.values - a, weights=(c[col] * c.w).values, minlength=n)
    cw = np.bincount(c.day.values - a, weights=c.w.values, minlength=n)
    obs = rs.sum() / rc.sum() - cs_.sum() / cw.sum()
    B = cs.BLOCK
    st = rng.integers(0, max(1, n - B + 1), size=(BOOT, int(np.ceil(n / B))))
    ix = (st[:, :, None] + np.arange(B)[None, None, :]).reshape(BOOT, -1)[:, :n]
    R, RC, C, CW = rs[ix].sum(1), rc[ix].sum(1), cs_[ix].sum(1), cw[ix].sum(1)
    ok = (RC > 0) & (CW > 0)
    bd = R[ok] / RC[ok] - C[ok] / CW[ok]
    lo, hi = np.percentile(bd, [2.5, 97.5])
    p = 2 * min((bd <= 0).mean(), (bd >= 0).mean())
    return {"n_real": int(len(r)), "n_placebo": int(len(c)), "real_mean_pct": round(float(r[col].mean()) * 100, 2),
            "placebo_mean_pct": round(float((c[col] * c.w).sum() / c.w.sum()) * 100, 2), "diff_pct": round(float(obs) * 100, 2),
            "ci95_pct": [round(lo * 100, 2), round(hi * 100, 2)], "p_raw": round(max(float(p), 1 / BOOT), 5)}


def match_weights(events: pd.DataFrame, ctrl: pd.DataFrame) -> pd.DataFrame:
    """Reweight controls to the events' distribution of day-t moves in 2-point bins."""
    eb = np.floor(events.ret1 * 100 / 2).astype(int)
    cb = np.floor(ctrl.ret1 * 100 / 2).astype(int)
    want = eb.value_counts()
    have = cb.value_counts()
    ctrl = ctrl.copy()
    ctrl["w"] = [want.get(x, 0) / have[x] for x in cb]
    return ctrl


def attach_daily(df: pd.DataFrame, frames: dict, days: np.ndarray) -> pd.DataFrame:
    close = frames["close"]
    pos = {p: i for i, p in enumerate(close.columns)}
    di = (df.day.values - days[0]).astype(int)
    ci = df["product"].map(pos).values
    get = lambda f: f.values[di, ci]
    df = df.copy()
    df["liquid"] = get(frames["liquid"]).astype(bool)
    df["ret1"] = get(frames["ret1"])
    sign = np.where(df.direction == "down", -1.0, 1.0)
    for k in (1, 3, 7):
        df[f"c{k}"] = sign * get(frames["fwd_vm"][k])
    return df[df.liquid & df.ret1.notna()]


def day_profiles(archive: Path, frames: dict, days: np.ndarray) -> pd.DataFrame:
    conn = sqlite3.connect(f"file:{archive.as_posix()}?mode=ro", uri=True)
    h = pd.read_sql_query("SELECT product_id, ts, high, low, volume FROM candles WHERE granularity=3600", conn)
    conn.close()
    d0, d1 = ls.day_of(H_FIRST) - 4, ls.day_of(H_LAST)
    h["day"] = h.ts // DAY
    h = h[(h.day >= d0) & (h.day <= d1)]
    close, high, low = frames["close"], frames["high"], frames["low"]
    rows = []
    for (product, day), g in h.groupby(["product_id", "day"]):
        if len(g) < 20 or product not in close.columns or day not in close.index:
            continue
        H, L, C = high.at[day, product], low.at[day, product], close.at[day, product]
        if not (np.isfinite(H) and np.isfinite(L) and np.isfinite(C)) or H <= L:
            continue
        prof = vp.build_profile(g.low.values, g.high.values, g.volume.values, L, H, bins=DAY_BINS)
        tot = prof.sum()
        if tot <= 0:
            continue
        w = (H - L) / DAY_BINS
        poc = vp.poc_index(prof)
        lo, hi = vp.value_area(prof)
        rows.append({"product": product, "day": int(day), "H": H, "L": L, "C": C,
                     "poc_pos": (poc + 0.5) / DAY_BINS, "close_pos": (C - L) / (H - L),
                     "bottom": prof[:6].sum() / tot, "top": prof[-6:].sum() / tot,
                     "poc": L + (poc + 0.5) * w, "val": L + lo * w, "vah": L + (hi + 1) * w})
    return pd.DataFrame(rows)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--daily-dir", required=True)
    ap.add_argument("--archive", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    rng = np.random.default_rng(SEED)

    cs.HORIZONS = ls.HORIZONS
    d = cs.load_daily_dir(Path(args.daily_dir), ls.FIRST, ls.LAST)
    frames: dict = {}
    _, days, _ = cs.build_panel(d, frames)
    close, high, low = frames["close"], frames["high"], frames["low"]
    vol = d.pivot(index="day", columns="product_id", values="vol").reindex(days)

    h_split = ls.day_of(H_SPLIT)
    hp = {"discovery": (ls.day_of(H_FIRST), h_split - 1), "test": (h_split, ls.day_of(H_LAST))}
    split = ls.day_of(ls.SPLIT)
    dp = {"discovery": (int(days[0]), split - 1), "test": (split, int(days[-1]))}
    tests = []

    # ---------------- S1
    prof = day_profiles(Path(args.archive), frames, days)
    pr = prof[(prof.day >= ls.day_of(H_FIRST))].copy()
    pr["ret1"] = [frames["ret1"].at[r["day"], r["product"]] for r in pr.to_dict("records")]
    pr["rng_pct"] = (pr.H - pr.L) / pr.L
    directional = pr[(pr.ret1.abs() >= 0.05) & (pr.rng_pct >= 0.05)]
    up, dn = directional[directional.ret1 >= 0.05], directional[directional.ret1 <= -0.05]
    s1 = pd.concat([
        up[(up.poc_pos >= 0.60) & (up.bottom < 0.15) & (up.close_pos >= 0.70)].assign(etype="P", direction="up"),
        up[(up.close_pos >= 0.70) & (up.poc_pos <= 0.40)].assign(etype="bottom_heavy", direction="up"),
        dn[(dn.poc_pos <= 0.40) & (dn.top < 0.15) & (dn.close_pos <= 0.30)].assign(etype="b", direction="down"),
        dn[(dn.close_pos <= 0.30) & (dn.poc_pos >= 0.60)].assign(etype="top_heavy", direction="down"),
    ])
    s1 = attach_daily(cooldown(s1[["product", "day", "etype", "direction"]]), frames, days)
    for real, ctrl in (("P", "bottom_heavy"), ("b", "top_heavy")):
        for k in (1, 3):
            tests.append({"name": f"S1_{real}_minus_{ctrl}", "horizon": k,
                          **{pn: ls.diff_boot(s1[s1.etype == real], s1[s1.etype == ctrl], f"c{k}", per, k, rng) for pn, per in hp.items()}})

    # ---------------- S2h (hourly value areas)
    prof = prof.sort_values(["product", "day"])
    s2h = []
    for product, g in prof.groupby("product"):
        g = g.set_index("day")
        for t in g.index:
            if t < ls.day_of(H_FIRST) or not all((t - j) in g.index for j in (1, 2, 3)):
                continue
            a, b_, c_ = g.loc[t - 3], g.loc[t - 2], g.loc[t - 1]
            bal = (a.val <= b_.poc <= a.vah) and (min(a.val, b_.val) <= c_.poc <= max(a.vah, b_.vah))
            hi_, lo_ = max(a.vah, b_.vah, c_.vah), min(a.val, b_.val, c_.val)
            ct = g.loc[t].C
            if bal and ct > hi_:
                s2h.append((product, t, "break_up", "up"))
            elif bal and ct < lo_:
                s2h.append((product, t, "break_down", "down"))
            elif not bal:
                s2h.append((product, t, "ctrl", "up" if frames["ret1"].at[t, product] > 0 else "down"))
    s2h = attach_daily(cooldown(pd.DataFrame(s2h, columns=["product", "day", "etype", "direction"])), frames, days)

    # ---------------- S2d (daily ranges)
    rng_ = (high - low) / close
    med = rng_.shift(1).rolling(20, min_periods=15).median()
    quiet = rng_ <= 1.5 * med
    ov1 = (low <= high.shift(1)) & (high >= low.shift(1))  # overlaps the previous day
    sh = lambda f, k: f.shift(k, fill_value=False).astype(bool)
    bal = sh(quiet, 3) & sh(quiet, 2) & sh(quiet, 1) & sh(ov1, 2) & sh(ov1, 1)
    have = close.shift(3).notna() & close.shift(2).notna() & close.shift(1).notna() & close.notna()
    mh = pd.concat([high.shift(k) for k in (1, 2, 3)]).groupby(level=0).max()
    ml = pd.concat([low.shift(k) for k in (1, 2, 3)]).groupby(level=0).min()
    bu = (bal & (close > mh) & have).stack()
    bd = (bal & (close < ml) & have).stack()
    ct = (~bal & have).stack()
    s2d = pd.concat([pd.DataFrame([(p, dd, "break_up", "up") for (dd, p) in bu[bu].index]),
                     pd.DataFrame([(p, dd, "break_down", "down") for (dd, p) in bd[bd].index]),
                     pd.DataFrame([(p, dd, "ctrl", None) for (dd, p) in ct[ct].index])])
    s2d.columns = ["product", "day", "etype", "direction"]
    r1 = frames["ret1"]
    s2d.loc[s2d.etype == "ctrl", "direction"] = ["up" if r1.at[dd, p] > 0 else "down" for p, dd in s2d.loc[s2d.etype == "ctrl", ["product", "day"]].values]
    s2d = attach_daily(cooldown(s2d), frames, days)

    for label, df, per in (("S2h", s2h, hp), ("S2d", s2d, dp)):
        for etype, dirn in (("break_up", "up"), ("break_down", "down")):
            ev_ = df[df.etype == etype]
            ctl = df[(df.etype == "ctrl") & (df.direction == dirn)]
            ctl = match_weights(ev_, ctl) if len(ev_) else ctl.assign(w=0.0)
            for k in (1, 3, 7):
                tests.append({"name": f"{label}_{etype}_minus_matched_control", "horizon": k,
                              **{pn: wdiff_boot(ev_, ctl, f"c{k}", pp, k, rng) for pn, pp in per.items()}})

    # ---------------- S3 (volume ledges on Study 2b legs)
    rows = []
    for product in close.columns:
        wk = ls.weekly_bars(close[product], high[product], low[product])
        if len(wk) < 6:
            continue
        lo_a, hi_a, v_a = low[product].values, high[product].values, vol[product].values
        levels = []
        for leg in vp.causal_legs(ls.confirmed_pivots(wk)):
            i0, i1 = leg["start"] - days[0], leg["end"] - days[0]
            if i1 < 0 or i0 >= len(days):
                continue
            sl = slice(max(i0, 0), min(i1, len(days) - 1) + 1)
            pf = vp.build_profile(lo_a[sl], hi_a[sl], v_a[sl], leg["low"], leg["high"])
            if pf.sum() <= 0:
                continue
            sm = np.convolve(pf, np.ones(3) / 3, mode="same")
            p80 = np.percentile(sm, 80)
            poc = vp.poc_index(pf)
            w = (leg["high"] - leg["low"]) / len(pf)
            drops = np.abs(np.diff(sm))
            hvn_side = np.maximum(sm[:-1], sm[1:]) >= p80
            base = {"from": leg["from"], "until": 10**9, "pivot_type": leg["direction"], "ratio": None}
            for side_mask in (np.arange(len(drops)) >= poc, np.arange(len(drops)) + 1 <= poc):
                cand = np.where(side_mask & hvn_side)[0]
                if len(cand):
                    bb = cand[np.argmax(drops[cand])]
                    levels.append({**base, "family": "ledge", "placebo": False, "price": leg["low"] + (bb + 1) * w})
            levels += [x for x in vp.leg_levels(leg, pf) if x["family"] == "range_placebo"]
        rows += ls.arrivals_for(product, levels, days, hi_a, lo_a)
    ar = ls.attach_outcomes(pd.DataFrame(rows), frames, days)
    first = ar[ar.touch == 1]
    for side in ("below", "above"):
        for k in (1, 3, 7):
            tests.append({"name": f"S3_ledge_minus_placebo_from_{side}", "horizon": k,
                          **{pn: ls.diff_boot(first[(first.family == "ledge") & (first.side == side)],
                                              first[(first.family == "range_placebo") & (first.side == side)], f"react{k}", per, k, rng)
                             for pn, per in dp.items()}})

    n, surv = len(tests), 0
    for t in tests:
        a = t["discovery"]
        if "p_raw" in a:
            a["p_bonferroni"] = round(min(1.0, a["p_raw"] * n), 4)
            surv += a["p_bonferroni"] < 0.05
    for t in tests:
        a, b = t["discovery"], t["test"]
        if "p_raw" in b:
            b["p_bonferroni"] = round(min(1.0, b["p_raw"] * max(1, surv)), 4)
        t["replicates"] = bool("p_bonferroni" in a and "p_bonferroni" in b and a["p_bonferroni"] < 0.05
                               and b["p_bonferroni"] < 0.05 and np.sign(a["diff_pct"]) == np.sign(b["diff_pct"]))

    counts = {"S1": s1.etype.value_counts().to_dict(), "S2h": s2h.etype.value_counts().to_dict(),
              "S2d": s2d.etype.value_counts().to_dict(), "S3_first_touches": first.family.value_counts().to_dict(),
              "day_profiles": int(len(prof))}
    out = {"design": "docs/developer/PROFILE_SHAPE_STUDY.md (preregistered)", "tests": n, "discovery_survivors": int(surv),
           "counts": counts, "primary": tests,
           "sign": "S1/S2: positive = continued in the event's direction; S3: positive = turned back from the level"}
    (Path(args.out) / "profile_shape_study.json").write_text(json.dumps(out, indent=1, default=float) + "\n", encoding="utf-8", newline=cs.LF)
    print(json.dumps({"tests": n, "survivors": surv, "counts": counts}, default=str))
    for t in tests:
        a, b = t["discovery"], t["test"]
        print(t["name"], t["horizon"], "| disc", a.get("n_real"), a.get("n_placebo"), a.get("real_mean_pct"), a.get("placebo_mean_pct"), a.get("diff_pct"),
              a.get("ci95_pct"), a.get("p_bonferroni"), "| test", b.get("n_real"), b.get("n_placebo"), b.get("diff_pct"), b.get("ci95_pct"), b.get("p_bonferroni"),
              "REPL" if t["replicates"] else "")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
