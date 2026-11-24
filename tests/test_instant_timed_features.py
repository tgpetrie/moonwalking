"""Synthetic receipt boundaries and formula oracles for the timed feature row."""

import math

import pytest

from test_instant_input_evidence_review import BTC, COIN, Tape
from instant_timed_features import build_timed_features


CUTOFF = 3810000
FAST = CUTOFF - 30000
SLOW = CUTOFF - 180000
CANDLE_START = FAST - 900000


def feature_tape(*, traded_candles=15, unknown_side=False, tape_type=Tape):
    tape = tape_type(first=CUTOFF, stop=CUTOFF + 5000)
    tape.ack()
    watermark = 10
    for ts in range(100000, CUTOFF + 1, 5000):
        steps = [ts, ts, ts, ts, ts + 180] if ts == CUTOFF else None
        tape.hb(ts, watermark, steps=steps)
        tape.hb(ts, 10, BTC)
        if ts >= FAST:
            # A trade exactly at FAST is used by F2 and excluded by F4.
            if ts <= FAST + 20000 or ts == CUTOFF:
                watermark += 1
                tape.trade(
                    ts,
                    watermark,
                    price="10000" if ts in (FAST, CUTOFF) else "100",
                    size="0.01" if ts == FAST else "1",
                    side=(
                        "unknown"
                        if unknown_side and ts == FAST
                        else "buy" if ts == FAST + 20000 else "sell"
                    ),
                )
        elif ts % 30000 == 0 and (
            ts < CANDLE_START or ts < CANDLE_START + traded_candles * 60000
        ):
            watermark += 1
            tape.trade(
                ts, watermark, price="99" if ts % 60000 == 0 else "101", size="1"
            )

        if ts == CUTOFF:
            # A BBO at b is excluded by endpoints and F3.
            tape.send(ts, "snapshot", bids=[["1000", "1"]], asks=[["1002", "9"]])
            break
        next_cut = ts + 5000
        i = ts // 60000
        coin_mid, btc_mid = 100 + i % 2, 50000 + 100 * (i % 2)
        if next_cut in (SLOW, FAST, CUTOFF):
            coin_mid, btc_mid = {
                SLOW: (101, 50000),
                FAST: (103, 50300),
                CUTOFF: (110, 51000),
            }[next_cut]
        for pid, mid in ((COIN, coin_mid), (BTC, btc_mid)):
            tape.send(
                ts + 1000,
                "snapshot",
                pid,
                bids=[[str(mid - 1), "3"]],
                asks=[[str(mid + 1), "1"]],
            )
    return tape


def features(tape, direction="up", *, asof=CUTOFF + 180):
    return build_timed_features(tape.rec, COIN, CUTOFF, direction, asof=asof)


def test_all_five_formulas_with_direction_and_receipt_boundaries():
    tape = feature_tape()
    row = features(tape)
    down = features(tape, "down")
    vol = row["baseline"]["volatility"]
    sigma = row["sigma_used"]
    median = float(row["baseline"]["pace"]["pace_quote_usd_median_30s"])
    recent, prior = math.log(110 / 103), math.log(103 / 101)
    expected = {
        "F1": (recent - prior / 5) / sigma,
        "F2": 0.6 * math.log1p(500 / median),
        "F3": 0.5,
        "F4": (recent / sigma) / (1 + math.log(101 / 99) / (sigma * math.sqrt(15))),
        "F5": (math.log(110 / 101) - vol["beta"] * math.log(51000 / 50000)) / sigma,
    }
    for name, value in expected.items():
        assert row["features"][name]["value"] == pytest.approx(value)
        assert down["features"][name]["value"] == pytest.approx(
            0 if name == "F4" else -value
        )
    assert row["controls"]["cutoff_spread_bps"] == pytest.approx(2 / 110 * 10000)
    assert row["controls"]["unsigned_activity"]["verified_match_count"] == 5
    assert row["candle_end_ts_ms"] == FAST
    assert row["candle_end_ts_ms"] != row["baseline"]["sigma_end_ts_ms"]
    assert row["features"]["F2"]["evidence_available_ts_ms"] == CUTOFF + 180
    assert row["baseline"]["computation_completed_ts_ms"] == CUTOFF + 180
    assert row["computation_completed_ts_ms"] == CUTOFF + 180
    assert row["later_diagnostic"] is True


