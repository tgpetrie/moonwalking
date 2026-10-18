"""Path-resolution and cost checks; no network calls."""

import copy
import gzip
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import backfill_research_candles as backfill
import evaluate_resolution_costs as grid
import evaluate_trade_hypotheses as analysis

H, Q = analysis.HOUR, grid.QUARTER_HOUR


def bar(ts=0, open_=100, high=102, low=98, close=101):
    return analysis.Candle(ts, open_, high, low, close, 10)


def native_row(ts, granularity):
    return {
        "kind": "candle",
        "candle_ts": ts,
        "granularity_seconds": granularity,
        "product_id": "SOL-USD",
        "open": 100,
        "high": 102,
        "low": 98,
        "close": 101,
        "base_volume": 10,
        "source": "coinbase_exchange_ohlcv",
    }


def export(path, granularity, *, signal_id="s"):
    signal = {
        "kind": "signal",
        "signal_id": signal_id,
        "event_id": "e",
        "product_id": "SOL-USD",
        "primary_state": "Breakout",
        "read_label": "BUY WATCH",
        "direction": "up",
        "confidence": 85,
        "started_ts": 15 * H + 10,
        "start_price": 100,
    }
    rows = [signal] + [
        native_row(ts, granularity) for ts in range(0, 42 * H, granularity)
    ]
    with gzip.open(path, "wt", encoding="utf-8") as handle:
        for row in [
            {
                "kind": "manifest",
                "schema_version": 1,
                "captured_ts": 42 * H,
                "candle_granularity_seconds": granularity,
            },
            *rows,
            {"kind": "counts", "signal": 1, "candle": len(rows) - 1},
        ]:
            handle.write(json.dumps(row) + "\n")


def row_with_path():
    return {
        "event_id": "e",
        "decision_ts": 0,
        "action": "RESEARCH_CANDIDATE",
        "reason": "fixture",
        "opportunity": {
            "atr": 1,
            "atr_pct": 1,
            "risk_pct": 1,
            "reward_pct": 2,
            "invalid": 99,
            "net_reward_risk": 2,
            "extension_atr": 1,
            "confirmation_families": ["price_structure", "volume"],
        },
        "outcomes": {
            str(Q): {
                "available": True,
                "return_pct": 1.2,
                "net_forward_return_pct": 1.2,
                "mfe_atr": 2,
                "mae_atr": -1,
                "atr_first_touch": {"status": "target_first"},
                "geometry_first_touch": {"status": "target_first"},
            }
        },
    }


def test_quarter_hour_timestamps_require_explicit_resolution():
    row = native_row(Q, Q)
    assert analysis.candle_from_row(row) is None
    assert analysis.candle_from_row(row, granularity_seconds=Q).ts == Q


def test_fine_export_cannot_silently_feed_hourly_features(tmp_path):
    path = tmp_path / "fine.gz"
    export(path, Q)
    with pytest.raises(ValueError, match="granularity"):
        analysis.load_export(path)
    assert (
        analysis.load_export(path, candle_granularity_seconds=Q)[2]["valid_candles"]
        == 168
    )


@pytest.mark.parametrize("direction,close,gross", [(1, 101, 1), (-1, 99, 1)])
def test_fifteen_minute_return_and_costs(direction, close, gross):
    result = analysis.measure(
        {0: bar(close=close)},
        0,
        100,
        direction,
        1,
        100 - direction,
        100 + direction,
        Q,
        0.9,
        granularity_seconds=Q,
    )
    assert result["available"]
    assert result["return_pct"] == pytest.approx(gross)
    assert result["net_forward_return_pct"] == pytest.approx(0.1)


@pytest.mark.parametrize(
    "first_high,first_low,expected",
    [(102, 99.5, "target_first"), (100.5, 98, "stop_first")],
)
def test_finer_path_resolves_hourly_order_without_inventing_intrabar_order(
    first_high, first_low, expected
):
    coarse = analysis.first_touch([bar()], 100, 1, 99, 101)
    fine = analysis.first_touch([bar(high=first_high, low=first_low)], 100, 1, 99, 101)
    assert coarse["status"] == "ambiguous"
    assert fine["status"] == expected
    assert analysis.first_touch([bar()], 100, 1, 99, 101)["status"] == "ambiguous"


def test_missing_quarter_hour_invalidates_hourly_horizon():
    fine = {0: bar(), Q: bar(Q), 3 * Q: bar(3 * Q)}
    result = analysis.measure(fine, 0, 100, 1, 1, 99, 101, H, 0, granularity_seconds=Q)
    assert not result["available"]


def test_partial_or_zero_horizon_is_not_silently_rounded():
    assert not analysis.measure(
        {0: bar()}, 1, 100, 1, 1, 99, 101, Q, 0, granularity_seconds=Q
    )["available"]
    assert not analysis.measure(
        {0: bar()}, 0, 100, 1, 1, 99, 101, 60, 0, granularity_seconds=Q
    )["available"]
    with pytest.raises(ValueError, match="positive"):
        analysis.measure({0: bar()}, 0, 100, 1, 1, 99, 101, 0, 0, granularity_seconds=Q)


