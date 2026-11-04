"""Planned-row accounting, measured pipeline completion and scoped evidence."""

from dataclasses import FrozenInstanceError
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest

from test_instant_book import PID
from instant_input_evidence import InputEvidenceRecorder
import instant_input_evidence as evidence


BTC = "BTC-USD"


class Clock:
    def __init__(self):
        self.now = 0
        self.steps = []

    def __call__(self):
        if self.steps:
            self.now = self.steps.pop(0)
        return self.now


class Feed:
    def __init__(self, first=30000, stop=40000):
        self.clock = Clock()
        self.recorder = InputEvidenceRecorder(
            (PID, BTC), first, stop, clock_ms=self.clock
        )
        self.seq = 0
        self.events = []
        self.ids = {PID: 10, BTC: 10}

    def send(self, ts, kind, pid=PID, lag=0, **fields):
        self.clock.now = ts + lag
        self.seq += 1
        event = dict(
            receipt_seq=self.seq,
            receipt_ts_ms=ts,
            receipt_monotonic_ns=ts * 1000000,
            connection_id=1,
            message=dict(type=kind, product_id=pid, **fields),
        )
        self.events.append(event)
        self.recorder.ingest(event)
        return event

    def ack(self, products=(PID, BTC)):
        self.send(
            0,
            "subscriptions",
            channels=[
                dict(name=c, product_ids=list(products))
                for c in ("matches", "heartbeat", "level2_batch")
            ],
        )

    def hb(self, ts, pid=PID):
        self.send(ts, "heartbeat", pid, last_trade_id=self.ids[pid])

    def snapshot(self, ts, pid=PID, **kw):
        self.send(ts, "snapshot", pid, bids=[["99", "2"]], asks=[["101", "1"]], **kw)

    def trade(self, ts, pid=PID, side="sell", **kw):
        self.ids[pid] += 1
        return self.send(
            ts,
            "match",
            pid,
            trade_id=self.ids[pid],
            price="100",
            size="2",
            side=side,
            **kw,
        )


def ready(*, side=None):
    feed = Feed()
    feed.ack()
    for p in (PID, BTC):
        feed.hb(0, p)
    for p in (PID, BTC):
        feed.snapshot(10, p)
    for ts in range(1000, 30001, 1000):
        if ts == 1000 and side is not None:
            feed.trade(500, side=side)
        if ts == 26000:
            for p in (PID, BTC):
                feed.snapshot(25500, p)
        for p in (PID, BTC):
            feed.hb(ts, p)
    feed.clock.now = 30001
    return feed


def test_inventory_accounts_for_products_directions_and_every_cutoff_without_packets():
    f = Feed()
    f.clock.now = 35000
    report = f.recorder.seal()
    assert report["expected_rows"] == report["recorded_rows"] == 8
    assert {
        (r["product_id"], r["direction"], r["cutoff_ts_ms"]) for r in report["rows"]
    } == {(p, d, t) for p in (PID, BTC) for d in ("up", "down") for t in (30000, 35000)}
    assert report["packet_count"] == 0
    assert all(
        r["eligibility_status"] == "unavailable" and not r["study_eligible"]
        for r in report["rows"]
    )
    assert all(
        "baseline_evidence_not_implemented" in r["unavailable_reasons"]
        for r in report["rows"]
    )


def test_a_missing_product_is_retained_in_both_boards():
    f = Feed()
    f.ack((BTC,))
    f.hb(1000, BTC)
    f.snapshot(2000, BTC)
    f.clock.now = 30000
    rows = f.recorder.checkpoint(30000)
    missing = [r.to_dict() for r in rows if r.product_id == PID]
    assert len(missing) == 2
    assert all(r["components"]["coin"]["quote"]["available"] is False for r in missing)


def test_processing_completion_is_measured_after_book_and_trade_construction():
    f = Feed()
    f.ack()
    # Producer start, monitor start, monitor finish, book finish, producer finish.
    f.clock.steps = [100, 101, 102, 103, 110]
    f.trade(100)
    packet, trade = f.recorder.packets[-1], f.recorder.trades[-1]
    assert packet.processing_started_ts_ms == 100
    assert packet.processing_completed_ts_ms == trade.available_ts_ms == 110
    assert packet.available_ts_ms > packet.receipt_ts_ms
    assert f.recorder.book.completed[packet.receipt_seq] == 103
    with pytest.raises(FrozenInstanceError):
        trade.available_ts_ms = 100


