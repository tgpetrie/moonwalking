"""Hand-computable synthetic paths; no historical or prospective fitting."""

from dataclasses import replace
import importlib.util
import math
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "instant_targets", ROOT / "scripts/scoring_experiment/instant_targets.py"
)
target = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = target
spec.loader.exec_module(target)
ANCHOR = 3_780_000


def baseline(**kwargs):
    return replace(
        target.Baseline(
            sigma_1m=0.0015,
            beta=1.0,
            return_count=60,
            end_ts_ms=ANCHOR,
            available_ts_ms=ANCHOR,
            beta_available_ts_ms=ANCHOR,
            beta_fallback=False,
            pace_trade_median_30s=2,
            pace_quote_usd_median_30s=20,
            pace_window_count=120,
            pace_end_ts_ms=ANCHOR - 30_000,
            pace_available_ts_ms=ANCHOR,
        ),
        **kwargs,
    )


def samples(direction="up", residual=None, btc=None):
    sign = 1 if direction == "up" else -1
    rows = []
    for ts in range(ANCHOR - 180_000, ANCHOR + 905_000, 5000):
        elapsed = (ts - ANCHOR) / 1000
        move = (
            residual(elapsed)
            if residual
            else 0.002 + 0.02 * min(max(elapsed / 300, 0), 1) if elapsed >= 0 else 0
        )
        market = btc(elapsed) if btc else 0
        mid, btc_mid = 100 * math.exp(sign * move + market), 50000 * math.exp(market)
        rows.append(
            target.Sample(
                product_id="TEST-USD",
                ts_ms=ts,
                bid=mid * (1 - 0.0001),
                ask=mid * (1 + 0.0001),
                btc_bid=btc_mid * (1 - 0.0001),
                btc_ask=btc_mid * (1 + 0.0001),
                quote_ts_ms=ts,
                btc_quote_ts_ms=ts,
                available_ts_ms=ts,
                trade_count=1,
                quote_volume_usd=10,
                coverage_verified=True,
                trade_count_at_bucket_start=0,
            )
        )
    return rows


def grade(rows=None, direction="up", horizon=300, base=None, asof=None):
    engine = target.TargetEvaluator(rows if rows is not None else samples(direction))
    result = engine.evaluate(
        ANCHOR,
        base or baseline(),
        direction,
        horizon,
        asof if asof is not None else ANCHOR + horizon * 1000,
    )
    return engine, result


@pytest.mark.parametrize("direction", ["up", "down"])
@pytest.mark.parametrize("horizon", [300, 900])
def test_sustained_move_is_symmetric_and_peak_ties_choose_first(direction, horizon):
    _, result = grade(direction=direction, horizon=horizon)
    assert result["status"] == "ready"
    assert result["verified_forward"] and result["verified_onset"]
    assert result["terminal_residual_log"] == pytest.approx(0.02)
    assert result["retention"] == pytest.approx(1)
    assert result["peak_ts_ms"] == ANCHOR + 300_000
    assert result["breakout_ts_ms"] == ANCHOR + 35_000
    assert result["forward_trade_count"] == horizon / 5


def test_market_move_is_not_an_idiosyncratic_impulse():
    _, result = grade(
        samples(residual=lambda t: 0, btc=lambda t: 0.04 * max(t, 0) / 300)
    )
    assert result["terminal_residual_log"] == pytest.approx(0, abs=1e-12)
    assert result["verified_forward"] is False


@pytest.mark.parametrize("direction", ["up", "down"])
def test_opposite_direction_is_never_verified_by_absolute_magnitude(direction):
    opposite = "down" if direction == "up" else "up"
    _, result = grade(samples(opposite), direction=direction)
    assert result["terminal_residual_log"] < 0
    assert result["verified_forward"] is False


def test_large_wick_with_good_terminal_magnitude_fails_retention():
    _, result = grade(
        samples(
            residual=lambda t: (
                0
                if t < 0
                else 0.002 + (0.05 if 0 < t < 300 else 0.02 if t >= 300 else 0)
            )
        )
    )
    assert result["terminal_residual_log"] > result["required_terminal_log"]
    assert result["retention"] == pytest.approx(0.4)
    assert result["verified_forward"] is False


