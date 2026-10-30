"""Offline receipt boundaries, immutable knowledge times, gaps and baseline windows."""

import hashlib
import json
import math
from pathlib import Path
import statistics
import subprocess
import sys

import pytest

sys.path.insert(
    0, str(Path(__file__).resolve().parents[1] / "scripts/scoring_experiment")
)
from micro_replay import ReplayStore
from micro_baseline import build_baseline


PID = "TEST-USD"


def packet(seq, ts, kind="ticker", **fields):
    defaults = (
        {"best_bid": 99, "best_ask": 101, "best_bid_size": 2, "best_ask_size": 1}
        if kind == "ticker"
        else {"trade_id": seq, "price": 100, "size": 2, "side": "sell"}
    )
    return dict(
        receipt_seq=seq,
        receipt_ts_ms=ts,
        receipt_monotonic_ns=ts * 1000000,
        connection_id=1,
        message={**defaults, "type": kind, "product_id": PID, **fields},
    )


def health(store, start=100000, end=110000, available=None, product=PID, verified=True):
    store.add_health(
        product=product,
        start=start,
        end=end,
        available=end if available is None else available,
        verified=verified,
        evidence="explicit synthetic interval assertion",
    )


@pytest.fixture
def store(tmp_path):
    value = ReplayStore(tmp_path / "offline.sqlite", create=True)
    yield value
    value.close()


def test_sparse_healthy_empty_bucket_keeps_quote_age_without_inventing_ohlc(store):
    store.ingest(packet(1, 100001))
    health(store)
    store.finalize()
    snapshot = store.snapshot(PID, 110000)
    assert snapshot["trade_count"] == 0 and snapshot["mid"] == 100
    assert snapshot["quote_ts_ms"] == 100001 and snapshot["quote_observed"] is False
    assert snapshot["observed_mid_ohlc"] is None
    assert store.db.execute("SELECT COUNT(*) FROM micro_bars_5s").fetchone()[0] == 1


def test_later_coverage_does_not_rewrite_what_was_known_earlier(store):
    store.ingest(packet(1, 100001))
    health(store)
    store.finalize()
    old = store.snapshot(PID, 105000)
    retrospective = store.snapshot(PID, 105000, asof=110000)
    assert old["trade_count"] is None and old["mid"] is None
    assert (
        retrospective["trade_count"] == 0 and retrospective["available_ts_ms"] == 110000
    )
    assert store.snapshot(PID, 105000) == old


def test_match_dedup_maker_inversion_reordering_and_receipt_bucket_boundaries(store):
    store.ingest(packet(1, 100500, "match", trade_id=9, side="sell"))
    duplicate = packet(2, 100700, "match", trade_id=9, side="sell")
    duplicate["connection_id"] = 2
    store.ingest(duplicate)
    store.ingest(
        packet(
            3, 105000, "match", trade_id=2, side="buy", size=1, time="old exchange time"
        )
    )
    health(store, 100000, 105000)
    health(store, 105000, 110000)
    store.finalize()
    first = store.snapshot(PID, 105000)
    second = store.snapshot(PID, 110000)
    assert first["trade_count"] == second["trade_count"] == 1
    assert (
        first["trade_count_at_bucket_start"] == 0
        and second["trade_count_at_bucket_start"] == 1
    )
    assert first["taker_buy_usd"] == 200 and first["taker_sell_usd"] == 0
    assert second["taker_sell_usd"] == 100 and second["taker_buy_usd"] == 0


def test_last_match_rest_recovery_and_ticker_last_size_never_add_volume(store):
    for seq, kind in enumerate(("last_match", "match", "ticker"), 1):
        event = packet(seq, 100000 + seq, kind, last_size=9999)
        if kind == "match":
            event["source"] = "rest_recovery"
        store.ingest(event)
    health(store)
    store.finalize()
    snapshot = store.snapshot(PID, 105000, asof=110000)
    assert snapshot["trade_count"] == 0 and snapshot["quote_volume_usd"] == 0
    assert store.db.execute("SELECT COUNT(*) FROM micro_bars_5s").fetchone()[0] == 1


def test_unknown_side_retains_volume_and_marks_signed_flow_unavailable(store):
    store.ingest(packet(1, 100001, "match", side="unknown"))
    health(store)
    store.finalize()
    result = store.snapshot(PID, 105000, asof=110000)
    assert (
        result["trade_count"] == 1
        and result["quote_volume_usd"] == result["unknown_side_usd"] == 200
    )
    assert result["flow_available"] is False


