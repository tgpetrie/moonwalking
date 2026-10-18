"""Offline, hourly-entry hypotheses. Never imported by the production app.

Input is the market-only JSONL export from export_trade_research.py. Entry at
the NEXT hourly open is an explicit research policy, not a reconstruction of
execution at a live signal's timestamp. No thresholds are promoted to runtime.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from dataclasses import dataclass
import gzip
import hashlib
import itertools
import json
import math
from pathlib import Path
import random
from statistics import mean, median

HOUR = 3600
HORIZONS = (900, HOUR, 4 * HOUR, 12 * HOUR, 24 * HOUR)
VERSION = "hourly-hypotheses-research-v1"


def number(value):
    if isinstance(value, bool):
        return None
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (TypeError, ValueError):
        return None


@dataclass(frozen=True)
class Candle:
    ts: int
    open: float
    high: float
    low: float
    close: float
    volume: float


def candle_from_row(row, *, granularity_seconds=HOUR):
    values = [
        number(row.get(k)) for k in ("open", "high", "low", "close", "base_volume")
    ]
    values.insert(0, number(row.get("candle_ts", row.get("hour_ts"))))
    # Production volume_hour extrema are minute-close samples, not OHLC.
    # Coverage alone cannot turn them into exchange candle observations.
    if (
        any(v is None for v in values)
        or row.get("source") != "coinbase_exchange_ohlcv"
        or row.get("granularity_seconds", HOUR) != granularity_seconds
        or granularity_seconds not in (900, HOUR)
    ):
        return None
    ts, open_, high, low, close, volume = values
    if (
        ts % granularity_seconds
        or not (0 < low <= min(open_, close) <= max(open_, close) <= high)
        or volume < 0
    ):
        return None
    return Candle(int(ts), open_, high, low, close, volume)


def load_export(path, *, candle_granularity_seconds=HOUR):
    """Collapse transitions deterministically, before looking at future prices."""
    signals, candles = {}, defaultdict(dict)
    audit = Counter()
    manifest = None
    expected_counts = None
    invalid_candles = set()
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        for line in handle:
            row = json.loads(line)
            kind = row.pop("kind")
            audit[kind] += 1
            if kind == "manifest":
                manifest = row
            elif kind == "counts":
                expected_counts = row
            elif kind == "signal":
                ts = number(row.get("started_ts"))
                if (
                    ts is None
                    or ts != int(ts)
                    or ts < 0
                    or not row.get("product_id")
                    or not row.get("signal_id")
                ):
                    audit["invalid_signal"] += 1
                    continue
                # Always wait for the next open, including an exactly aligned signal.
                entry_ts = (int(ts) // HOUR + 1) * HOUR
                key = (row["product_id"], entry_ts)
                existing = signals.get(key)
                if existing is None or (ts, row["signal_id"]) > (
                    existing["started_ts"],
                    existing["signal_id"],
                ):
                    signals[key] = row
            elif kind == "candle":
                product = row["product_id"]
                bar = candle_from_row(
                    row, granularity_seconds=candle_granularity_seconds
                )
                candle_ts = row.get("candle_ts", row.get("hour_ts"))
                key = (product, candle_ts)
                if bar is None or key in invalid_candles or bar.ts in candles[product]:
                    audit["invalid_or_duplicate_candle"] += 1
                    invalid_candles.add(key)
                    candles[product].pop(candle_ts, None)
                    continue
                candles[product][bar.ts] = bar
    if (
        not manifest
        or not expected_counts
        or any(expected_counts.get(k) != audit[k] for k in ("signal", "candle"))
    ):
        raise ValueError("Incomplete export or count mismatch")
    if manifest.get("schema_version") != 1:
        raise ValueError("Unsupported export schema")
    if manifest.get("candle_granularity_seconds", HOUR) != candle_granularity_seconds:
        raise ValueError("Candle granularity does not match requested analysis")
    audit["product_hour_decisions"] = len(signals)
    audit["signal_products"] = len({p for p, _ in signals})
    audit["valid_candles"] = sum(map(len, candles.values()))
    return signals, candles, dict(audit), manifest


def consecutive(bars, start, count, *, granularity_seconds=HOUR):
    result = [bars.get(start + i * granularity_seconds) for i in range(count)]
    return result if all(bar is not None for bar in result) else None


def geometry(history, entry, direction, cost_pct):
    ranges = [
        max(b.high - b.low, abs(b.high - a.close), abs(b.low - a.close))
        for a, b in zip(history, history[1:])
    ]
    atr = mean(ranges[-14:])
    if atr <= 0:
        return None
    support, resistance = min(b.low for b in history), max(b.high for b in history)
    stop = support - 0.2 * atr if direction == 1 else resistance + 0.2 * atr
    target = resistance if direction == 1 else support
    risk = direction * (entry - stop)
    reward = direction * (target - entry)
    baseline_volume = median(b.volume for b in history[:-1])
    volume_ratio = history[-1].volume / baseline_volume if baseline_volume > 0 else None
    risk_pct, reward_pct = risk / entry * 100, reward / entry * 100
    rr = (reward_pct - cost_pct) / (risk_pct + cost_pct) if risk > 0 else None
    extension = (
        (entry - support) / atr if direction == 1 else (resistance - entry) / atr
    )
    structure = direction * (history[-1].close - history[-2].close) > 0
    groups = (["price_structure"] if structure else []) + (
        ["volume"] if volume_ratio is not None and volume_ratio >= 1.5 else []
    )
    # RSI/MACD/stochastic would share a price family, never three confirmations.
    return {
        "entry": entry,
        "invalid": stop,
        "target": target,
        "atr": atr,
        "range_position_pct": (
            (entry - support) / (resistance - support) * 100
            if resistance > support
            else None
        ),
        "volume_ratio": volume_ratio,
        "extension_atr": extension,
        "risk_pct": risk_pct,
        "reward_pct": reward_pct,
        "net_reward_risk": rr,
        "structure_confirms": structure,
        "confirmation_families": groups,
        "atr_pct": atr / entry * 100,
    }


def first_touch(bars, entry, direction, stop, target):
    """Preserve OHLC ordering ambiguity; an opening gap has known precedence."""
    for bar in bars:
        if direction * (bar.open - target) >= 0:
            return {"status": "target_first", "bar_ts": bar.ts, "gap": True}
        if direction * (bar.open - stop) <= 0:
            return {"status": "stop_first", "bar_ts": bar.ts, "gap": True}
        target_hit = bar.high >= target if direction == 1 else bar.low <= target
        stop_hit = bar.low <= stop if direction == 1 else bar.high >= stop
        if target_hit or stop_hit:
            return {
                "status": (
                    "ambiguous"
                    if target_hit and stop_hit
                    else "target_first" if target_hit else "stop_first"
                ),
                "bar_ts": bar.ts,
                "gap": False,
            }
    return {"status": "neither", "bar_ts": None, "gap": False}


def measure(
    bars,
    ts,
    entry,
    direction,
    atr,
    stop,
    target,
    horizon,
    cost_pct,
    *,
    granularity_seconds=HOUR,
):
    if granularity_seconds not in (900, HOUR):
        raise ValueError("Only native 15m and hourly paths are supported")
    if horizon <= 0:
        raise ValueError("A positive forward horizon is required")
    if ts % granularity_seconds:
        return {"available": False, "reason": "entry_not_aligned_to_path_bar"}
    if horizon % granularity_seconds:
        return {"available": False, "reason": "hourly_candles_cannot_measure_15m"}
    future = consecutive(
        bars,
        ts,
        horizon // granularity_seconds,
        granularity_seconds=granularity_seconds,
    )
    if future is None:
        return {"available": False, "reason": "missing_or_incomplete_future_candle"}
    favorable = (
        max(
            [entry] + [b.high if direction == 1 else -b.low + 2 * entry for b in future]
        )
        - entry
    )
    adverse = (
        min(
            [entry] + [b.low if direction == 1 else -b.high + 2 * entry for b in future]
        )
        - entry
    )
    gross = direction * (future[-1].close / entry - 1) * 100
    valid_geometry = (
        direction * (entry - stop) > 0
        and direction * (target - entry) > 0
        and stop > 0
        and target > 0
    )
    return {
        "available": True,
        "return_pct": gross,
        "net_forward_return_pct": gross - cost_pct,
        "mfe_atr": favorable / atr,
        "mae_atr": adverse / atr,
        "atr_first_touch": first_touch(
            future, entry, direction, entry - direction * atr, entry + direction * atr
        ),
        "geometry_first_touch": (
            first_touch(future, entry, direction, stop, target)
            if valid_geometry
            else None
        ),
    }


def split_for(ts, start, end):
    """Global chronological 60/20/20 split with a 24h forward-label purge."""
    train_end, validation_end = start + int((end - start) * 0.6), start + int(
        (end - start) * 0.8
    )
    if ts < train_end:
        return "train" if ts + max(HORIZONS) < train_end else "purged"
    if ts < validation_end:
        return "validation" if ts + max(HORIZONS) < validation_end else "purged"
    return "test"


def opportunity_action(features):
    """Unvalidated research gates shared by replay and cost sensitivity."""
    if (
        features["risk_pct"] <= 0
        or features["invalid"] <= 0
        or features["net_reward_risk"] is None
        or features["net_reward_risk"] < 1
    ):
        return "NO_TRADE", "insufficient_net_reward_before_structure"
    if features["extension_atr"] > 2.4:
        return "WAIT_FOR_PULLBACK", "extension_exceeds_research_cap"
    if len(features["confirmation_families"]) < 2:
        return "WAIT", "independent_confirmation_missing"
    return "RESEARCH_CANDIDATE", "unvalidated_geometry_and_confirmation_pass"


def build_decision(signal, ts, bars, btc_bars, lookback, cost_pct):
    direction = {"up": 1, "down": -1}.get(signal.get("direction"))
    result = {
        "signal_id": signal["signal_id"],
        "event_id": signal["event_id"],
        "product_id": signal["product_id"],
        "signal_ts": signal["started_ts"],
        "decision_ts": ts,
        "setup": {
            "state": signal["primary_state"],
            "read_label": signal["read_label"],
            "direction": signal["direction"],
        },
        "confidence": {
            "score": signal.get("confidence"),
            "source": "legacy_event_evidence",
            "calibrated_probability": False,
        },
        "opportunity": {"score": None, "validated": False},
        "risk": {"liquidity": None},
        "action": "NO_TRADE",
        "reason": None,
        "outcomes": {},
        "lookback": lookback,
    }
    if direction is None:
        result["reason"] = "no_directional_hypothesis"
        return result
    history = consecutive(bars, ts - lookback * HOUR, lookback)
    entry_bar = bars.get(ts)
    if history is None or entry_bar is None:
        result["reason"] = "insufficient_complete_contiguous_candles"
        return result
    features = geometry(history, entry_bar.open, direction, cost_pct)
    if features is None:
        result["reason"] = "zero_atr"
        return result
    result["opportunity"].update(features)
    result["risk"]["atr_pct"] = features["atr_pct"]
    context = {}
    for name, n in (("btc_1h_pct", 1), ("btc_4h_pct", 4)):
        btc = consecutive(btc_bars, ts - n * HOUR, n)
        context[name] = (btc[-1].close / btc[0].open - 1) * 100 if btc else None
    result["context"] = context
    result["action"], result["reason"] = opportunity_action(features)
    for horizon in HORIZONS:
        result["outcomes"][str(horizon)] = measure(
            bars,
            ts,
            entry_bar.open,
            direction,
            features["atr"],
            features["invalid"],
            features["target"],
            horizon,
            cost_pct,
        )
    return result


def summarize(rows, horizon, *, bootstrap=True):
    measured = [(r, r["outcomes"].get(str(horizon), {})) for r in rows]
    measured = [(r, o) for r, o in measured if o.get("available")]
    counts = Counter(o["atr_first_touch"]["status"] for _, o in measured)
    geometry_counts = Counter(
        o["geometry_first_touch"]["status"]
        for _, o in measured
        if o.get("geometry_first_touch") is not None
    )
    daily = defaultdict(list)
    for row, outcome in measured:
        daily[row["decision_ts"] // 86400].append(outcome["net_forward_return_pct"])
    daily_means = [mean(v) for _, v in sorted(daily.items())]
    interval = None
    if bootstrap and len(daily_means) >= 20:
        rng = random.Random(1729)
        draws = sorted(
            mean(rng.choices(daily_means, k=len(daily_means))) for _ in range(500)
        )
        interval = [draws[12], draws[487]]
    n = len(measured)
    return {
        "decisions": len(rows),
        "measured": n,
        "distinct_events": len({r["event_id"] for r, _ in measured}),
        "utc_days": len(daily),
        "median_mfe_atr": median(o["mfe_atr"] for _, o in measured) if n else None,
        "median_mae_atr": median(o["mae_atr"] for _, o in measured) if n else None,
        "mean_net_forward_return_pct": (
            mean(o["net_forward_return_pct"] for _, o in measured) if n else None
        ),
        "mean_daily_net_forward_return_pct": mean(daily_means) if daily_means else None,
        "daily_block_bootstrap_95_interval": interval,
        "atr_first_touch_counts": dict(counts),
        "geometry_first_touch_counts": dict(geometry_counts),
        "target_first_fraction_bounds": (
            [
                counts["target_first"] / n,
                (counts["target_first"] + counts["ambiguous"]) / n,
            ]
            if n
            else None
        ),
    }


def threshold_grid(rows):
    # Prespecified comparisons, no winner chosen from validation/test results.
    summaries = []
    for conf, volume, rr, extension in itertools.product(
        (0, 65, 72, 85), (0, 1.25, 1.5, 1.8), (0, 1, 2), (None, 2.4)
    ):
        selected = []
        for row in rows:
            f = row["opportunity"]
            score = number(row["confidence"]["score"])
            if score is None or score < conf or "atr" not in f:
                continue
            if rr and (
                f["net_reward_risk"] is None
                or f["net_reward_risk"] < rr
                or f["invalid"] <= 0
            ):
                continue
            if volume and (f["volume_ratio"] is None or f["volume_ratio"] < volume):
                continue
            if extension is not None and f["extension_atr"] > extension:
                continue
            selected.append(row)
        # Bootstrap intervals belong to baseline stratifications; grid results
        # are descriptive multiple comparisons, never predictive probabilities.
        stats = summarize(selected, 4 * HOUR, bootstrap=False)
        summaries.append(
            {
                "min_confidence": conf,
                "min_volume_ratio": volume,
                "min_net_rr": rr,
                "max_extension_atr": extension,
                **stats,
            }
        )
    return summaries


def run(input_path, output_dir, lookbacks, fee_bps, slippage_bps):
    if not lookbacks or any(n < 15 for n in lookbacks):
        raise ValueError("At least 15 completed hourly candles required")
    if any(not math.isfinite(v) or v < 0 for v in (fee_bps, slippage_bps)):
        raise ValueError("Nonnegative finite per-side fees and slippage required")
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    # Refuse overwrite before expensive loading or analysis.
    report_path, decisions_path = (
        output_dir / "report.json",
        output_dir / "decisions.jsonl.gz",
    )
    if report_path.exists() or decisions_path.exists():
        raise FileExistsError("Choose a new output directory")
    signals, candles, audit, manifest = load_export(input_path)
    times = [ts for _, ts in signals]
    if not times:
        raise ValueError("No valid decisions")
    start, end = min(times), max(times)
    cost_pct = 2 * (fee_bps + slippage_bps) / 100
    with open(input_path, "rb") as source:
        input_sha256 = hashlib.file_digest(source, "sha256").hexdigest()
    report = {
        "methodology": VERSION,
        "entry_policy": "latest_signal_per_product_hour_then_next_hour_open",
        "outcome_validated": False,
        "input_sha256": input_sha256,
        "export_manifest": manifest,
        "audit": audit,
        "costs": {
            "fee_bps_per_side": fee_bps,
            "slippage_bps_per_side": slippage_bps,
            "round_trip_pct": cost_pct,
        },
        "split": {
            "start": start,
            "end": end,
            "train_end": start + int((end - start) * 0.6),
            "validation_end": start + int((end - start) * 0.8),
            "purge_seconds": max(HORIZONS),
        },
        "lookbacks": {},
    }
    with gzip.open(decisions_path, "xt", encoding="utf-8") as ledger:
        for lookback in sorted(set(lookbacks)):
            rows = []
            for (product, ts), signal in sorted(
                signals.items(), key=lambda pair: (pair[0][1], pair[0][0])
            ):
                row = build_decision(
                    signal,
                    ts,
                    candles.get(product, {}),
                    candles.get("BTC-USD", {}),
                    lookback,
                    cost_pct,
                )
                row["split"] = split_for(ts, start, end)
                ledger.write(
                    json.dumps(row, allow_nan=False, separators=(",", ":")) + "\n"
                )
                rows.append(row)
            result = {
                "actions": dict(Counter(r["action"] for r in rows)),
                "reasons": dict(Counter(r["reason"] for r in rows)),
                "splits": {},
            }
            for split in ("train", "validation", "test", "purged"):
                subset = [r for r in rows if r["split"] == split]
                result["splits"][split] = {
                    "horizons": {str(h): summarize(subset, h) for h in HORIZONS},
                    "thresholds_4h": (
                        threshold_grid(subset) if split != "purged" else []
                    ),
                }
            # Keep coin, setup, context and action descriptive strata separate;
            # tiny cells never become published probability or threshold rules.
            for dimension in (
                "product_id",
                "read_label",
                "btc_alignment",
                "action",
                "direction",
                "atr_regime",
                "range_zone",
                "confirmation_families",
            ):
                groups = defaultdict(list)
                for row in rows:
                    if row["split"] != "test":
                        continue
                    if dimension == "read_label":
                        key = row["setup"]["read_label"]
                    elif dimension == "direction":
                        key = row["setup"]["direction"]
                    elif dimension == "atr_regime":
                        value = row["opportunity"].get("atr_pct")
                        key = (
                            "unavailable"
                            if value is None
                            else (
                                "below_0.5pct"
                                if value < 0.5
                                else (
                                    "0.5_to_1.5pct"
                                    if value < 1.5
                                    else "at_least_1.5pct"
                                )
                            )
                        )
                    elif dimension == "range_zone":
                        value = row["opportunity"].get("range_position_pct")
                        key = (
                            "unavailable"
                            if value is None
                            else (
                                "below_support"
                                if value < 0
                                else (
                                    "bottom_15pct"
                                    if value <= 15
                                    else (
                                        "middle_70pct"
                                        if value < 85
                                        else (
                                            "top_15pct"
                                            if value <= 100
                                            else "above_resistance"
                                        )
                                    )
                                )
                            )
                        )
                    elif dimension == "confirmation_families":
                        key = (
                            "+".join(
                                row["opportunity"].get("confirmation_families", [])
                            )
                            or "none"
                        )
                    elif dimension == "btc_alignment":
                        value = row.get("context", {}).get("btc_4h_pct")
                        sign = {"up": 1, "down": -1}.get(row["setup"]["direction"])
                        key = (
                            "unavailable"
                            if value is None or sign is None
                            else "aligned" if value * sign > 0 else "opposing_or_flat"
                        )
                    else:
                        key = row[dimension]
                    groups[key].append(row)
                result["test_by_" + dimension] = {
                    k: summarize(v, 4 * HOUR) for k, v in sorted(groups.items())
                }
            report["lookbacks"][str(lookback)] = result
    report_path.write_text(
        json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--lookbacks", nargs="+", type=int, default=[49])
    parser.add_argument(
        "--fee-bps",
        required=True,
        type=float,
        help="Assumed per-side fee, not fetched from an account",
    )
    parser.add_argument(
        "--slippage-bps", required=True, type=float, help="Assumed per-side slippage"
    )
    args = parser.parse_args()
    report = run(
        args.input, args.output_dir, args.lookbacks, args.fee_bps, args.slippage_bps
    )
    print(
        json.dumps(
            {
                "audit": report["audit"],
                "report": str((args.output_dir / "report.json").resolve()),
            }
        )
    )