def test_healthy_empty_is_zero_only_after_proof_completion_not_at_cutoff():
    f = ready()
    early = f.recorder.component_evidence(PID, 30000)
    later = f.recorder.component_evidence(PID, 30000, asof=30001)
    assert early["trades_30s"]["verified_trade_count"] is None
    assert later["trades_30s"]["verified_trade_count"] == 0
    assert later["trades_30s"]["quote_volume_usd"] == "0"
    assert later["later_diagnostic"] is True
    assert later["knowledge_asof_ts_ms"] == 30001
    assert later["full_feed_verified"] is False
    assert later["interval_quote_continuity_verified"] is False


@pytest.mark.parametrize(
    "side,expected_buy,expected_sell", [("sell", "200", "0"), ("buy", "0", "200")]
)
def test_match_maker_side_is_inverted_with_exact_decimal_amounts(
    side, expected_buy, expected_sell
):
    f = ready(side=side)
    view = f.recorder.component_evidence(PID, 30000, asof=30001)["trades_30s"]
    assert view["verified_trade_count"] == 1
    assert view["quote_volume_usd"] == "200"
    assert (view["taker_buy_usd"], view["taker_sell_usd"]) == (
        expected_buy,
        expected_sell,
    )
    assert view["flow_available"] is True


def test_unknown_side_keeps_verified_count_but_signed_flow_unavailable():
    f = ready(side="unknown")
    view = f.recorder.component_evidence(PID, 30000, asof=30001)["trades_30s"]
    assert view["verified_trade_count"] == 1
    assert view["unknown_side_usd"] == "200"
    assert view["flow_available"] is False


def test_later_evidence_and_caller_mutation_cannot_rewrite_frozen_cohort():
    f = ready()
    cohort = f.recorder.checkpoint(30000)
    before = [r.to_dict() for r in cohort]
    f.send(30002, "audit_transport_error")
    assert f.recorder.checkpoint(30000) is cohort
    assert [r.to_dict() for r in cohort] == before
    edited = cohort[0].to_dict()
    edited["components"]["coin"]["quote"]["available"] = "forged"
    assert [r.to_dict() for r in cohort] == before
    assert all(
        "assessment_completed_after_cutoff" in r.unavailable_reasons for r in cohort
    )
    assert all(
        r.to_dict()["components"]["coin"]["trades_30s"]["verified_trade_count"] is None
        for r in cohort
    )


def test_assessment_completion_is_measured_and_not_labelled_as_input_availability():
    f = ready()
    f.clock.steps = [30001, 30020]
    cohort = f.recorder.checkpoint(30000)
    assert all(r.assessment_completed_ts_ms == 30020 for r in cohort)
    assert all(
        r.to_dict()["components"]["coin"]["knowledge_asof_ts_ms"] == 30000
        for r in cohort
    )


def test_receipt_at_cutoff_is_excluded_and_row_completion_cannot_be_backdated():
    f = ready()
    f.trade(30000)
    f.clock.now = 30001
    assert (
        f.recorder.component_evidence(PID, 30000, asof=30001)["trades_30s"][
            "known_unique_match_count"
        ]
        == 0
    )


def test_lost_id_is_not_converted_to_zero():
    f = ready()
    # The following window includes an undelivered ID and no book refresh.
    f.ids[PID] += 1
    f.hb(31000)
    f.hb(35000)
    f.clock.now = 35001
    view = f.recorder.component_evidence(PID, 35000, asof=35001)
    assert view["trades_30s"]["verified_trade_count"] is None
    assert view["trades_30s"]["quote_volume_usd"] is None


def test_source_ticker_and_rest_do_not_create_trade_rows():
    f = Feed()
    event = f.send(100, "ticker", last_size="1000", best_bid="99", best_ask="101")
    event["message"]["last_size"] = "forged"
    f.send(200, "last_match", trade_id=11, price="100", size="2", side="sell")
    f.clock.now = 300
    f.seq += 1
    recovery = dict(
        receipt_seq=f.seq,
        receipt_ts_ms=300,
        receipt_monotonic_ns=300000000,
        connection_id=1,
        source="rest_recovery",
        message=dict(type="match", product_id=PID, trade_id=12, price="100", size="2"),
    )
    f.recorder.ingest(recovery)
    assert len(f.recorder.packets) == 3 and not f.recorder.trades
    assert (
        f.recorder.packets[0].envelope_sha256
        != hashlib.sha256(evidence._json(event).encode()).hexdigest()
    )


