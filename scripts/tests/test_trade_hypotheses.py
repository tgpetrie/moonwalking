"""Research correctness checks; no exchange or Railway access in tests."""

from contextlib import redirect_stdout
import gzip
import io
import json
from pathlib import Path
import sqlite3
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import evaluate_trade_hypotheses as analysis
import export_trade_research as exporter
import backfill_research_candles as backfill

H = analysis.HOUR


def candle(ts=0, open_=100, high=102, low=98, close=101, volume=10):
    return analysis.Candle(ts, open_, high, low, close, volume)


def source_row(**overrides):
    return {
        "kind": "candle",
        "product_id": "SOL-USD",
        "hour_ts": 0,
        "open": 100,
        "high": 102,
        "low": 98,
        "close": 101,
        "base_volume": 10,
        "source": "coinbase_exchange_ohlcv",
        **overrides,
    }


def signal(ts=15 * H + 20, **overrides):
    return {
        "kind": "signal",
        "signal_id": "s1",
        "event_id": "e1",
        "product_id": "SOL-USD",
        "primary_state": "Breakout",
        "read_label": "BUY WATCH",
        "direction": "up",
        "confidence": 85,
        "started_ts": ts,
        "start_price": 100,
        **overrides,
    }


def write_export(path, rows):
    with gzip.open(path, "wt", encoding="utf-8") as handle:
        for row in [
            {"kind": "manifest", "schema_version": 1, "captured_ts": 100 * H},
            *rows,
            {
                "kind": "counts",
                "signal": sum(r["kind"] == "signal" for r in rows),
                "candle": sum(r["kind"] == "candle" for r in rows),
            },
        ]:
            handle.write(json.dumps(row) + "\n")


@pytest.mark.parametrize("bad", [None, True, "NaN", float("inf"), "bad"])
def test_nonfinite_and_boolean_values_are_unavailable(bad):
    assert analysis.number(bad) is None


@pytest.mark.parametrize(
    "row",
    [
        source_row(open=0),
        source_row(low=103),
        source_row(hour_ts=1),
        source_row(base_volume=-1),
        source_row(source="coinbase_minute_rollup", minute_coverage=60),
    ],
)
def test_malformed_and_sampled_close_candles_rejected(row):
    assert analysis.candle_from_row(row) is None


def test_native_exchange_candles_need_no_invented_minute_coverage():
    assert analysis.candle_from_row(source_row()) == candle()


def test_latest_transition_per_hour_is_deterministic_and_never_same_open(tmp_path):
    path = tmp_path / "export.gz"
    write_export(
        path,
        [
            signal(ts=H, signal_id="a"),
            signal(ts=H + 30, signal_id="z"),
            signal(ts=H + 30, signal_id="b"),
        ],
    )
    rows, _, audit, _ = analysis.load_export(path)
    assert len(rows) == 1
    assert rows[("SOL-USD", 2 * H)]["signal_id"] == "z"
    assert audit["signal"] == 3


def test_conflicting_candle_is_invalidated_not_last_write_wins(tmp_path):
    path = tmp_path / "export.gz"
    write_export(path, [source_row(), source_row(close=100), source_row()])
    _, bars, audit, _ = analysis.load_export(path)
    assert bars["SOL-USD"] == {}
    assert audit["invalid_or_duplicate_candle"] == 2


def test_truncated_export_refused(tmp_path):
    path = tmp_path / "export.gz"
    with gzip.open(path, "wt") as handle:
        handle.write(json.dumps(signal()) + "\n")
    with pytest.raises(ValueError, match="Incomplete"):
        analysis.load_export(path)


@pytest.mark.parametrize(
    "direction,bar", [(1, candle(high=102, low=98)), (-1, candle(high=102, low=98))]
)
def test_same_bar_target_and_stop_stays_ambiguous(direction, bar):
    result = analysis.first_touch(
        [bar], 100, direction, 100 - direction, 100 + direction
    )
    assert result == {"status": "ambiguous", "bar_ts": 0, "gap": False}


def test_gap_has_known_precedence_even_if_both_extremes_cross():
    result = analysis.first_touch(
        [candle(open_=103, high=104, low=98)], 100, 1, 99, 101
    )
    assert result["status"] == "target_first"
    assert result["gap"]


@pytest.mark.parametrize("direction,expected", [(1, (2, -1, 1)), (-1, (1, -2, -1))])
def test_directional_excursions_and_round_trip_costs(direction, expected):
    bars = {0: candle(high=104, low=98, close=101)}
    result = analysis.measure(
        bars, 0, 100, direction, 2, 100 - 2 * direction, 100 + 2 * direction, H, 0.9
    )
    assert result["mfe_atr"] == expected[0]
    assert result["mae_atr"] == expected[1]
    assert result["return_pct"] == pytest.approx(expected[2])
    assert result["net_forward_return_pct"] == pytest.approx(expected[2] - 0.9)


def test_missing_bar_never_late_filled():
    bars = {0: candle(), 2 * H: candle(2 * H)}
    assert not analysis.measure(bars, 0, 100, 1, 2, 98, 102, 2 * H, 0)["available"]
    assert not analysis.measure(bars, 0, 100, 1, 2, 98, 102, 900, 0)["available"]


