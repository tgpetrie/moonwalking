"""Synthetic checks for the A1 confirmation driver. No market data."""

import importlib.util
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = "scripts/scoring_experiment/confirm_a1_gate_20261115.py"
spec = importlib.util.spec_from_file_location("a1", ROOT / SCRIPT)
a1 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(a1)


def test_halves_partition_the_scored_window_as_declared():
    days = list(pd.date_range(*a1.WINDOWS["all"]).strftime("%Y-%m-%d"))
    first = list(pd.date_range(*a1.WINDOWS["first_half"]).strftime("%Y-%m-%d"))
    second = list(pd.date_range(*a1.WINDOWS["second_half"]).strftime("%Y-%m-%d"))
    assert (len(days), len(first), len(second)) == (31, 15, 16)
    assert first + second == days
    # Seven full UTC days of trailing thresholds precede the first scored day.
    assert a1.WARMUP == a1.screen.stamp(days[0]) - 7 * 86400
    assert a1.SEAL == a1.screen.stamp(days[-1]) + 86400


def test_sealed_data_is_refused():
    a1.assert_sealed([a1.SEAL - 1])
    a1.assert_sealed([])
    with pytest.raises(SystemExit, match="2026-11-13"):
        a1.assert_sealed([a1.SEAL - 1, a1.SEAL])


def test_candle_stores_merge_once_at_the_seam_and_stop_at_the_seal():
    def frame(rows):
        return pd.DataFrame(rows, columns=["product_id", "ts", "close"])

    archive = frame([("B-USD", 120, 2.0), ("A-USD", 60, 1.0), ("A-USD", 120, 1.5)])
    backfill = frame(
        [("A-USD", 120, 99.0), ("A-USD", 180, 3.0), ("A-USD", a1.SEAL, 7.0)]
    )
    merged = a1.merge_candles([archive, backfill])
    rows = list(merged.itertuples(index=False, name=None))
    assert rows == [
        ("A-USD", 60, 1.0),
        ("A-USD", 120, 1.5),  # the archive row wins the overlapping minute
        ("A-USD", 180, 3.0),
        ("B-USD", 120, 2.0),
    ]


def test_reading_applies_the_nov14_rule_and_the_half_check():
    def cell(dp, dc, lo=None, hi=None):
        return {
            "delta_P": {"mean": dp, "block3": {"lo": lo, "hi": None}},
            "delta_C": {"mean": dc, "block3": {"lo": None, "hi": hi}},
        }

    board = {
        "all": cell(0.003, -0.029, lo=-0.002, hi=-0.020),
        "first_half": cell(0.001, -0.031),
        "second_half": cell(-0.004, -0.027),
    }
    out = a1.reading(board)
    assert out["meets_nov14_rule"] is True and out["stable_across_halves"] is True
    board["all"] = cell(0.003, -0.024, lo=-0.002, hi=-0.020)  # mean cut too small
    assert a1.reading(board)["checks"]["dC_mean"] is False
    assert a1.reading(board)["meets_nov14_rule"] is False
    board["second_half"] = cell(-0.006, -0.027)  # runners lost in one half
    assert a1.reading(board)["halves"] == {"first_half": True, "second_half": False}


def test_parity_compares_counts_and_rounded_differences():
    full = {
        "entries": 51997,
        "flags": {"base": 12773, "arm": 12465},
        "delta_P": {"mean": 0.00296},
        "delta_C": {"mean": -0.02894},
    }
    assert a1.parity(full)["match"] is True
    full["flags"]["arm"] = 12464
    assert a1.parity(full)["match"] is False