def test_late_proof_cannot_rewrite_cutoff_evidence():
    tape = feature_tape()
    before = features(tape, asof=CUTOFF + 1)
    after = features(tape)
    repeated = features(tape, asof=CUTOFF + 1)
    assert before["features"]["F2"]["reason"] == "trade_row_processing_incomplete"
    assert after["features"]["F2"]["status"] == "ready"
    assert before["features"] == repeated["features"]
    assert (
        before["baseline"]["known_packet_prefix_sha256"]
        != after["baseline"]["known_packet_prefix_sha256"]
    )


@pytest.mark.parametrize("traded", [9, 10])
def test_f4_uses_verified_empty_minutes_without_making_up_candles(traded):
    row = features(feature_tape(traded_candles=traded))
    candles = row["controls"]["candle_range"]
    assert candles["traded_candles"] == traded
    assert candles["verified_empty_candles"] == 15 - traded
    if traded == 9:
        assert row["features"]["F4"]["reason"] == "too_few_traded_candles"
    else:
        assert row["features"]["F4"]["status"] == "ready"


def test_unknown_taker_side_keeps_unsigned_evidence():
    row = features(feature_tape(unknown_side=True))
    assert row["features"]["F2"]["reason"] == "unknown_match_side"
    assert row["controls"]["unsigned_activity"]["unknown_side_usd"] == "100.00"
    assert row["controls"]["unsigned_activity"]["verified_match_count"] == 5


@pytest.mark.parametrize("stale", [False, True])
def test_f3_carry_same_millisecond_and_full_window_age(stale):
    cutoff = 60000
    tape = Tape(first=cutoff, stop=cutoff + 5000)
    tape.ack()
    for ts in range(25000, cutoff, 5000):
        tape.hb(ts, 10)
        if ts in (25000, 40000, 50000) or (ts == 35000 and not stale):
            tape.snap(ts)
        if ts == 40000:
            # The final state at 40000 holds for ten seconds, with no weight
            # on the previous snapshot at the same millisecond.
            tape.send(ts, "snapshot", bids=[["99", "1"]], asks=[["101", "3"]])
    tape.now = cutoff
    row = build_timed_features(tape.rec, COIN, cutoff, "up", asof=cutoff)
    f3 = row["features"]["F3"]
    if stale:
        assert f3 == dict(
            status="unavailable", reason="stale_book_span", first_invalid_ts_ms=35000
        )
    else:
        assert f3["value"] == pytest.approx((1 / 3 - 1 / 2 + 1 / 3) / 3)
        assert row["features"]["F4"]["status"] == "unavailable"


def test_f3_detects_a_heartbeat_outage_inside_an_otherwise_fresh_window():
    cutoff = 60000
    tape = Tape(first=cutoff, stop=cutoff + 5000)
    tape.ack()
    for ts in range(25000, cutoff, 5000):
        if ts != 40000:
            tape.hb(ts, 10)
        tape.snap(ts)
    tape.now = cutoff
    row = build_timed_features(tape.rec, COIN, cutoff, "up", asof=cutoff)
    assert row["controls"]["cutoff_spread_bps"] is not None
    assert row["features"]["F3"] == dict(
        status="unavailable",
        reason="stale_heartbeat_span",
        first_invalid_ts_ms=40000,
    )


def test_f3_delayed_payload_only_changes_a_later_evidence_view():
    cutoff = 60000
    tape = Tape(first=cutoff, stop=cutoff + 5000)
    tape.ack()
    for ts in range(25000, cutoff, 5000):
        tape.hb(ts, 10)
        if ts in (25000, 35000, 45000, 50000):
            tape.snap(ts)
    tape.send(
        59000,
        "snapshot",
        steps=[59000, 59000, 59000, 59000, 60100],
        bids=[["99", "1"]],
        asks=[["101", "3"]],
    )
    early = build_timed_features(tape.rec, COIN, cutoff, "up", asof=cutoff)
    late = build_timed_features(tape.rec, COIN, cutoff, "up", asof=60100)
    assert early["features"]["F3"]["value"] == pytest.approx(1 / 3)
    assert late["features"]["F3"]["value"] == pytest.approx((29000 / 3 - 500) / 30000)
    assert late["features"]["F3"]["evidence_available_ts_ms"] == 60100
    assert early["computation_completed_ts_ms"] == 60100
    assert early["later_diagnostic"]
