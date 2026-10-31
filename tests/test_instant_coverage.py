"""Adversarial causal timing, ID completeness, session and offline CLI probes."""

import dataclasses
import gzip
import json
from pathlib import Path
import subprocess
import sys

import pytest

sys.path.insert(
    0, str(Path(__file__).resolve().parents[1] / "scripts/scoring_experiment")
)
from instant_coverage import CoverageMonitor
import instant_coverage
from instant_samples import paired_sample
from instant_targets import TargetEvaluator
from micro_replay import ReplayStore


PID = "TEST-USD"


class Feed:
    def __init__(self, *, products=(PID,), quote="ticker", lag=0):
        self.now = 0
        self.seq = 0
        self.lag = lag
        self.monitor = CoverageMonitor(
            products, quote_channel=quote, clock_ms=lambda: self.now
        )
        self.products = products
        self.quote = quote
        self.events = []

    def send(self, ts, kind, *, pid=PID, connection=1, source="ws", **fields):
        self.seq += 1
        self.now = ts + self.lag
        event = dict(
            receipt_seq=self.seq,
            receipt_ts_ms=ts,
            receipt_monotonic_ns=ts * 1000000,
            connection_id=connection,
            source=source,
            message=dict(type=kind, product_id=pid, **fields),
        )
        self.events.append(event)
        self.monitor.ingest(event)
        return event

    def ack(self, ts, *, products=None, connection=1, channels=None):
        return self.send(
            ts,
            "subscriptions",
            connection=connection,
            channels=(
                channels
                if channels is not None
                else [
                    dict(name=c, product_ids=list(products or self.products))
                    for c in (self.quote, "matches", "heartbeat")
                ]
            ),
        )

    def hb(self, ts, last, **kw):
        return self.send(ts, "heartbeat", last_trade_id=last, **kw)

    def trade(self, ts, tid, **kw):
        return self.send(
            ts, "match", trade_id=tid, price="100", size="2", side="sell", **kw
        )


def check(feed, start=1000, end=2000, asof=2001):
    return feed.monitor.assess(PID, start, end, asof=asof)


def simple(*, lag=0):
    feed = Feed(lag=lag)
    feed.ack(900)
    feed.hb(1000, 10)
    feed.trade(1500, 11)
    feed.hb(2000, 11)
    return feed


def test_actual_proof_time_never_backdates_and_same_ms_receipt_is_excluded():
    feed = simple(lag=100)
    early = check(feed, asof=2000)
    assert early["receipt_id_check_passed"] is False
    assert check(feed, asof=2099) == {**early, "knowledge_asof_ts_ms": 2099}
    later = check(feed, asof=2100)
    assert later["receipt_id_check_passed"] is True
    assert later["receipt_id_check_available_ts_ms"] == 2100
    assert check(feed, asof=2000) == early
    no_lag = simple()
    assert not check(no_lag, asof=2000)["receipt_id_check_passed"]
    assert check(no_lag)["receipt_id_check_available_ts_ms"] == 2001


def test_connection_health_is_not_completeness_or_quote_proof():
    feed = Feed()
    feed.ack(900)
    feed.hb(1000, 10)
    feed.hb(2000, 11)  # Missing execution even though the transport is alive.
    result = check(feed)
    assert result["transport_observed_ok"]
    assert result["receipt_id_check_reason"] == "missing_live_match_ids"
    assert not result["quote_coverage_verified"]


def test_healthy_no_trade_intervals_can_be_verified_without_fake_trades():
    feed = Feed()
    feed.ack(900)
    feed.hb(1000, 10)
    feed.hb(2000, 10)
    feed.hb(3000, 10)
    assert check(feed, end=3000, asof=3001)["receipt_id_check_passed"]
    assert feed.monitor.proofs[0]["observed_unique_trade_count"] == 0
    assert not check(feed, start=999, asof=3001)["receipt_id_check_passed"]


@pytest.mark.parametrize(
    "kind,source",
    [
        ("last_match", "ws"),
        ("ticker", "ws"),
        ("match", "rest"),
        ("match", "rest_recovery"),
    ],
)
def test_non_live_executions_never_repair_missing_ids(kind, source):
    feed = Feed()
    feed.ack(900)
    feed.hb(1000, 10)
    feed.send(
        1500,
        kind,
        source=source,
        trade_id=11,
        price="100",
        size="2",
        side="sell",
        last_size="9999",
    )
    feed.hb(2000, 11)
    assert check(feed)["receipt_id_check_reason"] == "missing_live_match_ids"
    assert not feed.monitor.seen


