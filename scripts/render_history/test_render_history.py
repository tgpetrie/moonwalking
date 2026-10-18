"""Tests for the RENDER/RNDR history builder and the committed dataset.

Run:  python -I -m pytest scripts/render_history -q
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import build_datasets as bd  # noqa: E402

DATA = HERE.parents[1] / "data" / "render-history"
DAY = bd.DAY
INCOMPLETE_FLAGS = {"open_period", "starts_before_first_candle", "series_ends_mid_week"}


def ts(date: str) -> int:
    return bd.parse_iso(date + "T00:00:00Z")


def row(date: str, o=1.0, h=1.2, l=0.9, c=1.1, v=10.0):
    return [ts(date), l, h, o, c, v]


# ---- weekly aggregation --------------------------------------------------

def test_week_starts_on_monday():
    assert bd.day(bd.week_start(ts("2026-10-18"))) == "2026-10-12"  # Sunday
    assert bd.day(bd.week_start(ts("2026-10-12"))) == "2026-10-12"  # Monday
    assert bd.day(bd.week_start(ts("2024-02-15"))) == "2024-02-12"  # Thursday


def full_week(start_date: str):
    t0 = ts(start_date)
    return [[t0 + i * DAY, 0.9 + i, 1.2 + i, 1.0 + i, 1.1 + i, 10.0] for i in range(7)]


def test_complete_week_aggregates_ohlcv():
    rows = full_week("2026-01-05") + full_week("2026-01-12") + full_week("2026-01-19")
    weeks = bd.build_weekly(rows, as_of=ts("2026-03-01"), series_ends=False)
    mid = weeks[1]
    assert mid["complete"] and mid["flags"] == []
    assert mid["o"] == rows[7][3] and mid["c"] == rows[13][4]
    assert mid["h"] == max(r[2] for r in rows[7:14]) and mid["l"] == min(r[1] for r in rows[7:14])
    assert mid["v"] == 70.0 and mid["days_present"] == 7


def test_first_week_flagged_when_series_starts_midweek():
    rows = [row("2024-02-15"), row("2024-02-16"), row("2024-02-17"), row("2024-02-18")] + full_week("2024-02-19")
    weeks = bd.build_weekly(rows, as_of=ts("2025-01-01"), series_ends=False)
    assert not weeks[0]["complete"] and "starts_before_first_candle" in weeks[0]["flags"]
    assert weeks[0]["days_present"] == 4
    assert weeks[1]["complete"]


def test_current_week_is_open_for_live_series():
    rows = full_week("2026-10-05") + [row("2026-10-12"), row("2026-10-13")]
    weeks = bd.build_weekly(rows, as_of=ts("2026-10-14"), series_ends=False)
    assert weeks[-1]["flags"] == ["open_period"] and not weeks[-1]["complete"]


def test_last_week_of_delisted_series_flagged_not_dropped():
    rows = full_week("2025-06-16") + [row("2025-06-23"), row("2025-06-24")]
    weeks = bd.build_weekly(rows, as_of=ts("2026-01-01"), series_ends=True)
    assert len(weeks) == 2
    assert weeks[-1]["flags"] == ["series_ends_mid_week"] and not weeks[-1]["complete"]


def test_no_trade_day_inside_complete_week_is_noted_not_filled():
    rows = full_week("2026-01-05")
    rows = rows[:3] + rows[4:]  # drop Thursday
    weeks = bd.build_weekly([row("2026-01-01")] + rows + full_week("2026-01-12"), as_of=ts("2026-03-01"), series_ends=False)
    # The week with a hole is inside the span (data before and after), so it is complete.
    assert weeks[1]["days_present"] == 6
    assert weeks[1]["complete"] is True and weeks[1]["flags"] == ["no_trade_days_inside_week"]


# ---- daily validation ----------------------------------------------------

def test_row_problems_catches_broken_candles():
    bad = [[ts("2026-01-01") + 5, 1, 2, 1.5, 1.6, 1], [ts("2026-01-02"), 1, 0.5, 1.5, 1.6, 1], [ts("2026-01-03"), 1, 2, 1.5, 1.6, -1]]
    problems = bd.row_problems(bad)
    assert any("not aligned" in p for p in problems)
    assert any("OHLC invariant" in p for p in problems)
    assert any("negative volume" in p for p in problems)


def test_missing_ranges_reports_gap_days():
    rows = [row("2026-01-01"), row("2026-01-02"), row("2026-01-05")]
    assert bd.missing_ranges(rows) == [{"from": "2026-01-03", "to": "2026-01-04", "days": 2}]


def test_open_day_is_not_complete():
    candles = bd.build_daily([row("2026-10-17"), row("2026-10-18")], as_of=ts("2026-10-18"))
    assert candles[0]["complete"] and not candles[1]["complete"]
    assert candles[1]["flags"] == ["open_period"]


# ---- cross-check against hourly -----------------------------------------

def test_crosscheck_ohlc_exact_and_volume_tolerant():
    d0 = ts("2026-01-01")
    hourly = [[d0 + h * 3600, 1.0 + h * 0.01, 1.5 + h * 0.01, 0.9 + h * 0.01, 1.0 + h * 0.01 + 0.001, 1.0] for h in range(24)]
    native = [[d0, min(h[3] for h in hourly), max(h[2] for h in hourly), hourly[0][1], hourly[-1][4], 24.0001]]
    windows = [(d0, d0 + 23 * 3600, 24, "ok")]
    result = bd.crosscheck_daily_vs_hourly(native, hourly, windows)
    assert result["days_compared"] == 1 and result["ohlc_days_matching"] == 1
    assert result["volume_days_differing"] == 1 and result["passed"]


def test_crosscheck_fails_on_price_mismatch():
    d0 = ts("2026-01-01")
    hourly = [[d0 + h * 3600, 1.0, 1.5, 0.9, 1.0, 1.0] for h in range(24)]
    native = [[d0, 0.8, 1.5, 1.0, 1.0, 24.0]]
    result = bd.crosscheck_daily_vs_hourly(native, hourly, [(d0, d0 + 23 * 3600, 24, "ok")])
    assert result["ohlc_mismatches"] and not result["passed"]


# ---- committed dataset ---------------------------------------------------

needs_data = pytest.mark.skipif(not (DATA / "index.json").exists(), reason="dataset not built")


@needs_data
def test_index_lists_eight_series_and_validation_passed():
    index = json.loads((DATA / "index.json").read_text())
    assert len(index["series"]) == 8
    assert json.loads((DATA / "validation.json").read_text())["passed"] is True


@needs_data
@pytest.mark.parametrize("kind,ext", [("series", "1d"), ("weekly", "1w")])
@pytest.mark.parametrize("product", bd.PRODUCTS)
def test_series_files_follow_contract(kind, ext, product):
    doc = json.loads((DATA / kind / f"coinbase_{product}_{ext}.json").read_text())
    assert doc["contract"] == bd.CONTRACT
    assert doc["provenance"]["stitched"] is False and doc["provenance"]["authenticated"] is False
    assert doc["market"]["product_id"] == product and doc["asset"]["symbol"] == product.split("-")[0]
    assert doc["coverage"]["lowest_daily_low"]["is_all_time_low"] is False
    candles = doc["candles"]
    times = [c["t"] for c in candles]
    assert times == sorted(set(times)), "ascending, no duplicates"
    for c in candles:
        assert c["l"] <= min(c["o"], c["c"]) and c["h"] >= max(c["o"], c["c"]) and c["v"] >= 0
        assert c["complete"] == (not set(c["flags"]) & INCOMPLETE_FLAGS)


@needs_data
def test_no_candle_is_complete_while_open():
    doc = json.loads((DATA / "series" / "coinbase_RENDER-USD_1d.json").read_text())
    last = doc["candles"][-1]
    assert last["t"].startswith(doc["as_of"][:10]) and not last["complete"]
    assert all(c["complete"] for c in doc["candles"][:-1])


@needs_data
def test_render_and_rndr_are_never_merged():
    cov = json.loads((DATA / "coverage.json").read_text())
    assert cov["lineage"]["stitched"] is False
    assert cov["all_time_low"]["established"] is False
    render = json.loads((DATA / "series" / "coinbase_RENDER-USD_1d.json").read_text())["candles"]
    rndr = json.loads((DATA / "series" / "coinbase_RNDR-USD_1d.json").read_text())["candles"]
    assert render[0]["t"][:10] == "2024-02-15" and rndr[0]["t"][:10] == "2022-02-03"


@needs_data
def test_identity_contracts_match_between_sources():
    ident = json.loads((DATA / "identity.json").read_text())
    assert {t["symbol"] for t in ident["tokens"]} == {"RENDER", "RNDR"}
    assert all(t["coinbase_contract_matches_coingecko"] for t in ident["tokens"])


# ---- reference parity / indicator fixture --------------------------------

import reference_parity as rp  # noqa: E402


def test_indicator_basics():
    closes = [float(i) for i in range(1, 61)]
    rows = rp.indicators(closes)
    assert rows[48]["sma50"] is None and rows[49]["sma50"] == sum(range(1, 51)) / 50
    assert rows[-1]["sma200"] is None
    assert rows[0]["macd"] == 0.0  # both EMAs seeded with the first close
    assert rows[-1]["rsi14"] == 100.0  # only up moves
    assert rows[-1]["macd_hist"] == rows[-1]["macd"] - rows[-1]["macd_signal"]


def test_rma_seeds_with_sma():
    out = rp.rma([1, 2, 3, 4, 5], 3)
    assert out[:2] == [None, None] and out[2] == 2.0 and out[3] == (2.0 * 2 + 4) / 3


@pytest.mark.skipif(not (DATA / "reference_parity.json").exists(), reason="parity file not built")
def test_parity_file_never_publishes_a_joined_sma200_as_render():
    doc = json.loads((DATA / "reference_parity.json").read_text())
    ind = doc["indicators_at_recording_bar"]
    assert ind["coinbase_render_usd_only"]["sma200"] is None
    assert "warning" in ind["comparison_only_rndr_then_render"]
    fixture = doc["indicator_fixture"]["rows"]
    weekly = json.loads((DATA / "weekly" / "coinbase_RENDER-USD_1w.json").read_text())["candles"]
    complete = {c["t"] for c in weekly if c["complete"]}
    times = [r["t"] for r in fixture]
    assert len(fixture) == 100 and times == sorted(times) and set(times) <= complete