def test_first_receipt_deduplication_and_conflicts_preserve_original_processing():
    f = ready(side="sell")
    original = f.recorder.trades[0]
    f.send(30001, "match", trade_id=11, price="100.0", size="2.0", side="sell")
    f.send(30002, "match", trade_id=11, price="101", size="2", side="sell")
    assert f.recorder.trades == [original]
    f.clock.now = 30003
    assert (
        f.recorder.component_evidence(PID, 30000, asof=30003)["trades_30s"]["reason"]
        == "conflicting_trade_id"
    )


def test_quote_age_is_not_refreshed_by_heartbeat_and_benchmark_is_separate():
    f = ready()
    f.hb(35000)
    f.hb(35000, BTC)
    f.clock.now = 35001
    # Last snapshot was 25,500. At 35,000 it is still inside the 10s TTL.
    assert (
        f.recorder.component_evidence(PID, 35000, asof=35001)["quote"][
            "observation_age_ms"
        ]
        == 9500
    )
    f.send(35001, "l2update", BTC, changes=[["sell", "101", "0"], ["sell", "102", "0"]])
    f.clock.now = 35002
    assert (
        f.recorder.component_evidence(BTC, 35000, asof=35002)["quote"]["available"]
        is True
    )  # update at/after cutoff excluded


@pytest.mark.parametrize("change", ["sequence", "clock", "packet_bound"])
def test_failed_or_truncated_tapes_cannot_be_reported_or_sealed(change, monkeypatch):
    f = Feed()
    f.ack()
    if change == "sequence":
        f.seq += 1
    elif change == "clock":
        f.clock.steps = [-1]
    else:
        import instant_coverage

        monkeypatch.setattr(instant_coverage, "MAX_PACKETS", 1)
    with pytest.raises(ValueError):
        f.hb(1000)
    with pytest.raises(ValueError):
        f.recorder.seal()
    with pytest.raises(ValueError):
        f.recorder.report()


@pytest.mark.parametrize(
    "products,start,stop",
    [
        ((PID,), 30000, 35000),
        ((PID, BTC, PID), 30000, 35000),
        ((PID, BTC), 30001, 35000),
        ((PID, BTC), 30000, 30000),
        ((PID, BTC), True, 35000),
        ((PID, BTC), 30000, 30000 + 5000 * 3000),
    ],
)
def test_invalid_inventory_is_rejected_before_consuming_packets(products, start, stop):
    with pytest.raises(ValueError):
        InputEvidenceRecorder(products, start, stop)


def test_seal_requires_last_cutoff_and_then_refuses_more_writes():
    f = Feed()
    f.clock.now = 34999
    with pytest.raises(ValueError, match="all declared cutoffs"):
        f.recorder.seal()
    f.clock.now = 35000
    f.recorder.seal()
    with pytest.raises(ValueError, match="sealed"):
        f.hb(36000)


def test_historical_replay_uses_now_and_does_not_claim_predeclaration():
    recorder = InputEvidenceRecorder(
        (PID, BTC), 30000, 35000, clock_ms=lambda: 10_000_000
    )
    report = recorder.seal()
    assert report["inventory_precedes_first_cutoff"] is False
    assert all(
        "inventory_recorded_after_first_cutoff" in r["unavailable_reasons"]
        for r in report["rows"]
    )
    assert report["directional_report_adapter_supported"] is False


def test_quote_processing_after_cutoff_does_not_inherit_earlier_book_completion():
    f = Feed()
    f.ack()
    f.hb(29000)
    f.clock.steps = [29999, 29999, 29999, 29999, 30001]
    f.snapshot(29999)
    assert f.recorder.book.view(PID, 30000).book_state_available
    early = f.recorder.component_evidence(PID, 30000)
    assert early["quote"]["available"] is False
    assert early["quote"]["bid"] is None
    assert early["quote"]["reason"] == "quote_row_processing_incomplete"
    later = f.recorder.component_evidence(PID, 30000, asof=30001)
    assert later["quote"]["available"] is True