def test_duplicate_decimal_representation_is_not_a_second_trade():
    feed = simple()
    feed.send(2100, "match", trade_id=11, price="100.00", size="2.0", side="sell")
    feed.hb(3000, 11)
    assert len(feed.monitor.seen) == 1
    assert check(feed, end=3000, asof=3001)["receipt_id_check_passed"]


def test_conflicting_duplicate_vetoes_only_when_the_conflict_is_known():
    feed = simple()
    original = check(feed)
    feed.send(2100, "match", trade_id=11, price="100.01", size="2", side="sell")
    assert check(feed, asof=2100)["receipt_id_check_passed"]
    assert check(feed, asof=2101)["receipt_id_check_reason"] == "conflicting_trade_id"
    assert check(feed) == original


def test_late_match_does_not_repair_old_coverage_or_its_own_receipt_interval():
    feed = Feed()
    feed.ack(900)
    feed.hb(1000, 10)
    feed.hb(2000, 11)
    old = check(feed)
    feed.trade(2100, 11)
    feed.hb(3000, 11)
    assert check(feed, asof=3001)["receipt_id_check_reason"] == "missing_live_match_ids"
    assert (
        check(feed, start=2000, end=3000, asof=3001)["receipt_id_check_reason"]
        == "receipt_ids_outside_watermarks"
    )
    assert check(feed) == old


@pytest.mark.parametrize("when", [1000, 2000])
def test_receipt_boundary_ambiguity_is_not_hidden_by_heartbeat_sequence(when):
    feed = Feed()
    feed.ack(900)
    if when == 1000:
        feed.trade(1000, 10)  # Received before the lower HB at the same ms.
        feed.hb(1000, 10)
        feed.hb(2000, 10)
    else:
        feed.hb(1000, 10)
        feed.trade(2000, 11)  # Excluded from [1000,2000), even before the HB.
        feed.hb(2000, 11)
    assert not check(feed)["receipt_id_check_passed"]


@pytest.mark.parametrize(
    "cause", ["heartbeat_gap", "watermark_regression", "id_span_bound"]
)
def test_bad_heartbeat_pairs_are_bounded_and_fresh_pairs_can_resume(cause):
    feed = Feed()
    feed.ack(900)
    feed.hb(1000, 10)
    end = 7000 if cause == "heartbeat_gap" else 2000
    last = {"heartbeat_gap": 10, "watermark_regression": 9, "id_span_bound": 100011}[
        cause
    ]
    feed.hb(end, last)
    assert check(feed, end=end, asof=end + 1)["receipt_id_check_reason"] == cause
    feed.hb(end + 1000, last)
    assert check(feed, start=end, end=end + 1000, asof=end + 1001)[
        "receipt_id_check_passed"
    ]


def test_missing_subscription_is_per_product_and_full_ack_replaces_membership():
    feed = Feed(products=(PID, "BTC-USD"))
    feed.ack(900, products=("BTC-USD",))
    feed.hb(1000, 10)
    feed.hb(2000, 10)
    assert check(feed)["transport_reason"] == "subscription_unconfirmed"
    assert not feed.monitor.proofs
    feed.ack(2100)
    feed.hb(2200, 10)
    feed.ack(2300, products=("BTC-USD",))
    feed.ack(2400)
    feed.hb(2500, 10)
    assert not feed.monitor.proofs  # No bridge through the lost subscription.
    feed.hb(3000, 10)
    assert check(feed, start=2500, end=3000, asof=3001)["receipt_id_check_passed"]
    assert not check(feed, start=2200, end=3000, asof=3001)["receipt_id_check_passed"]


@pytest.mark.parametrize("kind", ["connection_closed", "error", "queue_overflow"])
def test_disconnect_or_queue_failure_requires_new_ack_and_watermark(kind):
    feed = simple()
    old = check(feed)
    feed.send(2100, kind)
    assert check(feed, asof=2101)["transport_reason"] == kind
    feed.hb(2200, 11)
    assert len(feed.monitor.proofs) == 1
    feed.ack(2300)
    feed.hb(2400, 11)
    feed.hb(3000, 11)
    assert check(feed, start=2400, end=3000, asof=3001)["receipt_id_check_passed"]
    assert check(feed) == old