def test_conflicting_trade_is_known_at_conflict_receipt_not_retroactively(store):
    store.ingest(packet(1, 100500, "match", trade_id=9))
    store.ingest(packet(2, 105500, "match", trade_id=9, price=101))
    health(store, 100000, 105000)
    health(store, 105000, 110000)
    store.finalize()
    assert store.snapshot(PID, 105000)["trade_count"] == 1
    later = store.snapshot(PID, 105000, asof=110000)
    assert later["trade_count"] is None and later["available_ts_ms"] == 105500


@pytest.mark.parametrize(
    "change",
    [{"receipt_ts_ms": 99999}, {"receipt_seq": 1}, {"receipt_monotonic_ns": 1}],
)
def test_clock_or_receipt_regression_fails_the_artifact_closed(store, change):
    store.ingest(packet(1, 100000))
    with pytest.raises(ValueError, match="regressed"):
        store.ingest({**packet(2, 100100), **change})
    with pytest.raises(ValueError):
        store.finalize()
    with pytest.raises(ValueError):
        store.snapshot(PID, 105000)


@pytest.mark.parametrize(
    "quote,reason",
    [
        ({"best_bid": 0}, "invalid_quote"),
        ({"best_bid": 102}, "invalid_quote"),
        ({"best_bid": "NaN"}, "invalid_quote"),
        ({"best_bid": True}, "invalid_quote"),
    ],
)
def test_invalid_quotes_never_become_primary_prices(store, quote, reason):
    store.ingest(packet(1, 100001, **quote))
    health(store)
    store.finalize()
    result = store.snapshot(PID, 105000, asof=110000)
    assert result["mid"] is None and result["reason"] == reason


def test_future_quote_is_not_used_and_quote_cannot_cross_a_gap(store):
    store.ingest(packet(1, 100001))
    store.ingest(packet(2, 110001, best_bid=199, best_ask=201))
    health(store, 101000, 115000)
    store.finalize()
    result = store.snapshot(PID, 110000, asof=115000)
    assert result["quote_ts_ms"] == 100001 and result["mid"] is None
    assert result["reason"] == "quote_crossed_unverified_interval"
    assert store.snapshot(PID, 115000)["mid"] == 200


def test_stale_quote_and_missing_sizes_are_explicit(store):
    store.ingest(packet(1, 100001, best_bid_size=None))
    health(store, 100000, 120000)
    store.finalize()
    fresh = store.snapshot(PID, 105000, asof=120000)
    assert fresh["mid"] == 100 and fresh["bbo_size_available"] is False
    assert store.snapshot(PID, 115000, asof=120000)["reason"] == "stale_quote"


def test_negative_interval_vetoes_positive_assertion_when_known(store):
    health(store, 100000, 110000)
    health(store, 105000, 110000, available=115000, verified=False)
    store.finalize()
    assert store.snapshot(PID, 110000)["trade_count"] == 0
    result = store.snapshot(PID, 110000, asof=115000)
    assert result["trade_count"] is None and result["available_ts_ms"] == 115000


def test_existing_output_readonly_and_unfinished_artifact_protection(tmp_path):
    path = tmp_path / "store.sqlite"
    store = ReplayStore(path, create=True)
    with pytest.raises(FileExistsError):
        ReplayStore(path, create=True)
    with pytest.raises(ValueError):
        store.snapshot(PID, 105000)
    with pytest.raises(ValueError):
        health(store, available=100001)
    store.finalize()
    store.close()
    frozen = hashlib.sha256(path.read_bytes()).hexdigest()
    reader = ReplayStore(path)
    assert reader.snapshot(PID, 105000)["trade_count"] is None
    with pytest.raises(ValueError):
        reader.ingest(packet(1, 100001))
    reader.close()
    assert hashlib.sha256(path.read_bytes()).hexdigest() == frozen