def test_split_purges_overlapping_outcomes_on_both_boundaries():
    end = 1000 * H
    assert analysis.split_for(575 * H, 0, end) == "train"
    assert analysis.split_for(576 * H, 0, end) == "purged"
    assert analysis.split_for(600 * H, 0, end) == "validation"
    assert analysis.split_for(776 * H, 0, end) == "purged"
    assert analysis.split_for(800 * H, 0, end) == "test"


def test_future_extremes_cannot_change_geometry_confidence_or_action():
    bars = {i * H: candle(i * H) for i in range(45)}
    original = analysis.build_decision(signal(), 16 * H, bars, bars, 15, 0.1)
    bars[16 * H] = candle(16 * H, high=999, low=1, close=500)
    changed = analysis.build_decision(signal(), 16 * H, bars, bars, 15, 0.1)
    for key in ("opportunity", "confidence", "context", "action"):
        assert original[key] == changed[key]
    assert original["outcomes"] != changed["outcomes"]


def test_evidence_score_cannot_override_bad_geometry():
    bars = {i * H: candle(i * H) for i in range(45)}
    row = analysis.build_decision(signal(confidence=100), 16 * H, bars, bars, 15, 1.0)
    assert row["confidence"]["score"] == 100
    assert row["opportunity"]["score"] is None
    assert row["action"] == "NO_TRADE"


def test_missing_direction_never_becomes_a_trade():
    row = analysis.build_decision(signal(direction="neutral"), 16 * H, {}, {}, 15, 0)
    assert row["reason"] == "no_directional_hypothesis"
    assert row["outcomes"] == {}


def test_ambiguity_stays_in_fraction_denominator_and_small_samples_have_no_ci():
    rows = []
    for i, status in enumerate(("target_first", "ambiguous", "neither", "stop_first")):
        rows.append(
            {
                "event_id": str(i),
                "decision_ts": i * H,
                "outcomes": {
                    str(H): {
                        "available": True,
                        "atr_first_touch": {"status": status},
                        "net_forward_return_pct": 1,
                        "mfe_atr": 2,
                        "mae_atr": -1,
                    }
                },
            }
        )
    result = analysis.summarize(rows, H)
    assert result["target_first_fraction_bounds"] == [0.25, 0.5]
    assert result["daily_block_bootstrap_95_interval"] is None
    assert result["utc_days"] == 1


def test_export_roundtrip_is_market_only_read_only_and_checksum_checked(tmp_path):
    db = sqlite3.connect(tmp_path / "signal_outcomes.sqlite")
    db.execute(
        "CREATE TABLE signal_outcomes (signal_id,event_id,product_id,primary_state,read_label,direction,confidence,started_ts,start_price)"
    )
    db.execute(
        "INSERT INTO signal_outcomes VALUES ('s','e','SOL-USD','Breakout','BUY WATCH','up',85,1,100)"
    )
    db.execute("CREATE TABLE users (email,password_hash)")
    db.execute("INSERT INTO users VALUES ('private@example.invalid','secret-fixture')")
    db.commit()
    db.close()
    db = sqlite3.connect(tmp_path / "volume_1h.sqlite")
    db.execute(
        "CREATE TABLE volume_hour (product_id,hour_ts,open,high,low,close,base_volume,minute_coverage,source)"
    )
    db.commit()
    db.close()
    before = {p: p.read_bytes() for p in tmp_path.glob("*.sqlite")}
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        exporter.export(tmp_path)
    envelope = tmp_path / "envelope.txt"
    envelope.write_text(buffer.getvalue(), encoding="utf-8")
    output = tmp_path / "decoded.gz"
    exporter.decode(envelope, output)
    assert len(analysis.load_export(output)[0]) == 1
    with gzip.open(output, "rt") as handle:
        assert "private@example.invalid" not in handle.read()
    assert all(p.read_bytes() == content for p, content in before.items())
    with pytest.raises(FileExistsError):
        exporter.decode(envelope, output)
    envelope.write_text(
        buffer.getvalue().replace("BHABIT_RESEARCH_BEGIN ", "BHABIT_RESEARCH_BEGIN 0")
    )
    with pytest.raises(ValueError, match="checksum"):
        exporter.decode(envelope, tmp_path / "corrupt.gz")


def test_cached_exchange_response_filters_outside_range_and_incomplete(tmp_path):
    cache = tmp_path / "SOL-USD-3600-10800.json"
    cache.write_text(
        json.dumps(
            {
                "fetched_ts": 2 * H + 30,
                "candles": [
                    [0, 98, 102, 100, 101, 10],
                    [H, 98, 102, 100, 101, 10],
                    [2 * H, 98, 102, 100, 101, 10],
                ],
            }
        )
    )
    rows = backfill.fetch_window("SOL-USD", H, 3 * H, tmp_path)
    assert [row["hour_ts"] for row in rows] == [H]


def test_end_to_end_output_and_cost_validation(tmp_path):
    source = tmp_path / "input.gz"
    rows = [source_row(hour_ts=i * H) for i in range(100)] + [signal()]
    write_export(source, rows)
    result = analysis.run(source, tmp_path / "results", [15], 40, 5)
    assert result["costs"]["round_trip_pct"] == 0.9
    assert (
        result["lookbacks"]["15"]["splits"]["test"]["horizons"][str(H)]["measured"] == 1
    )
    with pytest.raises(FileExistsError):
        analysis.run(source, tmp_path / "results", [15], 40, 5)
    with pytest.raises(ValueError):
        analysis.run(source, tmp_path / "other", [15], -1, 5)