def test_connection_change_without_close_never_reuses_old_ack_or_watermark():
    feed = simple()
    feed.hb(2100, 11, connection=2)
    assert check(feed, asof=2101)["transport_reason"] == "subscription_unconfirmed"
    feed.ack(2200, connection=2)
    feed.hb(2300, 11, connection=2)
    feed.hb(3000, 11, connection=2)
    assert not check(feed, end=3000, asof=3001)["receipt_id_check_passed"]
    assert check(feed, start=2300, end=3000, asof=3001)["receipt_id_check_passed"]


@pytest.mark.parametrize(
    "fault",
    [
        "seq",
        "wall",
        "mono",
        "missing_mono",
        "processing",
        "future_receipt",
        "source",
        "amount",
    ],
)
def test_invalid_logger_or_clock_fails_the_artifact_closed(fault):
    feed = simple()
    feed.now = 2100
    event = dict(
        receipt_seq=5,
        receipt_ts_ms=2100,
        receipt_monotonic_ns=2100000000,
        connection_id=1,
        message=dict(type="match", product_id=PID, trade_id=12, price="100", size="1"),
    )
    if fault == "seq":
        event["receipt_seq"] = 6
    if fault == "wall":
        event["receipt_ts_ms"] = 1999
    if fault == "mono":
        event["receipt_monotonic_ns"] = 0
    if fault == "missing_mono":
        event.pop("receipt_monotonic_ns")
    if fault == "processing":
        feed.now = 1999
    if fault == "future_receipt":
        event["receipt_ts_ms"] = 2101
    if fault == "source":
        event["source"] = "maybe_ws"
    if fault == "amount":
        event["message"]["price"] = "NaN"
    with pytest.raises((ValueError, KeyError)):
        feed.monitor.ingest(event)
    with pytest.raises(ValueError, match="failed monitor"):
        check(feed)


def test_heartbeat_liveness_expires_without_claiming_historical_trade_loss():
    feed = simple()
    result = check(feed, asof=7001)
    assert result["receipt_id_check_passed"]
    assert result["transport_reason"] == "stale_heartbeat"


def test_same_timestamp_heartbeat_cannot_erase_the_old_watermark():
    feed = Feed()
    feed.ack(900)
    feed.hb(1000, 10)
    feed.hb(1000, 11)
    feed.hb(2000, 11)
    assert check(feed)["receipt_id_check_reason"] == "missing_live_match_ids"


def test_book_subscription_does_not_fabricate_book_quality():
    feed = Feed(quote="level2_batch")
    feed.ack(900)
    feed.hb(1000, 10)
    feed.hb(2000, 10)
    assert check(feed)["receipt_id_check_passed"]
    assert not check(feed)["quote_coverage_verified"]
    assert not check(feed)["full_feed_verified"]


def test_availability_uses_completion_not_the_start_of_processing():
    feed = simple()
    clock = iter((3000, 3500))
    feed.monitor.clock_ms = lambda: next(clock)
    feed.hb(3000, 11)
    assert not check(feed, end=3000, asof=3499)["receipt_id_check_passed"]
    assert check(feed, end=3000, asof=3500)["receipt_id_check_available_ts_ms"] == 3500


def test_packet_bound_never_accepts_a_truncated_prefix(monkeypatch):
    feed = simple()
    monkeypatch.setattr(instant_coverage, "MAX_PACKETS", 4)
    with pytest.raises(ValueError, match="packet bound"):
        feed.hb(3000, 11)
    with pytest.raises(ValueError, match="failed monitor"):
        check(feed)


def test_mid_processing_clock_regression_fails_closed():
    feed = simple()
    clock = iter((3000, 2999))
    feed.monitor.clock_ms = lambda: next(clock)
    with pytest.raises(ValueError, match="completion clock"):
        feed.hb(3000, 11)
    with pytest.raises(ValueError, match="failed monitor"):
        check(feed)