def test_cost_overlay_preserves_gross_path_and_input_and_uses_percent_units():
    original = row_with_path()
    before = copy.deepcopy(original)
    adjusted = grid.with_cost(original, 90)
    assert original == before
    assert adjusted["outcomes"][str(Q)]["return_pct"] == 1.2
    assert adjusted["outcomes"][str(Q)]["net_forward_return_pct"] == pytest.approx(0.3)
    assert adjusted["cost_in_atr"] == pytest.approx(0.9)
    assert adjusted["opportunity"]["net_reward_risk"] == pytest.approx(1.1 / 1.9)
    assert adjusted["action"] == "NO_TRADE"
    assert (
        adjusted["outcomes"][str(Q)]["atr_first_touch"]
        == before["outcomes"][str(Q)]["atr_first_touch"]
    )


def test_iso_calendar_week_and_insufficient_week_count():
    assert grid.week_key(1609459200) == "2020-W53"
    summary = grid.cost_summary([grid.with_cost(row_with_path(), 90)], Q)
    assert summary["calendar_weeks"] == 1
    assert summary["weekly_cluster_bootstrap_95_interval"] is None


def test_weekly_interval_is_reproducible_and_requires_twelve_blocks():
    rows = []
    for i in range(12):
        row = row_with_path()
        row["decision_ts"] = i * 7 * 86400
        rows.append(grid.with_cost(row, 90))
    first = grid.cost_summary(rows, Q)
    assert first["calendar_weeks"] == 12
    assert first["weekly_cluster_bootstrap_95_interval"] == pytest.approx([0.3, 0.3])
    assert first == grid.cost_summary(rows, Q)


def test_fine_cache_does_not_collide_with_hourly_cache(tmp_path):
    response = {"fetched_ts": 2 * H, "candles": [[Q, 98, 102, 100, 101, 10]]}
    (tmp_path / "SOL-USD-0-3600-g900.json").write_text(json.dumps(response))
    (tmp_path / "SOL-USD-0-3600.json").write_text(
        json.dumps({"fetched_ts": 2 * H, "candles": [[0, 98, 102, 100, 101, 10]]})
    )
    fine = backfill.fetch_window("SOL-USD", 0, H, tmp_path, granularity_seconds=Q)
    coarse = backfill.fetch_window("SOL-USD", 0, H, tmp_path)
    assert fine[0]["candle_ts"] == Q
    assert coarse[0]["candle_ts"] == 0


def test_cost_grid_keeps_same_cohort_and_fills_15m_horizon(tmp_path):
    hourly, fine = tmp_path / "hourly.gz", tmp_path / "fine.gz"
    export(hourly, H)
    export(fine, Q)
    result = grid.run(hourly, fine, tmp_path / "results", [0, 20, 90], 15)
    observed = []
    for scenario in result["cost_scenarios"].values():
        outcome = scenario["splits"]["test"]["fixed_cohort_horizons"][str(Q)]
        assert outcome["measured"] == 1
        observed.append(outcome["mean_net_forward_return_pct"])
    assert observed == pytest.approx([1, 0.8, 0.1])
    assert result["resolution_comparison"][str(H)]["paired_decisions"] == 1
    with pytest.raises(FileExistsError):
        grid.run(hourly, fine, tmp_path / "results", [90], 15)


def test_different_cohorts_fail_before_creating_outputs(tmp_path):
    hourly, fine = tmp_path / "hourly.gz", tmp_path / "fine.gz"
    export(hourly, H)
    export(fine, Q, signal_id="different")
    with pytest.raises(ValueError, match="identical"):
        grid.run(hourly, fine, tmp_path / "results", [90], 15)
    assert not (tmp_path / "results").exists()


def test_entry_open_disagreement_is_reported_and_not_averaged_away(tmp_path):
    hourly, fine = tmp_path / "hourly.gz", tmp_path / "fine.gz"
    export(hourly, H)
    export(fine, Q)
    with gzip.open(fine, "rt", encoding="utf-8") as handle:
        rows = [json.loads(line) for line in handle]
    for row in rows:
        if row.get("kind") == "candle" and row["candle_ts"] == 16 * H:
            row["open"] = 100.5
    with gzip.open(fine, "wt", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row) + "\n")
    result = grid.run(hourly, fine, tmp_path / "results", [90], 15)
    assert result["entry_open_disagreements"] == 1
    assert (
        result["cost_scenarios"]["90"]["splits"]["test"]["fixed_cohort_horizons"][
            str(Q)
        ]["measured"]
        == 0
    )


@pytest.mark.parametrize("cost", [-1, float("nan"), float("inf")])
def test_invalid_cost_scenarios_fail_before_reading_inputs(tmp_path, cost):
    with pytest.raises(ValueError, match="cost"):
        grid.run("missing", "missing", tmp_path / "results", [cost])