def test_later_retrace_rejects_onset_but_preserves_forward_impulse():
    rows = samples()
    rows = [
        replace(row, bid=99, ask=99.02) if row.ts_ms == ANCHOR + 50_000 else row
        for row in rows
    ]
    _, result = grade(rows)
    assert result["verified_forward"] is True
    assert result["onset_candidate"] is True
    assert result["no_retrace"] is False
    assert result["verified_onset"] is False
    assert result["adverse_residual_log"] < 0


@pytest.mark.parametrize(
    "change,reason",
    [
        ({"coverage_verified": False}, "unverified_coverage"),
        ({"price_source": "last_trade_fallback"}, "price_fallback"),
        ({"btc_price_source": "last_trade_fallback"}, "price_fallback"),
        ({"quote_ts_ms": ANCHOR - 20_000}, "stale_or_future_quote"),
        ({"quote_ts_ms": ANCHOR + 10_001}, "stale_or_future_quote"),
        ({"bid": 110, "ask": 100}, "invalid_quote"),
        ({"ask": None}, "invalid_quote"),
        ({"btc_bid": float("nan")}, "invalid_quote"),
        ({"trade_count": -1}, "invalid_trade_count"),
        ({"quote_volume_usd": float("nan")}, "invalid_volume"),
        ({"available_ts_ms": ANCHOR + 10_001}, "future_receipt"),
    ],
)
def test_unknown_data_never_becomes_a_negative_label(change, reason):
    rows = [
        replace(row, **change) if row.ts_ms == ANCHOR + 10_000 else row
        for row in samples()
    ]
    _, result = grade(rows)
    assert result["status"] == "unavailable"
    assert result["reason"] == reason
    assert result["verified_forward"] is None
    assert result["verified_onset"] is None


def test_missing_grid_point_and_nonexact_endpoint_are_unknown():
    for missing in (ANCHOR + 5000, ANCHOR + 300_000):
        _, result = grade([row for row in samples() if row.ts_ms != missing])
        assert result["reason"] == "missing_grid_point"
        assert result["verified_forward"] is None


def test_label_waits_for_full_horizon_instead_of_using_partial_success():
    _, result = grade(asof=ANCHOR + 299_999)
    assert result["status"] == "pending"
    assert result["verified_forward"] is None


@pytest.mark.parametrize(
    "change,reason",
    [
        ({"available_ts_ms": ANCHOR + 1}, "future_baseline"),
        ({"beta_available_ts_ms": ANCHOR + 1}, "future_baseline"),
        ({"end_ts_ms": ANCHOR - 60_000}, "baseline_window_misaligned"),
        ({"return_count": 59}, "baseline_warming"),
        ({"sigma_1m": float("nan")}, "invalid_baseline"),
    ],
)
def test_baselines_are_causal_complete_and_current(change, reason):
    _, result = grade(base=baseline(**change))
    assert result["status"] == "unavailable"
    assert result["reason"] == reason


def test_sigma_floor_and_beta_fallback_are_visible():
    _, result = grade(base=baseline(sigma_1m=0, beta_fallback=True))
    assert result["sigma_1m"] == 0.0015
    assert result["sigma_floor_applied"] is True
    assert result["beta_fallback"] is True


def test_forward_trade_quantum_excludes_anchor_bucket():
    rows = [
        replace(row, trade_count=100 if row.ts_ms == ANCHOR else 0) for row in samples()
    ]
    _, result = grade(rows)
    assert result["forward_trade_count"] == 0
    assert result["verified_forward"] is False


def test_exact_pace_threshold_and_single_print_do_not_create_onset():
    _, result = grade(
        base=baseline(pace_trade_median_30s=3, pace_quote_usd_median_30s=30)
    )
    assert result["pace_multiple"] == 2
    assert result["onset_candidate"] is False
    rows = [
        replace(row, trade_count=0) if ANCHOR - 30_000 < row.ts_ms < ANCHOR else row
        for row in samples()
    ]
    _, result = grade(rows)
    assert result["recent_trade_count"] == 1
    assert result["onset_candidate"] is False


