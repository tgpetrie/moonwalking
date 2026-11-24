"""Synthetic ledger cases for baseline evidence timing and window boundaries."""

import math

import pytest

from test_instant_input_evidence_review import BTC, COIN, Tape
from instant_timed_baseline import build_timed_baseline


CUTOFF = 3_780_000
SIGMA_START, SIGMA_END = 120_000, 3_720_000
PACE_START, PACE_END = 150_000, 3_750_000


def history(*, flat_btc=False, missing_btc_close=None, active=True):
    tape = Tape(first=CUTOFF, stop=CUTOFF + 5000)
    tape.ack()
    watermark = 10
    for ts in range(100_000, PACE_END + 5001, 5000):
        steps = [ts, ts, ts, ts, ts + 180] if ts == PACE_END else None
        tape.hb(ts, watermark, steps=steps)
        tape.hb(ts, 10, BTC)
        if active and ts % 30000 == 0 and PACE_START <= ts < PACE_START + 60 * 30000:
            watermark += 1
            tape.trade(ts, watermark)
        if ts == PACE_END:
            # This receipt is just outside the baseline window.
            watermark += 1
            tape.trade(ts, watermark, size="10000")
        close = ts + 5000
        if SIGMA_START <= close <= SIGMA_END and close % 60000 == 0:
            n = (close - SIGMA_START) // 60000
            path = 0.015 * n - 0.005 * (n % 2)
            for pid, mid in (
                (COIN, 100 * math.exp(2 * path)),
                (BTC, 50000 if flat_btc else 50000 * math.exp(path)),
            ):
                if pid == BTC and close == missing_btc_close:
                    continue
                tape.send(
                    close - 1000,
                    "snapshot",
                    pid,
                    bids=[[str(mid * 0.9999), "2"]],
                    asks=[[str(mid * 1.0001), "1"]],
                )
    return tape


def test_timed_baseline_separates_closing_proof_from_computation_time():
    tape = history()
    early = build_timed_baseline(tape.rec, COIN, CUTOFF, asof=PACE_END + 100)
    assert early["volatility"]["return_count"] == 60
    assert early["pace"]["reason"] == "trade_row_processing_incomplete"

    ready = build_timed_baseline(tape.rec, COIN, CUTOFF, asof=PACE_END + 180)
    assert (ready["sigma_start_ts_ms"], ready["sigma_end_ts_ms"]) == (
        SIGMA_START,
        SIGMA_END,
    )
    assert (ready["pace_start_ts_ms"], ready["pace_end_ts_ms"]) == (
        PACE_START,
        PACE_END,
    )
    assert ready["volatility"]["beta"] == pytest.approx(2)
    assert ready["volatility"]["sigma_1m"] == pytest.approx(0.01 * math.sqrt(60 / 59))
    assert ready["pace"] == dict(
        status="ready",
        inputs_available_ts_ms=PACE_END + 180,
        window_count=120,
        pace_trade_median_30s=0.5,
        pace_quote_usd_median_30s="100",
    )
    assert ready["computation_completed_ts_ms"] == PACE_END + 5000
    assert early["known_packet_prefix_sha256"] != ready["known_packet_prefix_sha256"]

    # Later computation with the same evidence limit retains the same inputs.
    tape.hb(CUTOFF + 5000, 10, BTC)
    late = build_timed_baseline(tape.rec, COIN, CUTOFF, asof=PACE_END + 180)
    assert late["computation_completed_ts_ms"] == CUTOFF + 5000
    assert late["known_packet_prefix_sha256"] == ready["known_packet_prefix_sha256"]
    assert late["volatility"] == ready["volatility"] and late["pace"] == ready["pace"]


def test_missing_benchmark_close_does_not_discard_verified_activity():
    tape = history(missing_btc_close=SIGMA_START + 60000)
    result = build_timed_baseline(tape.rec, COIN, CUTOFF, asof=PACE_END + 180)
    assert result["volatility"] == dict(
        status="unavailable",
        reason="stale_book_observation",
        product_id=BTC,
        missing_close_ts_ms=SIGMA_START + 60000,
    )
    assert result["pace"]["status"] == "ready"


def test_flat_benchmark_fallback_and_proven_empty_pace():
    tape = history(flat_btc=True, active=False)
    result = build_timed_baseline(tape.rec, COIN, CUTOFF, asof=PACE_END + 180)
    assert result["volatility"]["beta"] == 1
    assert result["volatility"]["beta_fallback"] is True
    assert result["pace"]["pace_trade_median_30s"] == 0
    assert result["pace"]["pace_quote_usd_median_30s"] == "0"


def test_elapsed_time_alone_cannot_supply_baseline_evidence():
    tape = Tape(first=CUTOFF, stop=CUTOFF + 5000)
    tape.now = CUTOFF
    result = build_timed_baseline(tape.rec, COIN, CUTOFF, asof=CUTOFF)
    for component in (result["volatility"], result["pace"]):
        assert component["status"] == "unavailable"
        assert component["reason"] == "trade_coverage_not_yet_proven"
        assert "inputs_available_ts_ms" not in component


def test_baseline_rejects_evidence_time_before_inventory_or_after_actual_clock():
    tape = Tape(first=CUTOFF, stop=CUTOFF + 5000, start_clock=1000)
    with pytest.raises(ValueError, match="inventory was not yet recorded"):
        build_timed_baseline(tape.rec, COIN, CUTOFF, asof=999)
    with pytest.raises(ValueError, match="evidence time has not been reached"):
        build_timed_baseline(tape.rec, COIN, CUTOFF, asof=1001)
