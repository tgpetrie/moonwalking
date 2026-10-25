"""Block-bootstrap statistics, score diagnostics, and the continuation/exhaustion event tests."""
from __future__ import annotations

import numpy as np
import pandas as pd

from model import daily_ic

DAY = pd.Timedelta(days=1)


def week_key(index) -> np.ndarray:
    d = pd.DatetimeIndex(index)
    iso = d.isocalendar()
    return (iso["year"].astype(int) * 100 + iso["week"].astype(int)).to_numpy()


def boot(values: pd.Series, cfg: dict, seed_offset: int = 0) -> dict:
    """Mean of block values with a percentile bootstrap interval over blocks."""
    v = values.dropna().to_numpy(float)
    n = len(v)
    out = {"n_blocks": n, "mean": float(v.mean()) if n else None, "lo": None, "hi": None}
    if n < 3:
        return out
    b = cfg["bootstrap"]
    rng = np.random.default_rng(b["seed"] + seed_offset)
    means = v[rng.integers(0, n, size=(b["resamples"], n))].mean(axis=1)
    a = (1 - b["level"]) / 2 * 100
    out["lo"], out["hi"] = (float(x) for x in np.percentile(means, [a, 100 - a]))
    out["se"] = float(v.std(ddof=1) / np.sqrt(n))
    return out


def weekly(series: pd.Series) -> pd.Series:
    """Average a date-indexed series within ISO weeks."""
    if series.empty:
        return series
    return series.groupby(week_key(series.index)).mean()


def ic_summary(ic: pd.Series, cfg: dict, seed_offset: int = 0) -> dict:
    out = boot(weekly(ic), cfg, seed_offset)
    out.update(n_days=int(len(ic)), mean_daily_ic=float(ic.mean()) if len(ic) else None,
               share_weeks_positive=float((weekly(ic) > 0).mean()) if len(ic) else None)
    return out


def verdict(est: dict, frozen_sign: int, mei: float) -> str:
    """supportive / ruled out / inconclusive under the protocol (section 5)."""
    if est.get("lo") is None:
        return "inconclusive"
    lo, hi, m = est["lo"], est["hi"], est["mean"]
    amp_hi = max(abs(lo), abs(hi))
    if amp_hi < mei:
        return "ruled out"
    if np.sign(m) == frozen_sign and abs(m) >= mei and (lo > 0 or hi < 0):
        return "supportive"
    return "inconclusive"


