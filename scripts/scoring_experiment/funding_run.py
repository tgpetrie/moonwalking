"""Funding comparison driver: M1 (baseline + funding) versus M0-matched on identical rows.

    python scripts/scoring_experiment/funding_run.py discovery
    python scripts/scoring_experiment/funding_run.py test          # refuses without a matching discovery result
Reads the corrected baseline pipeline (unchanged), the approved map and the stored funding responses. Writes small JSON
under docs/research/results/funding_comparison and a cache under ~/.moonwalking/analysis/scoring_baseline.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import evaluate as ev  # noqa: E402
import funding  # noqa: E402
import panel  # noqa: E402
import run as base_run  # noqa: E402
from model import daily_ic, to_score, walk_forward  # noqa: E402

REPO = HERE.parents[1]
OUT = REPO / "docs" / "research" / "results" / "funding_comparison"
WORK = base_run.WORK
START = "2023-06-01"


def fcfg_load() -> dict:
    return json.loads((HERE / "funding_config.json").read_text(encoding="utf-8"))


def combined_hash(cfg, fcfg, amap) -> str:
    return panel.config_hash({"baseline": cfg, "funding": fcfg, "map": amap})


def inwin(df, period):
    d = df.index.get_level_values("date")
    return (d >= pd.Timestamp(period[0])) & (d <= pd.Timestamp(period[1]))


def diff_summary(ic1: pd.Series, ic0: pd.Series, cfg: dict, seed: int) -> dict:
    both = pd.concat([ic1, ic0], axis=1, keys=["m1", "m0"]).dropna()
    d = both["m1"] - both["m0"]
    out = ev.ic_summary(d, cfg, seed, moving=True)
    out["mean_ic_m1"], out["mean_ic_m0"] = float(both["m1"].mean()) if len(both) else None, float(both["m0"].mean()) if len(both) else None
    return out


def weekday_diff(ic1, ic0, cfg, seed):
    both = pd.concat([ic1, ic0], axis=1, keys=["m1", "m0"]).dropna()
    d = both["m1"] - both["m0"]
    res = {}
    for w, name in enumerate(["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]):
        res[name] = ev.boot(d[d.index.dayofweek == w].reset_index(drop=True), cfg, seed + w)
    return res


def residual_ic(dm: pd.DataFrame, pred0: pd.Series, ycol: str, feat: str, min_n: int) -> pd.Series:
    out = {}
    z = dm["z_" + feat]
    for day, idx in dm.groupby(level="date").indices.items():
        sub = dm.iloc[idx]
        p, x, y = pred0.iloc[idx], z.iloc[idx], sub[ycol]
        m = p.notna() & x.notna() & y.notna()
        if m.sum() < min_n:
            continue
        P = np.column_stack([np.ones(m.sum()), p[m].to_numpy()])
        beta = np.linalg.lstsq(P, x[m].to_numpy(), rcond=None)[0]
        res = x[m].to_numpy() - P @ beta
        out[sub.index.get_level_values("date")[0]] = (pd.Series(res, index=sub.index[m.to_numpy()]), y[m])
    series = {}
    for d, (r, y) in out.items():
        a, b = r.rank().to_numpy(), y.rank().to_numpy()
        a, b = a - a.mean(), b - b.mean()
        den = np.sqrt((a * a).sum() * (b * b).sum())
        if den > 0:
            series[d] = float((a * b).sum() / den)
    return pd.Series(series).sort_index()


def run_variant(dm: pd.DataFrame, feat: str, cfg: dict, end: str, full_preds: dict | None):
    preds0, preds1, contrib1, logs1, logs0 = {}, {}, {}, {}, {}
    for h in cfg["horizons_days"]:
        preds0[h], _, logs0[h] = walk_forward(dm, h, cfg, START, end)
        preds1[h], contrib1[h], logs1[h] = walk_forward(dm, h, cfg, START, end, panel.FEATURES + [feat])
    return preds0, preds1, contrib1, logs0, logs1


def evaluate_variant(dm, feat, preds0, preds1, full_preds, cfg, fcfg, period, frozen, thresholds, label):
    m = inwin(dm, period)
    min_n = cfg["min_cross_section"]
    res = {}
    delisted = dm.index.get_level_values("product").isin(fcfg["_delisted"])
    kc = dm.index.get_level_values("product").isin(fcfg["k_contracts"])
    cuts = {"all_matched": np.ones(len(dm), bool), "excluding_thin": (dm["thin"] == 0).to_numpy(),
            "excluding_delisted_hl_markets": ~delisted, "excluding_k_contracts": ~kc}
    for h in cfg["horizons_days"]:
        y = dm[f"y{h}"]
        r = {}
        for cname, cmask in cuts.items():
            mm = m & cmask
            ic0 = daily_ic(preds0[h][mm], y[mm], min_n)
            ic1 = daily_ic(preds1[h][mm], y[mm], min_n)
            e = {"incremental_ic_m1_minus_m0": diff_summary(ic1, ic0, cfg, h * 7 + len(cname))}
            e["m0_matched"] = ev.ic_summary(ic0, cfg, h + 1)
            e["m1"] = ev.ic_summary(ic1, cfg, h + 2)
            if cname == "all_matched":
                icf = daily_ic(full_preds[h][mm], y[mm], min_n) if full_preds else pd.Series(dtype=float)
                e["m0_full_universe_model_on_matched_rows"] = ev.ic_summary(icf, cfg, h + 3)
                e["funding_alone_rank_normal_z"] = ev.ic_summary(daily_ic(dm["z_" + feat][mm], y[mm], min_n), cfg, h + 4)
                e["funding_level_alone"] = ev.ic_summary(daily_ic(dm["z_fl" + feat[2:]][mm], y[mm], min_n), cfg, h + 5)
                e["residualised_incremental_ic"] = ev.ic_summary(
                    residual_ic(dm[mm], preds0[h][mm], f"y{h}", feat, min_n), cfg, h + 6, moving=True)
                e["weekday_phases_incremental"] = weekday_diff(ic1, ic0, cfg, h * 100)
                reg = pd.cut(dm["btc30"], [-np.inf, thresholds[0], thresholds[1], np.inf], labels=["down", "flat", "up"])
                days_by = {k: set(reg[reg == k].index.get_level_values("date")) for k in ("down", "flat", "up")}
                both = pd.concat([ic1, ic0], axis=1, keys=["m1", "m0"]).dropna()
                dd = both["m1"] - both["m0"]
                e["by_btc_30d_regime"] = {k: {**ev.ic_summary(dd[[d in days_by[k] for d in dd.index]], cfg, h + 10),
                                             "interpretable": None} for k in days_by}
                for k in e["by_btc_30d_regime"]:
                    e["by_btc_30d_regime"][k]["interpretable"] = e["by_btc_30d_regime"][k]["n_blocks"] >= cfg["min_blocks_for_regime"]
                e["by_calendar_year"] = {str(yr): ev.ic_summary(dd[dd.index.year == yr], cfg, h + 20) for yr in sorted(set(dd.index.year))}
            r[cname] = e
        sign_disc = frozen.get(f"h{h}") if frozen else None
        est = r["all_matched"]["incremental_ic_m1_minus_m0"]
        r["verdict_inputs"] = {"mean": est["mean"], "lo": est["lo"], "hi": est["hi"]}
        res[f"h{h}"] = r
    return res


def coef_summary(logs: dict, feat: str, period) -> dict:
    out = {}
    lo, hi = pd.Timestamp(period[0]), pd.Timestamp(period[1])
    for h, fits in logs.items():
        c = [f["coef"][feat] for f in fits if lo <= pd.Timestamp(f["month"]) <= hi]
        out[f"h{h}"] = {"months": len(c), "mean_coef": float(np.mean(c)) if c else None,
                        "share_negative": float(np.mean([x < 0 for x in c])) if c else None}
    return out


def verdict(est, disc_est, mei, coef_ok):
    if est["lo"] is None:
        return "inconclusive"
    if est["hi"] < mei:
        return "ruled out"
    if est["mean"] >= mei and est["lo"] > 0 and disc_est is not None and disc_est["mean"] > 0 and coef_ok:
        return "supportive"
    return "inconclusive"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("phase", choices=("discovery", "test"))
    phase = ap.parse_args().phase
    cfg = panel.load_config()
    fcfg = fcfg_load()
    amap = json.loads((REPO / fcfg["map"]).read_text(encoding="utf-8"))
    fcfg["_delisted"] = [k for k, v in amap.items() if v.get("hyperliquid_delisted")]
    chash = combined_hash(cfg, {k: v for k, v in fcfg.items() if not k.startswith("_")}, amap)
    base, _ = base_run.load_long(cfg, "base")
    root = panel.expand(fcfg["funding_root"])
    period = cfg[phase]
    dpath = WORK / "results_discovery_funding.json"
    frozen, thresholds, ev_signs = None, None, None
    if phase == "test":
        if not dpath.exists():
            raise SystemExit("Refusing to run the test phase: no funding discovery result exists.")
        disc = json.loads(dpath.read_text(encoding="utf-8"))
        if disc["config_hash"] != chash:
            raise SystemExit("Refusing to run the test phase: configuration differs from the discovery run.")
        thresholds, ev_signs = disc["btc30_tercile_thresholds"], disc["events"]
    end = str(pd.Timestamp(cfg["test"][1]).to_period("M").start_time.date()) if phase == "test" else str(
        pd.Timestamp(cfg["discovery"][1]).to_period("M").start_time.date())
    out = {"phase": phase, "config_hash": chash, "code_commit": base_run.git_head(), "variants": {}}
    # matched rows, primary lag
    dm, per_product = funding.build_matched(base, amap, root, fcfg, fcfg["primary_lag_days"])
    n0 = len(dm)
    dm = dm[dm["n_matched_day"] >= cfg["min_cross_section"]]
    dates = dm.index.get_level_values("date")
    out["matched"] = {"rows_with_valid_funding_feature": n0, "rows_after_20_coin_day_rule": int(len(dm)),
                      "products_with_matched_rows": int(dm.index.get_level_values("product").nunique()),
                      "first_date": str(dates.min().date()), "last_date": str(dates.max().date()),
                      "rows_in_period": int(inwin(dm, period).sum()),
                      "mean_coins_per_day_in_period": float(dm[inwin(dm, period)].groupby(level="date").size().mean()),
                      "min_coins_per_day_in_period": int(dm[inwin(dm, period)].groupby(level="date").size().min()),
                      "weeks_in_period": int(len(set(ev.week_key(dm[inwin(dm, period)].index.get_level_values("date").unique())))),
                      "baseline_eligible_rows_for_approved_products": int(base.index.get_level_values("product").isin(list(amap)).sum())}
    out["per_product"] = per_product
    if phase == "discovery":
        d_in = dm[inwin(dm, period)]
        out["btc30_tercile_thresholds"] = [float(x) for x in d_in["btc30"].groupby(level="date").first().quantile([1 / 3, 2 / 3])]
        thresholds = out["btc30_tercile_thresholds"]
    # context model: baseline fitted on the full eligible universe (as in the baseline results)
    full_preds = {}
    for h in cfg["horizons_days"]:
        p, _, _ = walk_forward(base, h, cfg, "2023-01-01", end)
        full_preds[h] = p.reindex(dm.index)
    p0, p1, c1, l0, l1 = run_variant(dm, "fz", cfg, end, full_preds)
    ev_primary = evaluate_variant(dm, "fz", p0, p1, full_preds, cfg, fcfg, period, None, thresholds, "primary")
    out["variants"]["primary_lag_1d"] = ev_primary
    out["fz_coefficient"] = coef_summary(l1, "fz", period)
    out["walk_forward_first_fit"] = {f"h{h}": (l1[h][0]["month"] if l1[h] else None) for h in l1}
    # sensitivity: same-day window
    dm_sd, _ = funding.build_matched(base, amap, root, fcfg, fcfg["sensitivity_lag_days"], tag="_sd")
    dm_sd = dm_sd[dm_sd["n_matched_day"] >= cfg["min_cross_section"]]
    s0, s1, _, _, ls1 = run_variant(dm_sd.rename(columns={"z_fz_sd": "z_fz_sd"}), "fz_sd", cfg, end, None)
    out["variants"]["same_day_window"] = evaluate_variant(dm_sd, "fz_sd", s0, s1, None, cfg, fcfg, period, None, thresholds, "same_day")
    out["variants"]["same_day_window"]["matched_rows_in_period"] = int(inwin(dm_sd, period).sum())
    # verdicts
    if phase == "test":
        for h in cfg["horizons_days"]:
            est = ev_primary[f"h{h}"]["verdict_inputs"]
            disc_est = disc["variants"]["primary_lag_1d"][f"h{h}"]["verdict_inputs"]
            coefs_t, coefs_d = out["fz_coefficient"][f"h{h}"]["mean_coef"], disc["fz_coefficient"][f"h{h}"]["mean_coef"]
            coef_ok = coefs_t is not None and coefs_d is not None and np.sign(coefs_t) == np.sign(coefs_d)
            ev_primary[f"h{h}"]["verdict"] = verdict(est, disc_est, fcfg["min_effect_of_interest_ic_difference"], coef_ok)
            ev_primary[f"h{h}"]["discovery_difference_mean"] = disc_est["mean"]
            ev_primary[f"h{h}"]["coefficient_sign_same_in_discovery_and_test"] = bool(coef_ok)
    # extreme-funding events
    ev_s = pd.Series("", index=dm.index)
    ev_s[dm["fz_raw"] >= fcfg["extreme_z"]] = "high_funding"
    ev_s[dm["fz_raw"] <= -fcfg["extreme_z"]] = "low_funding"
    eff = ev.event_effects(dm, ev_s, cfg, period, classes=("high_funding", "low_funding"))
    for cls, v in eff.items():
        for h in cfg["horizons_days"]:
            est = v.get(f"h{h}_vs_clean_controls_pp")
            if phase == "discovery":
                v[f"h{h}_frozen_sign"] = None if not est or est.get("mean") is None else int(np.sign(est["mean"]))
            else:
                s = ev_signs[cls].get(f"h{h}_frozen_sign")
                v[f"h{h}_frozen_sign"] = s
                if est and est.get("mean") is not None and s is not None:
                    excl = est["lo"] > 0 or est["hi"] < 0
                    v[f"h{h}_status"] = "supportive" if (np.sign(est["mean"]) == s and excl) else (
                        "sign reversed vs discovery" if np.sign(est["mean"]) != s and excl else "inconclusive")
    out["events"] = eff
    out["fit_log_primary"] = {f"h{h}": l1[h] for h in l1}
    # secondary (amendment A1): funding added to the strong full-universe baseline score, fitted on the matched rows
    stacked = {}
    mm_all = inwin(dm, period)
    for h in cfg["horizons_days"]:
        col = f"m0f{h}"
        g = full_preds[h].dropna().groupby(level="date")
        r = g.rank(method="average")
        nn = g.transform("count")
        z = pd.Series(np.nan, index=dm.index)
        ok = r.index
        z.loc[ok] = panel.norm_ppf(((r - 0.5) / nn).clip(1e-6, 1 - 1e-6).to_numpy())
        dm["z_" + col] = z
        pa, _, la = walk_forward(dm, h, cfg, START, end, [col])
        pb, _, lb = walk_forward(dm, h, cfg, START, end, [col, "fz"])
        y = dm[f"y{h}"]
        ia, ib = daily_ic(pa[mm_all], y[mm_all], cfg["min_cross_section"]), daily_ic(pb[mm_all], y[mm_all], cfg["min_cross_section"])
        stacked[f"h{h}"] = {"full_baseline_score_alone": ev.ic_summary(ia, cfg, h + 40),
                            "full_baseline_score_plus_funding": ev.ic_summary(ib, cfg, h + 41),
                            "increment": diff_summary(ib, ia, cfg, h + 42),
                            "funding_coefficient": coef_summary({h: lb}, "fz", period)[f"h{h}"]}
    out["stacked_secondary_amendment_A1"] = stacked
    # sample scores on the latest decision date (test phase)
    if phase == "test":
        last = dm.index.get_level_values("date").max()
        rows = []
        sc = {(k, h): to_score(v[h]) for k, v in (("m0", p0), ("m1", p1)) for h in cfg["horizons_days"]}
        day = dm[dm.index.get_level_values("date") == last]
        sel = list(day.sort_values("fz_raw").index[-3:]) + list(day.sort_values("fz_raw").index[:3])
        for name in ("ETH-USD", "SOL-USD", "XRP-USD", "DOGE-USD", "ADA-USD", "LINK-USD", "AVAX-USD"):
            if (last, name) in day.index and (last, name) not in sel:
                sel.append((last, name))
        for i in sel:
            rows.append({"product": i[1], "date": str(last.date()), "fz_raw_rolling_z": round(float(day.loc[i, "fz_raw"]), 2),
                         "daily_mean_hourly_funding_pct": round(float(day.loc[i, "fl_raw"]) * 100, 5),
                         "score_1d_m0": None if np.isnan(sc[("m0", 1)][i]) else int(sc[("m0", 1)][i]),
                         "score_1d_m1": None if np.isnan(sc[("m1", 1)][i]) else int(sc[("m1", 1)][i]),
                         "score_7d_m0": None if np.isnan(sc[("m0", 7)][i]) else int(sc[("m0", 7)][i]),
                         "score_7d_m1": None if np.isnan(sc[("m1", 7)][i]) else int(sc[("m1", 7)][i]),
                         "funding_contribution_7d": None if np.isnan(c1[7].loc[i, "c_fz"]) else round(float(c1[7].loc[i, "c_fz"]), 3),
                         "matched_coins_that_day": int(len(day))})
        out["sample_scores"] = rows
    WORK.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    (WORK / f"results_{phase}_funding.json").write_text(json.dumps(out, indent=2, default=float), encoding="utf-8")
    (OUT / f"results_{phase}_funding.json").write_text(json.dumps(out, indent=2, default=float), encoding="utf-8")
    for h in cfg["horizons_days"]:
        e = ev_primary[f"h{h}"]
        print(phase, f"h{h}", "M1-M0", {k: (None if e['verdict_inputs'][k] is None else round(e['verdict_inputs'][k], 4)) for k in ("mean", "lo", "hi")},
              e.get("verdict"))


if __name__ == "__main__":
    main()