def test_cli_is_offline_preserves_source_and_uses_real_processing_time(tmp_path):
    feed = simple()
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    source = source_dir / "ws.jsonl.gz"
    with gzip.open(source, "wt", encoding="utf-8") as stream:
        for event in feed.events:
            stream.write(json.dumps(event) + "\n")
    before = source.read_bytes()
    script = (
        Path(__file__).resolve().parents[1]
        / "scripts/scoring_experiment/instant_coverage.py"
    )
    output = tmp_path / "new-result"
    command = [
        sys.executable,
        str(script),
        str(source),
        "--products",
        PID,
        "--out-dir",
        str(output),
    ]
    result = subprocess.run(command, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    report = json.loads((output / "REPORT.json").read_text())
    assert report["packet_count"] == 4 and report["unique_ws_matches"] == 1
    assert report["verified_proofs"] == 1 and not report["feed_gate_pass"]
    assert report["first_proof_available_ts_ms"] > 1000000
    assert source.read_bytes() == before
    assert subprocess.run(command, capture_output=True).returncode != 0
    bad = command[:-1] + [str(source_dir / "inside")]
    assert subprocess.run(bad, capture_output=True).returncode != 0
    assert not (source_dir / "inside").exists()


def test_paired_samples_are_immutable_keep_real_zero_and_exact_boundary_counts(
    tmp_path,
):
    store = ReplayStore(tmp_path / "sample.sqlite", create=True)
    try:
        feed = Feed(products=(PID, "BTC-USD"))
        for product in (PID, "BTC-USD"):
            feed.send(100001, "ticker", pid=product, best_bid="99", best_ask="101")
        feed.trade(105000, 11)
        for event in feed.events:
            store.ingest(event)
        for product in (PID, "BTC-USD"):
            store.add_health(
                product=product,
                start=100000,
                end=110000,
                available=110000,
                verified=True,
                evidence="synthetic timely assertion",
            )
        store.finalize()
        early = paired_sample(store, PID, 105000)
        assert (
            early.sample is None
            and "coin:unverified_coverage" in early.unavailable_reasons
        )
        row = paired_sample(store, PID, 110000)
        assert (
            row.sample.trade_count == 1 and row.sample.trade_count_at_bucket_start == 1
        )
        assert row.sample.quote_ts_ms == 100001
        zero = paired_sample(store, "BTC-USD", 110000)
        assert zero.sample.trade_count == 0 and zero.sample.quote_volume_usd == 0
        with pytest.raises(dataclasses.FrozenInstanceError):
            row.sample.ts_ms = 115000
        with pytest.raises(dataclasses.FrozenInstanceError):
            row.ts_ms = 115000
        assert TargetEvaluator([row.sample]).rows[110000] == row.sample
        assert paired_sample(store, PID, 105000) == early
        assert (
            len(row.producer_recorder_sha256) == len(row.input_provenance_sha256) == 64
        )
    finally:
        store.close()


@pytest.mark.parametrize(
    "fault", ["stale_coin", "stale_btc", "missing_btc", "late_health", "invalid_quote"]
)
def test_paired_sample_never_falls_back_to_last_trade_or_later_audit(tmp_path, fault):
    store = ReplayStore(tmp_path / "unavailable.sqlite", create=True)
    try:
        feed = Feed()
        if fault == "stale_coin":
            feed.send(90000, "ticker", best_bid=99, best_ask=101)
        if fault == "stale_btc":
            feed.send(90000, "ticker", pid="BTC-USD", best_bid=99, best_ask=101)
        if fault not in ("missing_btc", "stale_btc"):
            feed.send(109000, "ticker", pid="BTC-USD", best_bid=99, best_ask=101)
        if fault != "stale_coin":
            feed.send(
                109001,
                "ticker",
                best_bid=102 if fault == "invalid_quote" else 99,
                best_ask=101,
            )
        feed.trade(109999, 11)  # A fresh execution never substitutes for missing L1.
        for event in feed.events:
            store.ingest(event)
        for product in (PID, "BTC-USD"):
            store.add_health(
                product=product,
                start=85000,
                end=110000,
                available=110001 if fault == "late_health" else 110000,
                verified=True,
                evidence="synthetic",
            )
        store.finalize()
        result = paired_sample(store, PID, 110000)
        assert result.sample is None and result.unavailable_reasons
        if fault == "late_health":
            assert store.snapshot(PID, 110000, asof=110001)["mid"] == 100
            assert paired_sample(store, PID, 110000) == result
    finally:
        store.close()


def test_unknown_side_does_not_hide_an_otherwise_valid_target_sample(tmp_path):
    store = ReplayStore(tmp_path / "side.sqlite", create=True)
    try:
        feed = Feed()
        for product in (PID, "BTC-USD"):
            feed.send(109000, "ticker", pid=product, best_bid=99, best_ask=101)
        feed.send(109001, "match", trade_id=11, price=100, size=2, side="unknown")
        for event in feed.events:
            store.ingest(event)
        for product in (PID, "BTC-USD"):
            store.add_health(
                product=product,
                start=100000,
                end=110000,
                available=110000,
                verified=True,
                evidence="synthetic",
            )
        store.finalize()
        result = paired_sample(store, PID, 110000)
        assert result.sample.trade_count == 1 and result.sample.quote_volume_usd == 200
        assert result.coin_flow_available is False
        assert not result.unavailable_reasons
    finally:
        store.close()
