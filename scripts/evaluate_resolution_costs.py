"""Same-decision 1h versus 15m path comparison and fixed-cohort cost grid.

Hourly features and next-hour entry remain fixed. This is descriptive research;
matched controls and the owner's shared archive are handled separately.
"""

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import gzip
import hashlib
import json
import math
from pathlib import Path
import random
from statistics import mean, median

from evaluate_trade_hypotheses import (
    HOUR,
    HORIZONS,
    build_decision,
    load_export,
    measure,
    opportunity_action,
    split_for,
    summarize,
)

QUARTER_HOUR = 900
VERSION = "hourly-entry-15m-path-costs-v1"


def digest(path):
    with open(path, "rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def week_key(ts):
    year, week, _ = datetime.fromtimestamp(ts, timezone.utc).isocalendar()
    return f"{year}-W{week:02d}"


def with_cost(row, round_trip_bps):
    cost = round_trip_bps / 100
    result = {**row, "opportunity": dict(row["opportunity"]), "outcomes": {}}
    f = result["opportunity"]
    if "atr" in f:
        f["net_reward_risk"] = (
            (f["reward_pct"] - cost) / (f["risk_pct"] + cost)
            if f["risk_pct"] > 0
            else None
        )
        result["action"], result["reason"] = opportunity_action(f)
        result["cost_in_atr"] = cost / f["atr_pct"]
    for horizon, outcome in row["outcomes"].items():
        adjusted = dict(outcome)
        if outcome.get("available"):
            adjusted["net_forward_return_pct"] = outcome["return_pct"] - cost
            adjusted["net_forward_return_atr"] = (
                adjusted["net_forward_return_pct"] / f["atr_pct"]
            )
        result["outcomes"][horizon] = adjusted
    return result


def cost_summary(rows, horizon):
    stats = summarize(rows, horizon, bootstrap=False)
    measured = [(r, r["outcomes"].get(str(horizon), {})) for r in rows]
    measured = [(r, o) for r, o in measured if o.get("available")]
    weeks = defaultdict(list)
    for row, outcome in measured:
        weeks[week_key(row["decision_ts"])].append(outcome["net_forward_return_pct"])
    week_means = [mean(v) for _, v in sorted(weeks.items())]
    interval = None
    # An exploratory cluster bootstrap. Never turn 3 test weeks into a z-score.
    if len(week_means) >= 12:
        rng = random.Random(1729)
        draws = sorted(
            mean(rng.choices(week_means, k=len(week_means))) for _ in range(500)
        )
        interval = [draws[12], draws[487]]
    stats.update(
        {
            "calendar_weeks": len(weeks),
            "mean_weekly_mean_net_forward_return_pct": (
                mean(week_means) if week_means else None
            ),
            "weekly_cluster_bootstrap_95_interval": interval,
            "fraction_positive_after_assumed_cost": (
                mean(o["net_forward_return_pct"] > 0 for _, o in measured)
                if measured
                else None
            ),
            "mean_net_forward_return_atr": (
                mean(o["net_forward_return_atr"] for _, o in measured)
                if measured
                else None
            ),
            "median_cost_in_atr": (
                median(r["cost_in_atr"] for r, _ in measured) if measured else None
            ),
        }
    )
    return stats


def compare_resolution(rows):
    comparisons = {}
    for horizon in HORIZONS:
        paired = []
        coarse_status, fine_status, resolved = Counter(), Counter(), Counter()
        transitions = Counter()
        geometry_coarse, geometry_fine, geometry_resolved = (
            Counter(),
            Counter(),
            Counter(),
        )
        deltas = []
        mfe_deltas, mae_deltas = [], []
        for row in rows:
            hourly = row.get("hourly_outcomes", {}).get(str(horizon), {})
            fine = row["outcomes"].get(str(horizon), {})
            if hourly.get("available") and fine.get("available"):
                paired.append(row)
                a, b = (
                    hourly["atr_first_touch"]["status"],
                    fine["atr_first_touch"]["status"],
                )
                coarse_status[a] += 1
                fine_status[b] += 1
                transitions[f"{a}->{b}"] += 1
                if a == "ambiguous":
                    resolved[b] += 1
                deltas.append(abs(hourly["return_pct"] - fine["return_pct"]))
                mfe_deltas.append(abs(hourly["mfe_atr"] - fine["mfe_atr"]))
                mae_deltas.append(abs(hourly["mae_atr"] - fine["mae_atr"]))
                if (
                    hourly["geometry_first_touch"] is not None
                    and fine["geometry_first_touch"] is not None
                ):
                    ga = hourly["geometry_first_touch"]["status"]
                    gb = fine["geometry_first_touch"]["status"]
                    geometry_coarse[ga] += 1
                    geometry_fine[gb] += 1
                    if ga == "ambiguous":
                        geometry_resolved[gb] += 1
        comparisons[str(horizon)] = {
            "paired_decisions": len(paired),
            "hourly_atr_first_touch_counts": dict(coarse_status),
            "fine_atr_first_touch_counts": dict(fine_status),
            "hourly_ambiguous_to_fine_status": dict(resolved),
            "atr_status_transitions": dict(transitions),
            "geometry_paired_decisions": sum(geometry_coarse.values()),
            "hourly_geometry_first_touch_counts": dict(geometry_coarse),
            "fine_geometry_first_touch_counts": dict(geometry_fine),
            "hourly_geometry_ambiguous_to_fine_status": dict(geometry_resolved),
            "max_abs_close_return_difference_pct": max(deltas) if deltas else None,
            "max_abs_mfe_difference_atr": max(mfe_deltas) if mfe_deltas else None,
            "max_abs_mae_difference_atr": max(mae_deltas) if mae_deltas else None,
        }
    return comparisons


def run(hourly_input, fine_input, output_dir, costs, lookback=49):
    if not costs or any(not math.isfinite(v) or v < 0 for v in costs):
        raise ValueError("Finite nonnegative round-trip cost scenarios required")
    if lookback < 15:
        raise ValueError("At least 15 completed hourly candles required")
    out = Path(output_dir)
    if out.exists():
        raise FileExistsError("Choose a new output directory")
    signals, hourly, hourly_audit, hourly_manifest = load_export(hourly_input)
    fine_signals, fine, fine_audit, fine_manifest = load_export(
        fine_input, candle_granularity_seconds=QUARTER_HOUR
    )
    if signals != fine_signals or not signals:
        raise ValueError("Both exports must contain identical hourly decision cohorts")
    if hourly_manifest["captured_ts"] != fine_manifest["captured_ts"]:
        raise ValueError("Both exports must use the same source capture cutoff")
    start, end = min(t for _, t in signals), max(t for _, t in signals)
    rows = []
    mismatched_entry = 0
    for (product, ts), signal in sorted(
        signals.items(), key=lambda pair: (pair[0][1], pair[0][0])
    ):
        row = build_decision(
            signal, ts, hourly.get(product, {}), hourly.get("BTC-USD", {}), lookback, 0
        )
        row["split"] = split_for(ts, start, end)
        row["hourly_outcomes"], row["outcomes"] = row["outcomes"], {}
        f = row["opportunity"]
        if "atr" in f:
            fine_entry = fine.get(product, {}).get(ts)
            if fine_entry is not None and not math.isclose(
                fine_entry.open, f["entry"], rel_tol=1e-8, abs_tol=1e-12
            ):
                mismatched_entry += 1
                row["outcomes"] = {
                    str(h): {
                        "available": False,
                        "reason": "native_entry_opens_disagree",
                    }
                    for h in HORIZONS
                }
            else:
                direction = {"up": 1, "down": -1}[signal["direction"]]
                for h in HORIZONS:
                    row["outcomes"][str(h)] = measure(
                        fine.get(product, {}),
                        ts,
                        f["entry"],
                        direction,
                        f["atr"],
                        f["invalid"],
                        f["target"],
                        h,
                        0,
                        granularity_seconds=QUARTER_HOUR,
                    )
        rows.append(row)
    # Every scenario uses the same decision cohort. Action-specific cohorts are
    # separately labelled because the geometry gates depend on assumed costs.
    report = {
        "methodology": VERSION,
        "outcome_validated": False,
        "entry_policy": "latest_signal_per_product_hour_then_next_hour_open",
        "feature_granularity_seconds": HOUR,
        "path_granularity_seconds": QUARTER_HOUR,
        "lookback": lookback,
        "split": {
            "start": start,
            "end": end,
            "train_end": start + int((end - start) * 0.6),
            "validation_end": start + int((end - start) * 0.8),
            "purge_seconds": max(HORIZONS),
        },
        "matched_controls": False,
        "hourly_input_sha256": digest(hourly_input),
        "fine_input_sha256": digest(fine_input),
        "hourly_audit": hourly_audit,
        "fine_audit": fine_audit,
        "entry_open_disagreements": mismatched_entry,
        "resolution_comparison": compare_resolution(rows),
        "cost_scenarios": {},
    }
    for cost in sorted(set(costs)):
        adjusted = [with_cost(row, cost) for row in rows]
        scenario = {
            "round_trip_bps": cost,
            "assumed_total_cost_not_account_fee": True,
            "splits": {},
        }
        for split in ("train", "validation", "test", "purged"):
            subset = [r for r in adjusted if r["split"] == split]
            scenario["splits"][split] = {
                "fixed_cohort_horizons": {
                    str(h): cost_summary(subset, h) for h in HORIZONS
                },
                "cost_dependent_action_counts": dict(
                    Counter(r["action"] for r in subset)
                ),
                "cost_dependent_actions_4h": {
                    action: cost_summary(
                        [r for r in subset if r["action"] == action], 4 * HOUR
                    )
                    for action in sorted({r["action"] for r in subset})
                },
            }
        report["cost_scenarios"][str(cost)] = scenario
    out.mkdir(parents=True)
    with gzip.open(out / "decisions-gross.jsonl.gz", "xt", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, allow_nan=False, separators=(",", ":")) + "\n")
    (out / "report.json").write_text(
        json.dumps(report, allow_nan=False, indent=2) + "\n", encoding="utf-8"
    )
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hourly-input", required=True, type=Path)
    parser.add_argument("--fine-input", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--round-trip-bps", nargs="+", type=float, required=True)
    parser.add_argument("--lookback", type=int, default=49)
    args = parser.parse_args()
    result = run(
        args.hourly_input,
        args.fine_input,
        args.output_dir,
        args.round_trip_bps,
        args.lookback,
    )
    print(
        json.dumps(
            {
                "decisions": result["hourly_audit"]["product_hour_decisions"],
                "report": str((args.output_dir / "report.json").resolve()),
            }
        )
    )