def decile_table(df: pd.DataFrame, score: pd.Series, ycol: str, rawcol: str, cfg: dict) -> list[dict]:
    d = pd.DataFrame({"s": score, "y": df[ycol], "raw": df[rawcol]}).dropna()
    d["bucket"] = np.minimum((d["s"] - 1) // 10, 9).astype(int) + 1
    day = d.index.get_level_values("date")
    rows = []
    for b, g in d.groupby("bucket"):
        per_day_y = g["y"].groupby(g.index.get_level_values("date")).mean()
        per_day_raw = g["raw"].groupby(g.index.get_level_values("date")).mean()
        e = boot(weekly(per_day_y), cfg, int(b))
        e2 = boot(weekly(per_day_raw), cfg, 50 + int(b))
        rows.append({"bucket": f"{(b-1)*10+1}-{b*10}", "n_rows": int(len(g)),
                     "mean_scaled_residual": e["mean"], "lo": e["lo"], "hi": e["hi"],
                     "mean_raw_return_pct": None if e2["mean"] is None else 100 * e2["mean"],
                     "raw_lo_pct": None if e2["lo"] is None else 100 * e2["lo"],
                     "raw_hi_pct": None if e2["hi"] is None else 100 * e2["hi"]})
    return rows


def spread_series(df: pd.DataFrame, score: pd.Series, ycol: str) -> pd.Series:
    d = pd.DataFrame({"s": score, "y": df[ycol]}).dropna()
    day = d.index.get_level_values("date")
    top = d[d["s"] > 90]["y"].groupby(d[d["s"] > 90].index.get_level_values("date")).mean()
    bot = d[d["s"] <= 10]["y"].groupby(d[d["s"] <= 10].index.get_level_values("date")).mean()
    return (top - bot).dropna()


def staggered_sleeves(df: pd.DataFrame, score: pd.Series, h: int, costs: list[float], cfg: dict) -> dict:
    """Top-quintile weekly excess return over the equal-weight eligible universe.

    Seven staggered sleeves (one per weekday) are averaged per ISO week. Raw open-to-open
    returns, not residuals. Costs are scenarios applied to the top-quintile leg each
    rebalance (full turnover assumed); the benchmark is cost-free.
    """
    d = pd.DataFrame({"s": score, "raw": df[f"rawret{h}"]}).dropna()
    day = d.index.get_level_values("date")
    d["day"] = day
    g = d.groupby("day")
    uni = g["raw"].mean()
    topm = d[d["s"] > 80].groupby("day")["raw"].mean()
    top_med = d[d["s"] > 80].groupby("day")["raw"].median()
    uni_med = g["raw"].median()
    ex = (topm - uni).dropna()
    wk = week_key(ex.index)
    out = {"gross_excess_pct": {k: (None if v is None else 100 * v) for k, v in
                                boot(ex.groupby(wk).mean(), cfg, 700).items() if k in ("mean", "lo", "hi")},
           "n_weeks": int(len(set(wk)))}
    out["median_top_quintile_minus_median_universe_pct"] = float(100 * (top_med - uni_med).dropna().mean())
    for c in costs:
        net = (ex - c / 100.0).groupby(wk).mean()
        e = boot(net, cfg, 710 + int(c * 10))
        out[f"net_excess_pct_cost_{c}"] = {k: (None if e[k] is None else 100 * e[k]) for k in ("mean", "lo", "hi")}
    return out


# ------------------------------------------------------------------ events
def _pct(df, col, q):
    return df.groupby(level="date")[col].transform(lambda s: s.quantile(q / 100.0))


def flag_events(df: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """Past-only event rules (protocol section 6). Exclusive; exhaustion first."""
    e = cfg["event"]
    r1_hi, r1_lo = _pct(df, "r1", e["exhaustion_r1_pct"]), _pct(df, "r1", 100 - e["exhaustion_r1_pct"])
    ext_hi, ext_lo = _pct(df, "ext30", e["exhaustion_ext30_pct"]), _pct(df, "ext30", 100 - e["exhaustion_ext30_pct"])
    res_hi, res_lo = _pct(df, "res7", e["continuation_res7_pct"]), _pct(df, "res7", 100 - e["continuation_res7_pct"])
    spike = df["relvol"] >= e["exhaustion_relvol_log"]
    normal = (df["relvol"] <= e["continuation_relvol_max_log"])
    ex_up = (df["r1"] >= r1_hi) & (spike | (df["ext30"] >= ext_hi))
    ex_dn = (df["r1"] <= r1_lo) & (spike | (df["ext30"] <= ext_lo))
    top = df["res7"] >= res_hi
    bot = df["res7"] <= res_lo
    med_top = df["ext30"].where(top).groupby(level="date").transform("median")
    med_bot = df["ext30"].where(bot).groupby(level="date").transform("median")
    cont_up = top & (df["ext30"] <= med_top) & normal & ~ex_up & ~ex_dn
    cont_dn = bot & (df["ext30"] >= med_bot) & normal & ~ex_up & ~ex_dn
    ev = pd.Series("", index=df.index)
    ev[cont_dn] = "downside_continuation"
    ev[cont_up] = "continuation"
    ev[ex_dn] = "capitulation"
    ev[ex_up] = "exhaustion"
    return ev


def _btc_bucket(btc7: pd.Series) -> pd.Series:
    return pd.cut(btc7, [-np.inf, -0.03, 0.03, np.inf], labels=False)


def match_controls(df: pd.DataFrame, ev: pd.Series, cfg: dict, period: tuple[str, str], seed: int = 0):
    """For each event row, up to k clean same-coin controls (no event of the coin within +-gap days).

    Matching: same coin, same period, same same-day vol30 quintile, same BTC 7-day bucket.
    Returns a list of (event_index, [control_indices]).
    """
    e = cfg["event"]
    gap = pd.Timedelta(days=e["control_min_gap_days"])
    k = e["controls_per_event"]
    rng = np.random.default_rng(cfg["bootstrap"]["seed"] + seed)
    d0, d1 = pd.Timestamp(period[0]), pd.Timestamp(period[1])
    date = df.index.get_level_values("date")
    inwin = (date >= d0) & (date <= d1)
    sub = df[inwin]
    subev = ev[inwin]
    vq = sub.groupby(level="date")["vol30"].transform(lambda s: pd.qcut(s.rank(method="first"), 5, labels=False, duplicates="drop"))
    bb = _btc_bucket(sub["btc7"])
    prod = sub.index.get_level_values("product")
    dts = sub.index.get_level_values("date")
    meta = pd.DataFrame({"prod": prod, "date": dts, "vq": vq.to_numpy(), "bb": bb.to_numpy(),
                         "ev": subev.to_numpy(), "hasy": sub["y1"].notna().to_numpy()},
                        index=np.arange(len(sub)))
    pairs = []
    for p, g in meta.groupby("prod"):
        evd = g.loc[g["ev"] != "", "date"].to_numpy()
        if len(evd) == 0:
            continue
        evd_sorted = np.sort(evd)
        pos = np.searchsorted(evd_sorted, g["date"].to_numpy())
        near = np.zeros(len(g), bool)
        for sh in (-1, 0):
            idx = np.clip(pos + sh, 0, len(evd_sorted) - 1)
            near |= np.abs(g["date"].to_numpy() - evd_sorted[idx]) <= gap.to_timedelta64()
        clean = g[(~near) & (g["ev"] == "") & g["hasy"]]
        by_key = {key: grp.index.to_numpy() for key, grp in clean.groupby(["vq", "bb"])}
        for i in g.index[g["ev"] != ""]:
            cand = by_key.get((g.at[i, "vq"], g.at[i, "bb"]))
            if cand is None or len(cand) == 0:
                continue
            take = cand if len(cand) <= k else rng.choice(cand, size=k, replace=False)
            pairs.append((i, take))
    return sub, meta, pairs


def event_effects(df: pd.DataFrame, ev: pd.Series, cfg: dict, period: tuple[str, str], seed: int = 0) -> dict:
    sub, meta, pairs = match_controls(df, ev, cfg, period, seed)
    out = {}
    day_mean = {h: sub.groupby(level="date")[f"yraw{h}"].transform("mean").to_numpy() for h in cfg["horizons_days"]}
    for cls in ("exhaustion", "continuation", "capitulation", "downside_continuation"):
        rows = [(i, c) for i, c in pairs if meta.at[i, "ev"] == cls]
        total_events = int((meta["ev"] == cls).sum())
        res = {"events_in_period": total_events, "events_matched": len(rows)}
        if rows:
            ei = np.array([i for i, _ in rows])
            dates = meta.loc[ei, "date"]
            res["distinct_coins"] = int(meta.loc[ei, "prod"].nunique())
            res["distinct_weeks"] = int(len(set(week_key(dates))))
            res["largest_coin_share"] = float(meta.loc[ei, "prod"].value_counts(normalize=True).iloc[0])
            for h in cfg["horizons_days"]:
                y = sub[f"yraw{h}"].to_numpy()
                ys = sub[f"y{h}"].to_numpy()
                ok = np.isfinite(y[ei])
                d_ctrl, d_ctrl_s, d_peer, d_peer_s, keep = [], [], [], [], []
                for (i, c), good in zip(rows, ok):
                    if not good:
                        continue
                    ctrl = y[c][np.isfinite(y[c])]
                    ctrl_s = ys[c][np.isfinite(ys[c])]
                    if len(ctrl) == 0:
                        continue
                    d_ctrl.append(y[i] - ctrl.mean())
                    d_ctrl_s.append(ys[i] - ctrl_s.mean())
                    d_peer.append(y[i] - day_mean[h][i])
                    keep.append(i)
                keep = np.array(keep)
                wk = week_key(meta.loc[keep, "date"]) if len(keep) else np.array([])
                for name, vals in (("vs_clean_controls", d_ctrl), ("vs_same_day_universe", d_peer)):
                    s = pd.Series(vals, index=wk)
                    est = boot(s.groupby(level=0).mean(), cfg, 900 + h) if len(s) else {"n_blocks": 0}
                    res[f"h{h}_{name}_pp"] = {k: (None if est.get(k) is None else 100 * est[k]) for k in ("mean", "lo", "hi")}
                    res[f"h{h}_{name}_pp"]["n_blocks"] = est["n_blocks"]
                res[f"h{h}_n_events"] = int(len(keep))
        out[cls] = res
    return out
