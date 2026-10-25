"""Driver: build, discovery, test, report.

    python scripts/scoring_experiment/run.py build
    python scripts/scoring_experiment/run.py discovery
    python scripts/scoring_experiment/run.py test        # refuses without a matching discovery file
    python scripts/scoring_experiment/run.py report

Reads only the frozen daily panel. Writes pickles under ~/.moonwalking/analysis/scoring_baseline
and small JSON/Markdown results under docs/research/results/scoring_baseline. Never touches
production code, stores, or the network.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import evaluate as ev  # noqa: E402
import panel  # noqa: E402
from model import daily_ic, to_score, walk_forward  # noqa: E402

REPO = HERE.parents[1]
WORK = Path.home() / ".moonwalking" / "analysis" / "scoring_baseline"
OUT = REPO / "docs" / "research" / "results" / "scoring_baseline"
SAMPLE_COINS = ["ETH-USD", "SOL-USD", "XRP-USD", "DOGE-USD", "ADA-USD", "LINK-USD", "AVAX-USD", "RENDER-USD", "RNDR-USD"]


def overrides(cfg: dict, args) -> dict:
    cfg = json.loads(json.dumps(cfg))
    if getattr(args, "min_history", None):
        cfg["min_history_days"] = args.min_history
        cfg["min_usable_days_in_window"] = int(round(args.min_history * 80 / 90))
    return cfg


def git_head() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True, text=True).stdout.strip()
    except OSError:
        return "unknown"


def tag_of(args) -> str:
    return getattr(args, "tag", None) or "base"


def build(cfg: dict, tag: str) -> pd.DataFrame:
    root = panel.expand(cfg["panel_root"])
    frames, prov = panel.load_raw_frames(root)
    built = panel.build_features(frames, cfg)
    df = panel.stack_long(built, cfg)
    quality = json.loads((root / "QUALITY_REPORT.json").read_text(encoding="utf-8"))
    funding = {c["product_id"] for c in quality["funding_candidates"]["with_daily_candles"]}
    df["in_funding"] = df.index.get_level_values("product").isin(funding)
    n_before = len(df)
    thin_days = int((df["n_day"] < cfg["min_cross_section"]).sum())
    df = df[df["n_day"] >= cfg["min_cross_section"]]
    info = {"provenance": prov, "exclusions": built["exclusions"],
            "rows_dropped_for_small_cross_section": thin_days, "rows_eligible_after_cross_section_rule": len(df),
            "rows_before_cross_section_rule": n_before, "funding_candidate_products": len(funding),
            "funding_rows": int(df["in_funding"].sum()), "config_hash": panel.config_hash(cfg)}
    WORK.mkdir(parents=True, exist_ok=True)
    df.to_pickle(WORK / f"long_{tag}.pkl")
    (WORK / f"build_{tag}.json").write_text(json.dumps(info, indent=2, default=float), encoding="utf-8")
    print(json.dumps(info, indent=2, default=float))
    return df


def load_long(cfg, tag):
    p = WORK / f"long_{tag}.pkl"
    if not p.exists():
        raise SystemExit("run `build` first")
    info = json.loads((WORK / f"build_{tag}.json").read_text(encoding="utf-8"))
    if info["config_hash"] != panel.config_hash(cfg):
        raise SystemExit("config changed since build; rebuild")
    # Local cache written by `build` on this machine from the verified panel; never loaded from elsewhere.
    return pd.read_pickle(p), info


def subsets(df):
    return {"all": np.ones(len(df), bool), "funding_candidates": df["in_funding"].to_numpy(),
            "excluding_thin": (df["thin"] == 0).to_numpy()}


def evaluate_phase(df, preds, scores, contribs, cfg, period, frozen, thresholds):
    d0, d1 = pd.Timestamp(period[0]), pd.Timestamp(period[1])
    date = df.index.get_level_values("date")
    inwin = (date >= d0) & (date <= d1)
    res = {"period": list(period)}
    mei = cfg["min_effect_of_interest_ic"]
    sets = subsets(df)
    comparators = {"reversal_neg_r1": -df["r1"], "momentum_res7": df["res7"], "extension_neg_ext30": -df["ext30"]}
    rng = np.random.default_rng(cfg["bootstrap"]["seed"])
    ic_store = {}
    for h in cfg["horizons_days"]:
        y = df[f"y{h}"]
        r = {}
        pm = preds[h]
        for sname, smask in sets.items():
            m = inwin & smask
            sub_y, sub_p = y[m], pm[m]
            primary = daily_ic(sub_p, sub_y, cfg["min_cross_section"])
            ic_store[(h, sname, "model")] = primary
            entry = {"model": ev.ic_summary(primary, cfg, h, moving=True)}
            if sname == "all":
                # one decision weekday at a time: each phase's labels never overlap (entry d+1, exit d+1+h)
                phases = {}
                for w, name in enumerate(["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]):
                    pw = primary[primary.index.dayofweek == w]
                    phases[name] = ev.boot(pw.reset_index(drop=True), cfg, h * 10 + w)
                entry["model_by_weekday_phase"] = phases
                entry["phases_with_interval_excluding_zero"] = int(sum(
                    1 for v in phases.values() if v["lo"] is not None and (v["lo"] > 0 or v["hi"] < 0)))
            for cn, cv in comparators.items():
                ic = daily_ic(cv[m], sub_y, cfg["min_cross_section"])
                ic_store[(h, sname, cn)] = ic
                e = ev.ic_summary(ic, cfg, h + 3)
                both = pd.concat([primary, ic], axis=1, keys=["a", "b"]).dropna()
                diff = ev.boot(ev.weekly(both["a"] - both["b"]), cfg, h + 9)
                e["model_minus_this_weekly_ic"] = {k: diff.get(k) for k in ("mean", "lo", "hi", "n_blocks")}
                entry[cn] = e
            shuf = sub_y.copy()
            day = shuf.index.get_level_values("date")
            shuf = pd.Series(shuf.groupby(day).transform(lambda s: rng.permutation(s.to_numpy())), index=shuf.index)
            entry["shuffled_label_null"] = ev.ic_summary(daily_ic(sub_p, shuf, cfg["min_cross_section"]), cfg, h + 5)
            r[sname] = entry
        base = ic_store[(h, "all", "model")]
        key = f"h{h}"
        sign = frozen.get(key) if frozen else (1 if r["all"]["model"]["mean"] and r["all"]["model"]["mean"] > 0 else -1)
        res.setdefault("primary", {})[key] = {"estimate": r["all"]["model"], "frozen_sign": int(sign),
                                              "verdict": ev.verdict(r["all"]["model"], int(sign), mei),
                                              "moving_block_4w_interval_excludes_zero": bool(
                                                  r["all"]["model"]["moving_block"]["lo"] is not None and
                                                  (r["all"]["model"]["moving_block"]["lo"] > 0 or
                                                   r["all"]["model"]["moving_block"]["hi"] < 0)),
                                              "weekday_phases_excluding_zero": r["all"]["phases_with_interval_excluding_zero"]}
        r["deciles"] = ev.decile_table(df[inwin], scores[h][inwin], f"y{h}", f"yraw{h}", f"rawret{h}", cfg)
        spread = ev.spread_series(df[inwin], scores[h][inwin], f"y{h}")
        r["top_decile_minus_bottom_decile_scaled_residual"] = ev.boot(ev.weekly(spread), cfg, h + 20)
        if h == 7:
            r["top_quintile_weekly_excess"] = ev.staggered_sleeves(df[inwin], scores[h][inwin], h,
                                                                    cfg["cost_scenarios_pct_round_trip"], cfg)
        # regimes (terciles frozen from discovery)
        reg = pd.cut(df["btc30"], [-np.inf, thresholds[0], thresholds[1], np.inf], labels=["down", "flat", "up"])
        rr = {}
        for name in ("down", "flat", "up"):
            ic = base[[d in set(reg[reg == name].index.get_level_values("date")) for d in base.index]]
            e = ev.ic_summary(ic, cfg, h + 30)
            e["interpretable"] = e["n_blocks"] >= cfg["min_blocks_for_regime"]
            rr[name] = e
        r["by_btc_30d_regime"] = rr
        yrs = {}
        for yr in sorted(set(base.index.year)):
            yrs[str(yr)] = ev.ic_summary(base[base.index.year == yr], cfg, h + 40)
        r["by_calendar_year"] = yrs
        cov = df["coverage"]
        cb = {}
        for name, mask in (("complete_100", (cov >= 99.999).to_numpy()), ("below_100", (cov < 99.999).to_numpy())):
            m = inwin & mask
            cb[name] = {**ev.ic_summary(daily_ic(pm[m], y[m], cfg["min_cross_section"]), cfg, h + 50),
                        "share_of_rows": float(mask[inwin].mean()),
                        "coverage_range": [float(cov[m].min()), float(cov[m].max())] if m.any() else None}
        r["by_evidence_coverage"] = cb
        res[f"h{h}"] = r
    # risk rank vs forward absolute residual move
    risk = df.groupby(level="date")["vol30"].rank(pct=True)
    rk = {}
    for h in cfg["horizons_days"]:
        absy = df[f"yraw{h}"].abs()
        ic = daily_ic(risk[inwin], absy[inwin], cfg["min_cross_section"])
        rk[f"h{h}"] = ev.ic_summary(ic, cfg, h + 60)
        thin_ratio = absy[inwin & (df["thin"] == 1).to_numpy()].mean() / absy[inwin & (df["thin"] == 0).to_numpy()].mean()
        rk[f"h{h}"]["thin_over_nonthin_mean_abs_residual"] = float(thin_ratio)
    res["risk_rank_vs_forward_absolute_residual_move"] = rk
    # events
    evs = ev.flag_events(df, cfg)
    res["events"] = ev.event_effects(df, evs, cfg, period)
    return res


def drop_one(df, cfg, start, end, period):
    out = {}
    d0, d1 = pd.Timestamp(period[0]), pd.Timestamp(period[1])
    date = df.index.get_level_values("date")
    inwin = (date >= d0) & (date <= d1)
    for g, members in panel.FACTOR_GROUPS.items():
        feats = [f for f in panel.FEATURES if f not in members]
        out[g] = {}
        for h in cfg["horizons_days"]:
            p, _, _ = walk_forward(df, h, cfg, start, end, feats)
            ic = daily_ic(p[inwin], df[f"y{h}"][inwin], cfg["min_cross_section"])
            out[g][f"h{h}"] = ev.ic_summary(ic, cfg, h + 70)
    return out


def sample_table(df, preds, scores, contribs, cfg, horizon_for_drivers=7, date=None):
    date = date or df.index.get_level_values("date").max()
    day = df[df.index.get_level_values("date") == date]
    if day.empty:
        return []
    prods = day.index.get_level_values("product")
    risk = day["vol30"].rank(pct=True) * 100
    rows = []
    s7, s1 = scores[7], scores[1]
    chosen = [p for p in SAMPLE_COINS if p in set(prods)]
    ranked = s7[day.index].dropna().sort_values()
    for p in list(ranked.index.get_level_values("product")[-3:]) + list(ranked.index.get_level_values("product")[:3]):
        if p not in chosen:
            chosen.append(p)
    for p in chosen:
        i = (date, p)
        c = contribs[7].loc[i].dropna().sort_values(key=abs, ascending=False).head(3)
        flags = []
        if day.loc[i, "thin"] == 1:
            flags.append("thin liquidity")
        if day.loc[i, "vol30"] > 0.08:
            flags.append("very high volatility")
        rows.append({"product": p, "date": str(pd.Timestamp(date).date()),
                     "score_1d": None if np.isnan(s1[i]) else int(s1[i]),
                     "score_7d": None if np.isnan(s7[i]) else int(s7[i]),
                     "top_drivers_7d": {k[2:]: round(float(v), 3) for k, v in c.items()},
                     "evidence_coverage": round(float(day.loc[i, "coverage"]), 1),
                     "risk_rank_pct": round(float(risk[i]), 1), "vol30_daily_pct": round(float(day.loc[i, "vol30"] * 100), 2),
                     "flags": flags, "eligible_coins_that_day": int(len(day))})
    return rows


def run_phase(phase: str, args):
    cfg = overrides(panel.load_config(), args)
    tag = tag_of(args)
    df, info = load_long(cfg, tag)
    period = cfg[phase]
    frozen, thresholds = None, None
    dpath = WORK / f"results_discovery_{tag}.json"
    if phase == "test":
        if not dpath.exists():
            raise SystemExit("Refusing to run the test phase: no discovery result exists.")
        disc = json.loads(dpath.read_text(encoding="utf-8"))
        if disc["config_hash"] != panel.config_hash(cfg):
            raise SystemExit("Refusing to run the test phase: config differs from the discovery run.")
        frozen = {k: v["frozen_sign"] for k, v in disc["evaluation"]["primary"].items()}
        thresholds = disc["btc30_tercile_thresholds"]
        ev_frozen = disc["evaluation"]["events"]
    else:
        date = df.index.get_level_values("date")
        m = (date >= pd.Timestamp(period[0])) & (date <= pd.Timestamp(period[1]))
        d_btc = df["btc30"][m].groupby(level="date").first()
        thresholds = [float(x) for x in d_btc.quantile([1 / 3, 2 / 3])]
        ev_frozen = None
    start = "2023-01-01" if phase == "discovery" else "2023-01-01"
    end = str(pd.Timestamp(period[1]).to_period("M").start_time.date())
    preds, contribs, scores, logs = {}, {}, {}, {}
    for h in cfg["horizons_days"]:
        preds[h], contribs[h], logs[h] = walk_forward(df, h, cfg, start, end)
        scores[h] = to_score(preds[h])
    evaluation = evaluate_phase(df, preds, scores, contribs, cfg, period, frozen, thresholds)
    if phase == "discovery":
        # event sign freeze
        for cls, v in evaluation["events"].items():
            for h in cfg["horizons_days"]:
                est = v.get(f"h{h}_vs_clean_controls_pp")
                v[f"h{h}_frozen_sign"] = None if not est or est.get("mean") is None else int(np.sign(est["mean"]))
    else:
        for cls, v in evaluation["events"].items():
            for h in cfg["horizons_days"]:
                s = ev_frozen[cls].get(f"h{h}_frozen_sign")
                est = v.get(f"h{h}_vs_clean_controls_pp")
                v[f"h{h}_frozen_sign"] = s
                if est and est.get("mean") is not None and s is not None:
                    excl = est["lo"] > 0 or est["hi"] < 0
                    v[f"h{h}_status"] = "supportive" if (np.sign(est["mean"]) == s and excl) else (
                        "sign reversed vs discovery" if np.sign(est["mean"]) != s and excl else "inconclusive")
                    v[f"h{h}_exceeds_cost_scenarios_pct"] = [c for c in cfg["cost_scenarios_pct_round_trip"]
                                                             if abs(est["mean"]) > c]
    out = {"phase": phase, "tag": tag, "config_hash": panel.config_hash(cfg), "code_commit": git_head(),
           "input": info["provenance"].get("manifest_sha256"), "build": {k: info[k] for k in
                                                                         ("exclusions", "rows_dropped_for_small_cross_section",
                                                                          "rows_eligible_after_cross_section_rule", "funding_rows")},
           "btc30_tercile_thresholds": thresholds, "evaluation": evaluation,
           "walk_forward_fits": {f"h{h}": logs[h] for h in logs}}
    if phase == "test":
        out["drop_one_factor_group"] = drop_one(df, cfg, start, end, period)
        out["sample_scores"] = sample_table(df, preds, scores, contribs, cfg)
        out["sample_scores_latest_date"] = out["sample_scores"][0]["date"] if out["sample_scores"] else None
        # keep latest-date scores for reproducibility
        last = df.index.get_level_values("date").max()
        snap = pd.DataFrame({"score_1d": scores[1], "score_7d": scores[7]}).loc[lambda x: x.index.get_level_values("date") == last]
        OUT.mkdir(parents=True, exist_ok=True)
        snap.to_csv(OUT / f"scores_{last.date()}_{tag}.csv")
    WORK.mkdir(parents=True, exist_ok=True)
    (WORK / f"results_{phase}_{tag}.json").write_text(json.dumps(out, indent=2, default=float), encoding="utf-8")
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"results_{phase}_{tag}.json").write_text(json.dumps(out, indent=2, default=float), encoding="utf-8")
    pm = out["evaluation"]["primary"]
    print(phase, tag, {k: (round(v["estimate"]["mean"], 4), v["verdict"]) for k, v in pm.items()})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("action", choices=("build", "discovery", "test", "report"))
    ap.add_argument("--min-history", type=int)
    ap.add_argument("--tag")
    args = ap.parse_args()
    if args.min_history and not args.tag:
        args.tag = f"hist{args.min_history}"
    cfg = overrides(panel.load_config(), args)
    if args.action == "build":
        build(cfg, tag_of(args))
    elif args.action in ("discovery", "test"):
        run_phase(args.action, args)


if __name__ == "__main__":
    main()
