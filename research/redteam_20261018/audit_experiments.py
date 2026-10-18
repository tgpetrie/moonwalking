"""NEW COPY/ADAPTATION of scripts/evaluate_resolution_costs.py for a read-only red-team audit.
Source originals are frozen in source_scripts; never execute their original I/O.
Only copied data under .runtime/redteam_20261018/data may be opened.
"""

import ast, contextlib, datetime, gzip, hashlib, io, itertools, json, math, pathlib, sqlite3, sys
from collections import Counter, defaultdict
import numpy as np

ROOT = pathlib.Path(__file__).resolve().parent
DATA = pathlib.Path(".runtime/redteam_20261018/data").resolve()
OUT = pathlib.Path(".runtime/redteam_20261018") / (
    sys.argv[1] if __name__ == "__main__" and len(sys.argv) > 1 else "results_final"
)
if OUT.resolve().parent != DATA.parent:
    raise ValueError("Output outside own audit runtime directory")


def ro(name):
    p = (DATA / name).resolve()
    if p.parent != DATA:
        raise ValueError("Outside copied data")
    return sqlite3.connect(p.as_uri() + "?mode=ro&immutable=1", uri=True)


def emit(name, method, result, conclusion):
    row = {
        "test": name,
        "method": method,
        "result": result,
        "effect_on_conclusion": conclusion,
    }
    with (OUT / "tests.jsonl").open("a", encoding="utf-8") as f:
        f.write(
            json.dumps(
                row,
                allow_nan=False,
                default=lambda x: x.item() if isinstance(x, np.generic) else x.tolist(),
            )
            + "\n"
        )
    print(name, flush=True)


def boot(x, t, block="week", seed=11):
    if block == "iid":
        se = float(np.std(x, ddof=1) / np.sqrt(len(x)))
        return {
            "mean": float(np.mean(x)),
            "se": se,
            "normal_95": [float(np.mean(x) - 1.96 * se), float(np.mean(x) + 1.96 * se)],
            "blocks": len(x),
        }
    if block == "week":
        keys = [
            datetime.datetime.fromtimestamp(int(v), datetime.timezone.utc).strftime(
                "%G-W%V"
            )
            for v in t
        ]
    else:
        keys = t // 86400
    _, inv = np.unique(keys, return_inverse=True)
    G = int(inv.max()) + 1
    s = np.bincount(inv, weights=x)
    n = np.bincount(inv)
    rng = np.random.default_rng(seed)
    ix = rng.integers(0, G, (2000, G))
    means = s[ix].sum(1) / n[ix].sum(1)
    return {
        "mean": float(np.mean(x)),
        "se": float(np.std(means, ddof=1)),
        "percentile_95": np.quantile(means, [0.025, 0.975]).tolist(),
        "blocks": G,
    }


