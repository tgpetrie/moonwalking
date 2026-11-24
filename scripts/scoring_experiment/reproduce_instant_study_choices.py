"""Synthetic design counterexamples; no market inputs, fitting or live imports."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import instant_targets as target


ANCHOR = 3_780_000


def rows(path):
    return [
        target.Sample(
            product_id="SYNTHETIC-USD",
            ts_ms=ANCHOR + seconds * 1000,
            bid=100 * math.exp(path(seconds)) * (1 - 0.0001),
            ask=100 * math.exp(path(seconds)) * (1 + 0.0001),
            btc_bid=50000 * (1 - 0.0001),
            btc_ask=50000 * (1 + 0.0001),
            quote_ts_ms=ANCHOR + seconds * 1000,
            btc_quote_ts_ms=ANCHOR + seconds * 1000,
            available_ts_ms=ANCHOR + seconds * 1000,
            trade_count=3,
            quote_volume_usd=30,
            coverage_verified=True,
            trade_count_at_bucket_start=0,
        )
        for seconds in range(-180, 1906, 5)
    ]


def baseline(anchor):
    # Explicit fixed synthetic inputs, not a claim that a recorder built them.
    return target.Baseline(
        sigma_1m=0.0015,
        beta=1.0,
        return_count=60,
        end_ts_ms=(anchor - 35000) // 60000 * 60000,
        available_ts_ms=anchor,
        beta_available_ts_ms=anchor,
        beta_fallback=False,
        pace_trade_median_30s=2,
        pace_quote_usd_median_30s=20,
        pace_window_count=120,
        pace_end_ts_ms=anchor - 30000,
        pace_available_ts_ms=anchor,
    )


def engine(path):
    return target.TargetEvaluator(rows(path), contract_path=target.V2_CONTRACT_PATH)


def grade(evaluator, offset=0, horizon=300):
    anchor = ANCHOR + offset * 1000
    return evaluator.evaluate(
        anchor, baseline(anchor), "up", horizon, anchor + horizon * 1000
    )


def covered(catalog, publication):
    return any(
        row["anchor_ts_ms"] - 180000 <= publication <= row["label_maturity_ts_ms"]
        for row in catalog
    )


def reproduce():
    def wick_path(seconds):
        if seconds < 0:
            return {-10: 0.04, -5: 0.0005}.get(seconds, 0.0)
        return 0.002 + 0.02 * min(seconds / 300, 1)

    wick_engine = engine(wick_path)
    wick_label = grade(wick_engine)
    timing = wick_engine.alert_timing(wick_label, ANCHOR)
    assert wick_label["verified_onset"] is True
    assert timing["timing"] == "late_after_activity_trigger"
    reference_to_forward_peak = wick_engine._residual(
        ANCHOR - 30000, wick_label["peak_ts_ms"], 1, 1
    )
    alternate_fraction = (
        wick_engine._residual(ANCHOR - 30000, ANCHOR, 1, 1) / reference_to_forward_peak
    )
    assert math.isclose(timing["pre_window_consumed_fraction"], 0.05)
    assert math.isclose(alternate_fraction, 0.002 / 0.022)
    assert ANCHOR <= wick_label["peak_ts_ms"]

    horizon_cases = []
    for horizon in (300, 900):
        impulse_start = horizon + 40
        future = engine(
            lambda seconds: 0.022 * min(max((seconds - impulse_start) / 30, 0), 1)
        )
        at_alert = grade(future, horizon=horizon)
        catalog = target.forward_event_catalog(
            grade(future, offset, horizon) for offset in range(0, 121, 5)
        )
        associated = covered(catalog, ANCHOR)
        assert at_alert["verified_forward"] is False
        assert associated and catalog[0]["anchor_ts_ms"] > ANCHOR
        horizon_cases.append(
            dict(
                horizon_seconds=horizon,
                impulse_starts_after_alert_seconds=impulse_start,
                pointwise_verified_forward=at_alert["verified_forward"],
                earliest_catalog_anchor_after_alert_seconds=(
                    catalog[0]["anchor_ts_ms"] - ANCHOR
                )
                / 1000,
                gemini_association_accepts_alert=associated,
                gemini_false_alert_rule=(
                    at_alert["verified_forward"] is False and not associated
                ),
            )
        )

    late = engine(
        lambda seconds: 0.002 + 0.02 * min(seconds / 300, 1) if seconds >= 0 else 0
    )
    late_catalog = target.forward_event_catalog(
        grade(late, t) for t in range(0, 301, 5)
    )
    late_alert = grade(late, 300)
    assert late_alert["verified_forward"] is False
    assert covered(late_catalog, ANCHOR + 300000)

    missing = engine(
        lambda seconds: 0.03 if seconds < 0 else 0.02 * min(seconds / 300, 1)
    )
    missing_label = grade(missing)
    missing_timing = missing.forward_alert_timing(missing_label, ANCHOR)
    assert missing_label["verified_forward"] is True
    assert missing_timing["pre_window_consumed_fraction"] is None
    assert "pre_window_consumed_fraction_reason" not in missing_timing
    base = baseline(ANCHOR)
    assert base.end_ts_ms <= ANCHOR - 35000
    assert base.pace_end_ts_ms == ANCHOR - 30000

    return dict(
        scope="synthetic_recommendation_checks_only_no_fitting_or_market_results",
        evaluator_sha256=wick_engine.implementation_sha256,
        contract_sha256=wick_engine.contract_sha256,
        earlier_wick=dict(
            verified_onset=wick_label["verified_onset"],
            existing_whole_window_timing=timing,
            proposed_forward_peak_from_pre_window_reference_fraction=alternate_fraction,
            existing_rule_matches_contract=True,
            changing_search_changes_the_metric=True,
        ),
        later_move_forgives_failed_pointwise_alert=horizon_cases,
        completed_move_forgives_failed_pointwise_alert=dict(
            publication_offset_seconds=300,
            pointwise_verified_forward=late_alert["verified_forward"],
            gemini_association_accepts_alert=True,
        ),
        cutoff_metadata=dict(
            sigma_end_ts_ms=base.end_ts_ms, pace_end_ts_ms=base.pace_end_ts_ms
        ),
        null_reason=dict(verified_forward=True, timing=missing_timing),
        fitting_allowed=False,
        operational_rates_enabled=False,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    rendered = json.dumps(reproduce(), indent=2, allow_nan=False) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered, encoding="utf-8", newline="\n")
    else:
        print(rendered, end="")


if __name__ == "__main__":
    main()