@pytest.mark.parametrize(
    "change",
    [
        {"pace_window_count": 119},
        {"pace_end_ts_ms": ANCHOR},
        {"pace_available_ts_ms": ANCHOR + 1},
        {"pace_trade_median_30s": 0, "pace_quote_usd_median_30s": 0},
    ],
)
def test_onset_unavailable_does_not_erase_complete_forward_label(change):
    _, result = grade(base=baseline(**change))
    assert result["verified_forward"] is True
    assert result["verified_onset"] is None
    assert result["onset_status"] == "unavailable"


def test_appending_or_changing_after_horizon_cannot_change_label():
    rows = samples()
    _, expected = grade([row for row in rows if row.ts_ms <= ANCHOR + 300_000])
    changed = [
        (
            replace(row, bid=1, ask=2, coverage_verified=False)
            if row.ts_ms > ANCHOR + 300_000
            else row
        )
        for row in rows
    ]
    _, actual = grade(changed)
    assert actual == expected


@pytest.mark.parametrize("direction", ["up", "down"])
def test_prediction_detection_and_half_consumed_boundary(direction):
    engine, label = grade(direction=direction)
    before = engine.alert_timing(label, ANCHOR - 5000)
    assert before["timing"] == "pre_onset_prediction"
    assert before["detection_delay_seconds"] == -5
    assert before["consumed_fraction"] < 0  # deliberately not clipped
    assert engine.alert_timing(label, ANCHOR)["timing"] == "early_detection"
    half = engine.alert_timing(label, ANCHOR + 150_000)
    assert half["consumed_fraction"] == pytest.approx(0.5)
    assert half["timing"] == "late_detection"
    assert (
        engine.alert_timing(label, ANCHOR - 185_000)["timing"] == "outside_event_window"
    )


def test_unaligned_publication_uses_only_backward_asof_snapshot():
    engine, label = grade()
    result = engine.alert_timing(label, ANCHOR + 4999)
    assert result["price_snapshot_ts_ms"] == ANCHOR
    assert result["consumed_fraction"] == 0


def test_costs_apply_once_to_coin_return_not_market_residual():
    _, label = grade(samples(btc=lambda t: 0.01 * max(t, 0) / 300))
    expected = math.expm1(0.03) * 10000
    assert label["terminal_residual_log"] == pytest.approx(0.02)
    assert label["gross_coin_return_bps"] == pytest.approx(expected)
    assert label["cost_scenarios"][0]["net_coin_return_bps"] == pytest.approx(
        expected - 2
    )
    assert label["cost_scenarios"][1]["net_coin_return_bps"] == pytest.approx(
        expected - 2 - 20
    )


def test_catalog_deduplicates_events_without_merging_directions_or_horizons():
    _, label = grade()
    later = {
        **label,
        "anchor_ts_ms": ANCHOR + 5000,
        "label_maturity_ts_ms": ANCHOR + 305_000,
    }
    boundary = {
        **label,
        "anchor_ts_ms": ANCHOR + 300_000,
        "label_maturity_ts_ms": ANCHOR + 600_000,
    }
    down = {**label, "direction": "down"}
    longer = {**label, "horizon_seconds": 900, "label_maturity_ts_ms": ANCHOR + 900_000}
    assert target.event_catalog([later, boundary, down, label, longer]) == [
        down,
        label,
        longer,
        boundary,
    ]
    with pytest.raises(ValueError, match="mix"):
        target.event_catalog([label, {**label, "contract_sha256": "different"}])


def test_invalid_series_cannot_silently_sort_or_mix_products():
    rows = samples()
    for bad in (
        [rows[1], rows[0]],
        [rows[0], rows[0]],
        [rows[0], replace(rows[1], product_id="OTHER-USD")],
        [replace(rows[0], ts_ms=1)],
    ):
        with pytest.raises(ValueError):
            target.TargetEvaluator(bad)


def test_trades_exactly_at_anchor_are_excluded_and_unknown_boundary_is_unavailable():
    rows = [
        (
            replace(row, trade_count=3, trade_count_at_bucket_start=3)
            if row.ts_ms == ANCHOR + 5000
            else replace(row, trade_count=0)
        )
        for row in samples()
    ]
    _, result = grade(rows)
    assert result["forward_trade_count"] == 0
    assert result["verified_forward"] is False
    rows = [
        (
            replace(row, trade_count_at_bucket_start=None)
            if row.ts_ms == ANCHOR + 5000
            else row
        )
        for row in samples()
    ]
    _, result = grade(rows)
    assert result["reason"] == "unknown_boundary_trade_count"
    assert result["verified_forward"] is None