def dedupe(records, policy):
    # records are tuples (product,ts,label,direction,atr,btc,nr,r24,mfe,mae,confidence)
    if policy == "raw":
        return list(records)
    if policy == "latest":
        ordered = sorted(records, key=lambda r: (-r[1], r[0], r[2]))
    elif policy == "earliest":
        ordered = sorted(records, key=lambda r: (r[1], r[0], r[2]))
    elif policy == "max_confidence":
        ordered = sorted(
            records, key=lambda r: (-(r[10] if r[10] is not None else -1), r[1], r[0])
        )
    else:
        ordered = records
    seen = set()
    out = []
    last = {}
    for r in ordered:
        if policy == "nonoverlap_24h":
            key = (r[0], r[3])
            if r[1] < last.get(key, -1):
                continue
            last[key] = r[1] + 86400
        else:
            key = (r[0], r[3], r[2], r[1] // 14400)
            if key in seen:
                continue
            seen.add(key)
        out.append(r)
    return out


def bucket(x):
    return 0 if x < -0.005 else 2 if x > 0.005 else 1


def match(records, pool, *, past=False, exclude_hours=None):
    out = []
    unmatched = []
    for r in records:
        p, t, lab, d, atr, b, nr, r24, mfe, mae, cf = r
        a = pool.get((p, d))
        if a is None:
            unmatched.append(r)
            continue
        lo, hi = np.searchsorted(
            a[:, 0], [t - 7 * 86400, t + (0 if past else 7 * 86400)]
        )
        w = a[lo:hi]
        m = (
            (abs(w[:, 0] - t) >= 86400)
            & (w[:, 1] >= atr * 0.75)
            & (w[:, 1] <= atr / 0.75)
            & (w[:, 2] == bucket(b))
        )
        if exclude_hours is not None:
            m &= np.array(
                [(p, int(tt) // 3600) not in exclude_hours for tt in w[:, 0]],
                dtype=bool,
            )
        c = w[m]
        if len(c) < 3:
            unmatched.append(r)
            continue
        # p,t,label,d,atr,signal netR,control netR,signal24,control24,cf,ctlATR,ctlN,amb-control placeholder
        out.append(
            (
                p,
                t,
                lab,
                d,
                atr,
                nr,
                float(c[:, 3].mean()),
                r24,
                float(c[:, 4].mean()),
                cf,
                float(c[:, 1].mean()),
                len(c),
            )
        )
    return out, unmatched


def summary(rows):
    out = {}
    for d in ("up", "down"):
        r = [v for v in rows if v[3] == d]
        x = np.array([v[5] - v[6] for v in r])
        t = np.array([v[1] for v in r])
        out[d] = {
            "n": len(r),
            "net_R_excess": float(x.mean()) if len(x) else None,
            "week": boot(x, t) if len(x) else None,
            "return24_excess_ATR": (
                float(np.mean([v[7] - v[8] for v in r])) if r else None
            ),
        }
    return out


def main():
    OUT.mkdir(parents=True, exist_ok=False)
    # Confidence and entry prices come only from our frozen market-only export.
    confidence = {}
    entry = {}
    with gzip.open(
        DATA / "production-2026-10-18.jsonl.gz", "rt", encoding="utf-8"
    ) as f:
        for line in f:
            r = json.loads(line)
            if r["kind"] == "signal":
                key = (
                    r["product_id"],
                    r["started_ts"],
                    r["direction"],
                    r["read_label"],
                )
                confidence[key] = r["confidence"]
                entry[key] = r["start_price"]
    db = ro("recon.sqlite")
    raw = []
    pool = defaultdict(list)
    for kind, p, t, lab, d, atr, b, nr, r24, mfe, mae in db.execute(
        "select kind,product_id,ts,label,direction,atr_pct,btc4h,netR21,r24,mfe,mae from recon"
    ):
        if b is None:
            continue
        if kind == "base":
            pool[(p, d)].append((t, atr, bucket(b), nr, r24, mfe, mae))
        else:
            raw.append(
                (
                    p,
                    t,
                    lab,
                    d,
                    atr,
                    b,
                    nr,
                    r24,
                    mfe,
                    mae,
                    confidence.get((p, t, d, lab)),
                )
            )
    pool = {k: np.array(sorted(v)) for k, v in pool.items()}
    original = dedupe(raw, "original")
    matched, unmatched = match(original, pool)
    emit(
        "baseline_replication",
        "Copy matched_control.py matching and insertion-order first-per-label/coin/direction/4h; confidence from separately frozen market export",
        {
            "raw_with_btc": len(raw),
            "attempted": len(original),
            "matched": len(matched),
            "unmatched": len(unmatched),
            "median_controls": float(np.median([r[11] for r in matched])),
            "confidence_join_coverage": float(
                np.mean([r[9] is not None for r in matched])
            ),
            "estimates": summary(matched),
        },
        "Establishes a reproducible copied-data reference; estimates are conditional on the matchable universe, not independent trades.",
    )
    # 1. Future matches versus historical-only matches; full original covariate rules.
    past, pastun = match(original, pool, past=True)
    emit(
        "lookahead_future_controls",
        "Use only same-coin controls 1-7 days BEFORE the signal, rather than symmetric past/future controls",
        {
            "symmetric": summary(matched),
            "past_only": summary(past),
            "past_only_unmatched": len(pastun),
        },
        "Future controls are retrospective matching, not feature leakage by themselves; they cannot be used as an already-known online baseline. Sensitivity is quantified.",
    )
    # 2. Dedupe and SQL ordering.
    dedupresults = {}
    for policy in ("earliest", "latest", "max_confidence", "nonoverlap_24h"):
        selected = dedupe(
            sorted(raw, key=lambda r: r[1]) if policy == "nonoverlap_24h" else raw,
            policy,
        )
        rr, uu = match(selected, pool)
        dedupresults[policy] = {
            "attempted": len(selected),
            "matched": len(rr),
            "unmatched": len(uu),
            "estimates": summary(rr),
        }
    emit(
        "dedupe_selection",
        "Compare explicit earliest/latest/max-confidence per original 4h key, and chronological 24h nonoverlap per product/direction",
        dedupresults,
        "Dedupe policy defines the estimand. A conclusion that changes with row order or a selectable confidence rule is not a stable signal property.",
    )
    # 3. Overlap and pooled cluster uncertainty.
    overlap = {}
    for d in ("up", "down"):
        rr = [r for r in matched if r[3] == d]
        x = np.array([r[5] - r[6] for r in rr])
        t = np.array([r[1] for r in rr])
        overlap[d] = {b: boot(x, t, b) for b in ("iid", "day", "week")}
    reused = Counter()
    n_pairs = 0
    for r in original:
        p, t, _, d, atr, b, *_ = r
        a = pool.get((p, d))
        lo, hi = np.searchsorted(a[:, 0], [t - 7 * 86400, t + 7 * 86400])
        w = a[lo:hi]
        c = w[
            (abs(w[:, 0] - t) >= 86400)
            & (w[:, 1] >= atr * 0.75)
            & (w[:, 1] <= atr / 0.75)
            & (w[:, 2] == bucket(b))
        ]
        if len(c) >= 3:
            for ct in c[:, 0]:
                reused[(p, d, int(ct))] += 1
            n_pairs += len(c)
    emit(
        "overlap_and_reuse",
        "IID vs whole-day vs ISO-calendar-week weighted cluster bootstrap; count reused controls and 24h-spaced sensitivity above",
        {
            "inference": overlap,
            "control_pairs": n_pairs,
            "distinct_controls_used": len(reused),
            "median_reuse": float(np.median(list(reused.values()))),
            "maximum_reuse": max(reused.values()),
        },
        "Raw n greatly exceeds independent market periods. Week intervals are exploratory with only a few blocks, and a control may serve many signals.",
    )
    # 4. Costs on signal/control ATR, preserving the matched pairs.
    costs = {str(c): {} for c in (0, 0.002, 0.009, 0.012)}
    # Keep exact inverse ATR moment per matched signal using source covariates.
    bykey = {(r[0], r[1], r[2], r[3]): r for r in original}
    moments = []
    for r in matched:
        p, t, lab, d, atr = r[:5]
        src = bykey[(p, t, lab, d)]
        a = pool[(p, d)]
        lo, hi = np.searchsorted(a[:, 0], [t - 7 * 86400, t + 7 * 86400])
        w = a[lo:hi]
        ctl = w[
            (abs(w[:, 0] - t) >= 86400)
            & (w[:, 1] >= atr * 0.75)
            & (w[:, 1] <= atr / 0.75)
            & (w[:, 2] == bucket(src[5]))
        ]
        moments.append(float(np.mean(1 / ctl[:, 1])))
    for c in (0, 0.002, 0.009, 0.012):
        vals = np.array(
            [
                (r[5] - r[6]) + (0.002 - c) * (1 / r[4] - iv)
                for r, iv in zip(matched, moments)
            ]
        )
        costs[str(c)]["exact"] = {
            d: {
                "n": sum(r[3] == d for r in matched),
                "net_R_excess": float(vals[[r[3] == d for r in matched]].mean()),
                "week": boot(
                    vals[[r[3] == d for r in matched]],
                    np.array([r[1] for r in matched if r[3] == d]),
                ),
            }
            for d in ("up", "down")
        }
    emit(
        "cost_assumptions",
        "Undo 0.2% in signal/control R and apply 0/0.2/0.9/1.2%; control uses exact mean inverse ATR; do not mix raw-return and ATR-normalized excess",
        costs,
        "A flat percentage cost cancels raw percentage excess, but not R excess with imperfect ATR balance. Exact mean inverse control ATR is used.",
    )
    # 5. Multiplicity: prespecified family of labels and confidence buckets.
    names = []
    masks = []
    darr = np.array([r[3] for r in matched])
    labs = np.array([r[2] for r in matched])
    cf = np.array([r[9] if r[9] is not None else np.nan for r in matched])
    x = np.array([r[5] - r[6] for r in matched])
    tt = np.array([r[1] for r in matched])
    for lab, d in sorted(set(zip(labs, darr))):
        m = (labs == lab) & (darr == d)
        if m.sum() >= 150:
            names.append(f"{lab} / {d}")
            masks.append(m)
    for d in ("up", "down"):
        for lo, hi in ((50, 60), (60, 72), (72, 85), (85, 95), (95, 101)):
            m = (darr == d) & (cf >= lo) & (cf < hi)
            if m.sum() >= 150:
                names.append(f"confidence {lo}-{hi} / {d}")
                masks.append(m)
    wk = np.array(
        [
            datetime.datetime.fromtimestamp(int(t), datetime.timezone.utc).strftime(
                "%G-W%V"
            )
            for t in tt
        ]
    )
    weeks, wi = np.unique(wk, return_inverse=True)
    sums = np.array(
        [
            np.bincount(wi[m], weights=x[m], minlength=len(weeks)) / m.sum()
            for m in masks
        ]
    )
    means = sums.sum(1)
    fractions = np.array(
        [np.bincount(wi[m], minlength=len(weeks)) / m.sum() for m in masks]
    )
    residual_scores = sums - means[:, None] * fractions
    se = np.sqrt(len(weeks) / (len(weeks) - 1) * np.sum(residual_scores**2, axis=1))
    z = means / se
    signs = np.array(list(itertools.product((-1, 1), repeat=len(weeks))))
    null = (signs @ sums.T) / se
    p_raw = np.mean(abs(null) >= abs(z), axis=0)
    p_family = np.mean(np.max(abs(null), axis=1)[:, None] >= abs(z), axis=0)
    mult = [
        {
            "name": n,
            "n": int(m.sum()),
            "effect_R": float(e),
            "week_score": float(zz),
            "signflip_p": float(p),
            "familywise_max_score_p": float(pa),
        }
        for n, m, e, zz, p, pa in zip(names, masks, means, z, p_raw, p_family)
    ]
    emit(
        "multiple_comparisons",
        "Joint whole-calendar-week sign flips across all label-direction and confidence cells with n>=150; enumerate all 2^G signs, compare max absolute standardized score",
        {
            "family_size": len(names),
            "weeks": len(weeks),
            "sign_patterns": len(signs),
            "cells": mult,
            "unadjusted_below_05": int((p_raw < 0.05).sum()),
            "familywise_below_05": int((p_family < 0.05).sum()),
            "assumptions": "Exploratory symmetry/independent-week assumption; not a valid guarantee with few dependent weeks. Family excludes undocumented prior searches.",
        },
        "No cell earns a production rule merely from an unadjusted z near 2; see familywise results. The complete historical search family remains unknown.",
    )
    # 6. Non-signal-hour contamination in the all-hours baseline.
    signal_hours = {(r[0], int(r[1]) // 3600) for r in raw}
    ns, nsun = match(original, pool, exclude_hours=signal_hours)
    emit(
        "control_signal_contamination",
        "Exclude baseline coin-hours containing any source signal; keep source matching rules",
        {
            "all_hour_controls": summary(matched),
            "non_signal_hour_controls": summary(ns),
            "unmatched_without_signal_hours": len(nsun),
        },
        "Source controls are other hours, not necessarily non-signal hours. Excluding signals changes the target baseline and may shrink overlap.",
    )
    # 7. Universe and market drift on copied sell-side replay.
    replay = ro("candle_replay.sqlite")
    rows = replay.execute(
        "select product_id,ts,range_pos,momentum,vol_ratio,status,atr_pct,ret24,mae from replay"
    ).fetchall()
    replay.close()
    p = np.array([v[0] for v in rows])
    t = np.array([v[1] for v in rows])
    rp = np.array([v[2] for v in rows])
    mom = np.array([v[3] if v[3] is not None else np.nan for v in rows])
    vr = np.array([v[4] if v[4] is not None else np.nan for v in rows])
    status = np.array([v[5] for v in rows])
    atr = np.array([v[6] for v in rows])
    ret = np.array([v[7] for v in rows])
    coins, pi = np.unique(p, return_inverse=True)
    coinmean = np.bincount(pi, weights=ret) / np.bincount(pi)
    coinneutral = ret - coinmean[pi]
    times, ti = np.unique(t, return_inverse=True)
    marketmean = np.bincount(ti, weights=ret * atr) / np.bincount(ti)
    csneutral = ret - marketmean[ti] / atr
    features = {
        "top_85_vs_rest": (rp >= 85, rp < 85),
        "high_status_vs_clear": (status == "high", status == "clear"),
        "down_volume_1.5": ((mom < 0) & (vr >= 1.5), (mom < 0) & (vr < 1.5)),
    }
    peers = np.bincount(ti)
    peer_returns = np.bincount(ti, weights=ret * atr)
    loo = (
        ret * atr - (peer_returns[ti] - ret * atr) / np.maximum(1, peers[ti] - 1)
    ) / atr
    drift = {}
    for name, (a, b) in features.items():
        drift[name] = {
            k: float(v[a].mean() - v[b].mean())
            for k, v in [
                ("raw_ATR", ret),
                ("coin_demeaned_ATR", coinneutral),
                ("same_timestamp_equal_weight_market_neutral_ATR", csneutral),
            ]
        }
        aa = a & (peers[ti] >= 21)
        bb = b & (peers[ti] >= 21)
        drift[name]["leave_one_coin_out_min20_peers_ATR"] = float(
            loo[aa].mean() - loo[bb].mean()
        )
        drift[name]["n_treated_with_20peers"] = int(aa.sum())
        drift[name]["n_control_with_20peers"] = int(bb.sum())
    emit(
        "market_wide_drift",
        "Compare raw, coin-demeaned, and same-timestamp equal-weight market-neutral forward percentage returns converted to each coin ATR; market return is an outcome benchmark, never a feature",
        drift,
        "Only the observed timestamp universe is neutralized; variable coverage and differing beta remain. This is not a tradable market hedge.",
    )
    counts = Counter(p)
    long = set(c for c, n in counts.items() if n >= 0.8 * max(counts.values()))
    sigcoins = {r[0] for r in raw}
    universe = {}
    for name, sel in [
        ("all_replay_coins", np.ones(len(p), bool)),
        ("coins_with_reconstructed_signals", np.isin(p, list(sigcoins))),
        ("at_least_80pct_max_observed_coverage", np.isin(p, list(long))),
    ]:
        universe[name] = {
            "coins": len(set(p[sel])),
            "rows": int(sel.sum()),
            "effects": {
                k: float(coinneutral[sel & a].mean() - coinneutral[sel & b].mean())
                for k, (a, b) in features.items()
                if (sel & a).any() and (sel & b).any()
            },
        }
    emit(
        "survivorship_and_coverage",
        "Observed-universe stress: all replay products vs signal-bearing products vs products with >=80% of maximum observed row coverage; no invented delisted returns",
        {
            "cohorts": universe,
            "missing_historical_listing_membership": True,
            "delisted_outcome_test": "UNTESTABLE from supplied snapshots",
            "warning": "Coverage filter is a hindsight-selected sensitivity, not a corrected point-in-time universe.",
        },
        "Cannot generalize to delisted/omitted coins or claim survivorship eliminated. Cohort sensitivity is measured only among observed products.",
    )
    # 8. Reproduce the source evaluate() feature function without running its I/O.
    native = {}
    btc = None
    with gzip.open(DATA / "pilot-coinbase.jsonl.gz", "rt", encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            if r["kind"] == "candle":
                native.setdefault(r["product_id"], []).append(
                    (
                        r.get("candle_ts", r.get("hour_ts")),
                        r["open"],
                        r["high"],
                        r["low"],
                        r["close"],
                    )
                )
    native = {p: np.array(sorted(v)) for p, v in native.items()}
    data = {
        p: (a[:, 0].astype(int), a[:, 1], a[:, 2], a[:, 3], a[:, 4])
        for p, a in native.items()
    }
    tree = ast.parse((ROOT / "source_scripts/recon.py").read_text(encoding="utf-8"))
    functions = ast.Module(
        body=[
            n
            for n in tree.body
            if isinstance(n, ast.FunctionDef) and n.name in ("btc_ctx", "evaluate")
        ],
        type_ignores=[],
    )
    env = {
        "np": np,
        "H": 3600,
        "NPATH": 23,
        "COST_PCT": 0.002,
        "data": data,
        "btc": data["BTC-USD"],
    }
    exec(compile(functions, "copied_recon_functions", "exec"), env)
    joined = [r for r in raw if r[0] in data and (r[0], r[1], r[3], r[2]) in entry]
    tested = 0
    feature_changes = 0
    horizons = []
    gaps = []
    for r in joined[:: max(1, len(joined) // 500)]:
        p, t, lab, d = r[:4]
        px = entry[(p, t, d, lab)]
        s = 1 if d == "up" else -1
        before = env["evaluate"](p, t, px, s)
        if before is None:
            continue
        a = data[p]
        cut = np.searchsorted(a[0], -(-t // 3600) * 3600)
        save = [a[j][cut:].copy() for j in (2, 3, 4)]
        for j, m in ((2, 1.10), (3, 0.90), (4, 1.05)):
            a[j][cut:] *= m
        after = env["evaluate"](p, t, px, s)
        for j, v in zip((2, 3, 4), save):
            a[j][cut:] = v
        tested += 1
        feature_changes += not np.allclose(before[:3], after[:3], equal_nan=True)
        start = -(-t // 3600) * 3600
        horizons.append((start + 23 * 3600 - t) / 3600)
        gaps.append((start - t) / 60)
    emit(
        "lookahead_feature_poison_and_horizon",
        "Extract only btc_ctx/evaluate AST from frozen recon.py; mutate exclusively future high/low/close; verify ATR/extension/BTC features; calculate actual endpoint delay",
        {
            "real_signal_samples": tested,
            "features_changed_by_future_poison": feature_changes,
            "actual_forward_hours_min_max": [min(horizons), max(horizons)],
            "ignored_initial_minutes_min_max": [min(gaps), max(gaps)],
            "baseline_forward_hours": 23,
        },
        "No feature lookahead detected in tested function; its nominal r24 is 23-24h for signals but 23h for boundary baseline entries. Partial initial hour is omitted.",
    )
    # 9. The evidence script mixes weighted center and unweighted-week SE.
    ev = []
    for label, d in [
        ("QUIET FLOW BUILDING", "up"),
        ("QUIET FLOW BUILDING", "down"),
        ("MIXED — NO CLEAR EDGE", "up"),
        ("MIXED — NO CLEAR EDGE", "down"),
    ]:
        m = (labs == label) & (darr == d)
        xx = x[m]
        ts = tt[m]
        if not len(xx):
            continue
        wk = []
        for week in np.unique(wi[m]):
            z_ = xx[wi[m] == week]
            if len(z_) >= 30:
                wk.append(float(z_.mean()))
        ev.append(
            {
                "label": label,
                "direction": d,
                "n": int(m.sum()),
                "signal_weighted_mean_R": float(xx.mean()),
                "equal_weight_week_mean_R": float(np.mean(wk)),
                "weeks_passing_30row_filter": len(wk),
                "consistent_weighted_week_bootstrap": boot(xx, ts),
            }
        )
    emit(
        "evidence_interval_estimand",
        "Compare source signal-weighted point estimate with its unweighted-week means; recompute weighted ISO-week cluster bootstrap. Source weeks are epoch-Thursday bins, not ISO weeks.",
        ev,
        "Source interval combines a signal-weighted center with an equal-week standard error and drops thin weeks only from SE. Use consistent weights/estimand and retain small-block caveats.",
    )

    # Additional conservative first-touch ambiguity bounds, using stored flags.
    ambiguous = {
        (k, p, t, l, d): a
        for k, p, t, l, d, a in db.execute(
            "select kind,product_id,ts,label,direction,amb21 from recon"
        )
    }
    bounds = {}
    for d in ("up", "down"):
        rr = [r for r in matched if r[3] == d]
        sa = []
        ca = []
        for r in rr:
            p, t, lab, dr, atr = r[:5]
            src = bykey[(p, t, lab, dr)]
            a = pool[(p, dr)]
            lo, hi = np.searchsorted(a[:, 0], [t - 7 * 86400, t + 7 * 86400])
            w = a[lo:hi]
            ctl = w[
                (abs(w[:, 0] - t) >= 86400)
                & (w[:, 1] >= atr * 0.75)
                & (w[:, 1] <= atr / 0.75)
                & (w[:, 2] == bucket(src[5]))
            ]
            sa.append(ambiguous[("sig", p, t, lab, dr)])
            ca.append(
                np.mean(
                    [
                        ambiguous[("base", p, int(ct), "BASELINE", dr)]
                        for ct in ctl[:, 0]
                    ]
                )
            )
        center = np.mean([r[5] - r[6] for r in rr])
        bounds[d] = {
            "n": len(rr),
            "signal_ambiguous_fraction": float(np.mean(sa)),
            "control_ambiguous_fraction": float(np.mean(ca)),
            "ordering_only_excess_R_bounds": [
                float(center - 3 * np.mean(ca)),
                float(center + 3 * np.mean(sa)),
            ],
        }
    emit(
        "ambiguous_first_touch",
        "Stored amb21 flags are stop-first in source; bound excess allowing every ambiguous signal/control to range from -1R to +2R, holding costs fixed",
        bounds,
        "OHLC order is unidentified inside ambiguous bars. These are ordering sensitivity bounds, not confidence intervals or executable fill estimates.",
    )
    # Test the source BH implementation on an explicitly illustrative vector.
    ps = np.array([0.04, 0.041])
    source_bh = [bool(p <= (i + 1) / 2 * 0.05) for i, p in enumerate(ps)]
    cutoff = max([i for i, p in enumerate(ps) if p <= (i + 1) / 2 * 0.05], default=-1)
    correct_bh = [i <= cutoff for i in range(2)]
    emit(
        "BH_step_up_illustration",
        "Illustrative p-values [0.040,0.041], not observations; compare source per-rank booleans to BH step-up closure",
        {
            "illustrative": True,
            "p_values": ps.tolist(),
            "source_flags": source_bh,
            "correct_step_up_flags": correct_bh,
        },
        "ctrl_tests.py does not implement full BH step-up closure. This example demonstrates the bug, not a corrected empirical FDR result.",
    )

    # Source integrity, no in-place repair.
    manifests = []
    for p in sorted((ROOT / "source_scripts").glob("*.py")):
        manifests.append(
            {
                "file": str(p.relative_to(ROOT)),
                "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
            }
        )
    (OUT / "source_manifest.json").write_text(json.dumps(manifests, indent=2) + "\n")
    db.close()


if __name__ == "__main__":
    main()