def test_query_clock_regression_fails_the_artifact_closed():
    f = ready()
    f.clock.now = 29999
    with pytest.raises(ValueError, match="clock regressed"):
        f.recorder.component_evidence(PID, 30000)
    f.clock.now = 35000
    with pytest.raises(ValueError, match="failed"):
        f.recorder.seal()


def test_missing_benchmark_does_not_inherit_the_coins_fresh_book():
    f = Feed()
    f.ack((PID,))
    f.hb(29000)
    f.snapshot(29500)
    f.clock.now = 30000
    row = next(r.to_dict() for r in f.recorder.checkpoint(30000) if r.product_id == PID)
    assert row["components"]["coin"]["quote"]["available"] is True
    assert row["components"]["benchmark"]["quote"]["available"] is False
    assert any(
        reason.startswith("benchmark:quote:") for reason in row["unavailable_reasons"]
    )


def test_stale_quotes_do_not_get_the_heartbeat_timestamp():
    f = Feed()
    f.ack()
    f.snapshot(1000)
    f.hb(1000)
    for ts in range(5000, 30001, 5000):
        f.hb(ts)
    f.clock.now = 30001
    view = f.recorder.component_evidence(PID, 30000, asof=30001)
    assert view["quote"]["available"] is False
    assert view["quote"]["reason"] == "stale_book_observation"
    assert view["quote"]["observation_ts_ms"] == 1000


def test_unplanned_or_unreached_cutoffs_and_future_diagnostics_are_rejected():
    f = ready()
    with pytest.raises(ValueError, match="outside declared"):
        f.recorder.checkpoint(40000)
    with pytest.raises(ValueError, match="knowledge must be reached"):
        f.recorder.component_evidence(PID, 30000, asof=40000)
    with pytest.raises(ValueError, match="cutoff has not been reached"):
        f.recorder.checkpoint(35000)


def test_receipt_at_an_epoch_boundary_is_not_certified_by_the_next_epoch():
    f = Feed()
    f.ack()
    f.hb(0)
    f.trade(0)  # Actual first receipt stays at 0, before the failure.
    f.send(0, "audit_parse_error")
    f.ack()
    f.ids[PID] = 10
    f.hb(0)
    f.hb(0, BTC)
    for p in (PID, BTC):
        f.snapshot(1, p)
    for ts in range(1000, 30001, 1000):
        if ts == 26000:
            for p in (PID, BTC):
                f.snapshot(25500, p)
        for p in (PID, BTC):
            f.hb(ts, p)
    f.clock.now = 30001
    component = f.recorder.component_evidence(PID, 30000, asof=30001)["trades_30s"]
    assert component["known_unique_match_count"] == 1  # No receipt reassignment.
    assert component["verified_trade_count"] is None
    assert component["reason"] == "trade_row_continuity_mismatch"


def test_cli_round_trip_retains_planned_rows_and_processing_ledgers(tmp_path):
    source = tmp_path / "input" / "packets.jsonl.gz"
    source.parent.mkdir()
    f = Feed(stop=35000)
    f.ack()
    f.trade(100)
    with gzip.open(source, "wt", encoding="utf-8") as stream:
        for event in f.events:
            stream.write(json.dumps(event) + "\n")
    plan = source.parent / "inventory.json"
    plan.write_text(
        json.dumps(dict(products=[PID, BTC], first_cutoff=30000, stop_cutoff=35000)),
        encoding="utf-8",
    )
    output = tmp_path / "output"
    before = source.read_bytes(), plan.read_bytes()
    cmd = [
        sys.executable,
        str(Path(evidence.__file__)),
        str(source),
        "--inventory",
        str(plan),
        "--out-dir",
        str(output),
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    report = json.loads((output / "REPORT.json").read_text(encoding="utf-8"))
    assert report["recorded_rows"] == report["expected_rows"] == 4
    assert report["unique_live_matches"] == 1
    assert report["inventory_precedes_first_cutoff"] is False
    for name in ("packet_processing.jsonl", "trade_processing.jsonl"):
        assert (
            hashlib.sha256((output / name).read_bytes()).hexdigest()
            == report[name + "_sha256"]
        )
    assert (source.read_bytes(), plan.read_bytes()) == before
    assert subprocess.run(cmd, capture_output=True).returncode != 0