@pytest.mark.parametrize("sigma,spread", [(0.005, 2), (0.0015, 100)])
def test_volatility_and_spread_each_can_raise_required_magnitude(sigma, spread):
    rows = samples()
    start_mid = next(row.mid for row in rows if row.ts_ms == ANCHOR)
    rows = [
        (
            replace(
                row,
                bid=start_mid * (1 - spread / 20000),
                ask=start_mid * (1 + spread / 20000),
            )
            if row.ts_ms == ANCHOR
            else row
        )
        for row in rows
    ]
    _, result = grade(rows, base=baseline(sigma_1m=sigma))
    assert result["required_terminal_log"] > result["terminal_residual_log"]
    assert result["verified_forward"] is False


def test_breakout_deadline_is_not_extended_to_get_a_success():
    _, result = grade(
        samples(residual=lambda t: 0 if t < 0 else 0.002 + (0.02 if t >= 200 else 0))
    )
    assert result["verified_forward"] is True
    assert result["onset_candidate"] is True
    assert result["breakout_ts_ms"] is None
    assert result["verified_onset"] is False


def test_healthy_zero_trade_buckets_are_known_observations():
    rows = [
        (
            replace(row, trade_count=0, quote_volume_usd=0)
            if row.ts_ms == ANCHOR + 50_000
            else row
        )
        for row in samples()
    ]
    _, result = grade(rows)
    assert result["status"] == "ready"
    assert result["verified_forward"] is True


def test_zero_move_is_a_complete_negative_and_is_retained_outside_boards():
    _, result = grade(samples(residual=lambda t: 0))
    assert result["status"] == "ready"
    assert result["verified_forward"] is False
    assert result["verified_onset"] is False
    assert result["retention"] is None


def test_exact_minimum_log_magnitude_passes_with_float_tolerance():
    _, result = grade(
        samples(residual=lambda t: 0 if t < 0 else 0.002 + 0.015 * min(t / 300, 1))
    )
    assert result["terminal_residual_log"] == pytest.approx(0.015)
    assert result["verified_forward"] is True


def test_unavailable_alert_quote_does_not_select_a_future_quote():
    engine, label = grade()
    with_gap = target.TargetEvaluator(
        [row for row in samples() if row.ts_ms != ANCHOR - 5000]
    )
    assert with_gap.alert_timing(label, ANCHOR - 1)["timing"] == "unavailable"
    with pytest.raises(ValueError, match="verified onset"):
        engine.alert_timing({**label, "verified_onset": False}, ANCHOR)


def test_contract_hash_and_scope_travel_with_every_label():
    import hashlib

    _, result = grade()
    assert (
        result["contract_sha256"]
        == hashlib.sha256(
            target.CONTRACT_PATH.read_text(encoding="utf-8").encode("utf-8")
        ).hexdigest()
    )
    assert result["evaluation_only"] is True
    cfg, _ = target.load_contract()
    assert cfg["fitting_allowed"] is False


def test_contract_hash_is_portable_across_windows_and_unix_newlines(
    tmp_path, monkeypatch
):
    cfg, expected = target.load_contract()
    portable = tmp_path / "contract.json"
    portable.write_bytes(
        target.CONTRACT_PATH.read_text(encoding="utf-8")
        .replace("\n", "\r\n")
        .encode("utf-8")
    )
    monkeypatch.setattr(target, "CONTRACT_PATH", portable)
    actual_cfg, actual = target.load_contract()
    assert actual == expected and actual_cfg == cfg


def test_missing_or_invalid_baseline_metadata_is_unavailable():
    engine = target.TargetEvaluator(samples())
    for base, reason in (
        (None, "missing_baseline"),
        (baseline(available_ts_ms=None), "invalid_baseline_metadata"),
    ):
        result = engine.evaluate(ANCHOR, base, "up", 300, ANCHOR + 300_000)
        assert result["status"] == "unavailable" and result["reason"] == reason


def test_invalid_asof_cannot_mature_future_labels():
    engine = target.TargetEvaluator(samples())
    with pytest.raises(ValueError, match="as-of"):
        engine.evaluate(ANCHOR, baseline(), "up", 300, float("nan"))