def baseline_store(
    tmp_path,
    *,
    missing_quote=False,
    gap=False,
    future_health=False,
    flat_btc=False,
    no_trades=False,
    extra=False
):
    anchor = 7200000
    end = (anchor - 35000) // 60000 * 60000
    start = end - 3600000
    store = ReplayStore(tmp_path / "baseline.sqlite", create=True)
    events = []
    for i, t in enumerate(range(start, end + 1, 60000)):
        for pid, logprice in (
            (PID, 0.0004 * i * i),
            ("BTC-USD", 0 if flat_btc else 0.0002 * i * i),
        ):
            if missing_quote and i == 30 and pid == PID:
                continue
            price = 100 * math.exp(logprice)
            events.append(
                packet(
                    1,
                    t - 1,
                    best_bid=price * 0.9999,
                    best_ask=price * 1.0001,
                    product_id=pid,
                )
            )
    if not no_trades:
        for i, t in enumerate(
            range(anchor - 30000 - 120 * 30000 + 30000, anchor - 30000 + 1, 30000)
        ):
            events.append(packet(1, t - 1, "match", trade_id=i, price=10, size=2))
    if extra:
        events.extend(
            [
                packet(1, anchor - 10000, best_bid=999, best_ask=1001),
                packet(1, anchor + 1, best_bid=9999, best_ask=10001),
            ]
        )
    for seq, event in enumerate(sorted(events, key=lambda x: x["receipt_ts_ms"]), 1):
        store.ingest({**event, "receipt_seq": seq})
    for pid in (PID, "BTC-USD"):
        if gap and pid == PID:
            health(store, start - 5000, start + 30000, available=anchor, product=pid)
            health(store, start + 35000, anchor, available=anchor, product=pid)
        else:
            health(
                store,
                start - 5000,
                anchor,
                available=anchor + int(future_health),
                product=pid,
            )
    store.finalize()
    return store, anchor


def test_baseline_builds_60_closed_returns_and_120_nonoverlapping_pace_windows(
    tmp_path,
):
    store, anchor = baseline_store(tmp_path, extra=True)
    try:
        result = build_baseline(store, PID, anchor)
        assert result["status"] == "ready"
        b = result["baseline"]
        assert b.return_count == 60 and b.pace_window_count == 120
        assert (
            b.end_ts_ms == (anchor - 35000) // 60000 * 60000
            and b.pace_end_ts_ms == anchor - 30000
        )
        assert b.beta == pytest.approx(2, abs=1e-10)
        assert b.sigma_1m == pytest.approx(
            statistics.stdev(0.0004 * (2 * i + 1) for i in range(60))
        )
        assert b.pace_trade_median_30s == 1 and b.pace_quote_usd_median_30s == 20
        assert b.beta_available_ts_ms == b.available_ts_ms == anchor
    finally:
        store.close()


@pytest.mark.parametrize(
    "option,reason",
    [
        ("missing_quote", "baseline_quote_quality"),
        ("gap", "baseline_coverage"),
        ("future_health", "baseline_coverage"),
    ],
)
def test_baseline_never_fills_a_missing_quote_or_bridges_unknown_coverage(
    tmp_path, option, reason
):
    store, anchor = baseline_store(tmp_path, **{option: True})
    try:
        assert build_baseline(store, PID, anchor)["reason"] == reason
    finally:
        store.close()


def test_flat_benchmark_fallback_and_genuine_zero_pace_remain_visible(tmp_path):
    store, anchor = baseline_store(tmp_path, flat_btc=True, no_trades=True)
    try:
        result = build_baseline(store, PID, anchor)
        assert result["status"] == "ready"
        assert result["baseline"].beta_fallback and result["baseline"].beta == 1
        assert result["baseline"].pace_quote_usd_median_30s == 0
    finally:
        store.close()


def test_replay_cli_is_local_only_and_pins_source_hashes(tmp_path):
    packets = tmp_path / "packets.jsonl"
    intervals = tmp_path / "health.json"
    out = tmp_path / "result.sqlite"
    packets.write_text(json.dumps(packet(1, 100001)) + "\n", encoding="utf-8")
    intervals.write_text(
        json.dumps(
            [
                dict(
                    product=PID,
                    start=100000,
                    end=110000,
                    available=110000,
                    verified=True,
                    evidence="synthetic",
                )
            ]
        ),
        encoding="utf-8",
    )
    script = (
        Path(__file__).resolve().parents[1]
        / "scripts/scoring_experiment/micro_replay.py"
    )
    run = subprocess.run(
        [
            sys.executable,
            str(script),
            str(packets),
            "--health",
            str(intervals),
            "--out",
            str(out),
        ],
        capture_output=True,
        text=True,
    )
    assert run.returncode == 0, run.stderr
    assert json.loads(run.stdout)["feed_gate_pass"] is False
    reader = ReplayStore(out)
    try:
        meta = json.loads(
            reader.db.execute(
                "SELECT value FROM meta WHERE key='source_manifest'"
            ).fetchone()[0]
        )
        assert (
            meta["input_sha256"]["packets"]
            == hashlib.sha256(packets.read_bytes()).hexdigest()
        )
    finally:
        reader.close()
