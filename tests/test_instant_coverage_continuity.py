"""Continuity epochs: no merge or assessment chain crosses a lifecycle barrier.

Codex's counterexample (docs/research/RECONCILIATION_BOUNDARY_REVIEW_20261104.md
on codex/instant-radar-20261028) first, then every barrier kind at a shared
millisecond on one reused connection ID, valid recovery on each side, healthy
repeated acknowledgements, ordinary races without a barrier and known-at
immutability. Synthetic only.
"""

import copy
import random

import pytest

from test_instant_coverage import PID, Feed, check
from instant_coverage import MERGED_SCOPE


def merged(feed):
    return [p for p in feed.monitor.proofs if p["scope"] == MERGED_SCOPE]


def intervals(feed):
    return [p for p in feed.monitor.proofs if p["scope"] != MERGED_SCOPE]


def started():
    feed = Feed()
    feed.ack(900)
    feed.hb(1000, 10)
    return feed


def _audit(feed, ts):
    feed.send(ts, "audit_parse_error")


def _transport(feed, ts):
    feed.send(ts, "error")


def _closed(feed, ts):
    feed.send(ts, "connection_closed")


def _queue(feed, ts):
    feed.send(ts, "queue_overflow")


def _lost_subscription(feed, ts):
    # Membership in a required channel is lost and re-added, same connection ID.
    feed.ack(ts, channels=[dict(name="matches", product_ids=[])])


BARRIERS = dict(
    audit_parse_error=_audit,
    transport_error=_transport,
    connection_closed=_closed,
    queue_overflow=_queue,
    lost_subscription=_lost_subscription,
)


def _across(barrier):
    """Codex's tape, with `barrier` in place of the audit failure."""
    feed = started()
    feed.hb(2000, 11)  # First interval fails: ID 11 missing.
    BARRIERS[barrier](feed, 2000)
    feed.ack(2000)  # New complete acknowledgement, same connection ID.
    feed.hb(2000, 11)  # New baseline.
    feed.trade(2500, 11)
    feed.hb(3000, 11)  # Second interval: ID 11 outside its watermarks.
    return feed


def test_codex_counterexample_audit_failure_at_a_shared_millisecond():
    feed = _across("audit_parse_error")
    first, second = intervals(feed)
    assert (first["end_ts_ms"], first["upper_trade_id_inclusive"]) == (
        second["start_ts_ms"],
        second["lower_trade_id_exclusive"],
    )
    assert first["connection_id"] == second["connection_id"] == 1
    assert merged(feed) == []
    result = check(feed, 1000, 3000, 3001)
    assert result["receipt_id_check_passed"] is False
    assert result["receipt_id_check_available_ts_ms"] is None


@pytest.mark.parametrize("barrier", sorted(BARRIERS))
def test_no_merge_across_any_barrier_at_a_shared_millisecond(barrier):
    feed = _across(barrier)
    first, second = intervals(feed)
    assert first["continuity_epoch"] < second["continuity_epoch"]
    assert merged(feed) == []
    assert not check(feed, 1000, 3000, 3001)["receipt_id_check_passed"]
    # Each side alone keeps its own honest failure.
    assert (
        check(feed, 1000, 2000, 3001)["receipt_id_check_reason"]
        == "missing_live_match_ids"
    )
    assert (
        check(feed, 2000, 3000, 3001)["receipt_id_check_reason"]
        == "receipt_ids_outside_watermarks"
    )


@pytest.mark.parametrize("barrier", sorted(BARRIERS))
def test_assess_never_joins_valid_intervals_across_a_barrier(barrier):
    feed = started()
    feed.trade(1500, 11)
    feed.hb(2000, 11)  # Verified.
    BARRIERS[barrier](feed, 2000)
    feed.ack(2000)
    feed.hb(2000, 11)
    feed.trade(2500, 12)
    feed.hb(3000, 12)  # Verified, touching time and watermark, same ID.
    first, second = intervals(feed)
    assert first["verified"] and second["verified"]
    assert first["end_ts_ms"] == second["start_ts_ms"]
    assert first["upper_trade_id_inclusive"] == second["lower_trade_id_exclusive"]
    joined = check(feed, 1000, 3000, 3001)
    assert joined["receipt_id_check_passed"] is False
    assert joined["receipt_id_check_reason"] == "trade_coverage_not_yet_proven"
    # Valid recovery on each side is still usable on its own.
    assert check(feed, 1000, 2000, 3001)["receipt_id_check_passed"] is True
    assert check(feed, 2000, 3000, 3001)["receipt_id_check_passed"] is True


@pytest.mark.parametrize("barrier", sorted(BARRIERS))
def test_races_reconcile_on_each_side_of_a_barrier(barrier):
    feed = started()
    feed.hb(2000, 11)
    feed.trade(2500, 11)
    feed.hb(3000, 11)  # Race before: reconciles within epoch.
    BARRIERS[barrier](feed, 3000)
    feed.ack(3000)
    feed.hb(3000, 11)
    feed.hb(4000, 12)
    feed.trade(4500, 12)
    feed.hb(5000, 12)  # Race after: reconciles within the new epoch.
    spans = [(p["start_ts_ms"], p["end_ts_ms"]) for p in merged(feed)]
    assert spans == [(1000, 3000), (3000, 5000)]
    epochs = [p["continuity_epoch"] for p in merged(feed)]
    assert epochs[0] < epochs[1]
    assert check(feed, 1000, 3000, 5001)["receipt_id_check_passed"] is True
    assert check(feed, 3000, 5000, 5001)["receipt_id_check_passed"] is True
    assert not check(feed, 1000, 5000, 5001)["receipt_id_check_passed"]


def test_trade_received_before_a_barrier_is_not_counted_after_it():
    """Attribution follows receipt order: the pre-barrier receipt stays there."""
    feed = started()
    feed.hb(2000, 10)  # Verified empty.
    feed.trade(2000, 11)  # Received at 2000, before the barrier.
    _audit(feed, 2000)
    feed.ack(2000)
    feed.hb(2000, 10)
    feed.hb(3000, 11)
    assert intervals(feed)[-1]["observed_unique_trade_count"] == 0
    assert intervals(feed)[-1]["reason"] == "missing_live_match_ids"
    assert feed.monitor.trades[PID][0][:2] == (2000, 11)
    assert feed.monitor.seen[(PID, 11)][1] == 2000


def test_healthy_repeated_acknowledgement_is_not_a_barrier():
    feed = started()
    feed.hb(2000, 11)
    feed.ack(2000)  # Same full membership: continuity is retained.
    feed.trade(2500, 11)
    feed.hb(3000, 11)
    first, second = intervals(feed)
    assert first["continuity_epoch"] == second["continuity_epoch"]
    assert [p["merged_proof_count"] for p in merged(feed)] == [2]
    assert check(feed, 1000, 3000, 3001)["receipt_id_check_passed"] is True


def test_acknowledgement_for_other_products_only_is_not_a_barrier():
    other = "OTHER-USD"
    feed = Feed(products=(PID, other))
    feed.ack(900)
    feed.hb(1000, 10)
    feed.hb(2000, 11)
    # Loses OTHER only; TEST-USD keeps full membership.
    feed.ack(
        2000,
        channels=[
            dict(name="ticker", product_ids=[PID, other]),
            dict(name="matches", product_ids=[PID]),
            dict(name="heartbeat", product_ids=[PID, other]),
        ],
    )
    feed.trade(2500, 11)
    feed.hb(3000, 11)
    assert [p["merged_proof_count"] for p in merged(feed)] == [2]
    assert check(feed, 1000, 3000, 3001)["receipt_id_check_passed"] is True


def test_ordinary_same_millisecond_race_without_a_barrier_reconciles():
    feed = started()
    feed.hb(2000, 11)
    feed.trade(2000, 11)  # Same millisecond, after the heartbeat.
    feed.hb(3000, 11)
    assert [p["merged_proof_count"] for p in merged(feed)] == [2]
    assert check(feed, 1000, 3000, 3001)["receipt_id_check_passed"] is True


def test_barrier_does_not_change_known_at_answers_or_records():
    feed = started()
    feed.hb(2000, 11)
    before_records = copy.deepcopy(feed.monitor.proofs)
    before = [check(feed, 1000, 2000, asof) for asof in (2000, 2001, 2500)]
    _audit(feed, 2000)
    feed.ack(2000)
    feed.hb(2000, 11)
    feed.trade(2500, 11)
    feed.hb(3000, 11)
    assert feed.monitor.proofs[: len(before_records)] == before_records
    assert [check(feed, 1000, 2000, asof) for asof in (2000, 2001, 2500)] == before
    assert all(p["available_ts_ms"] >= p["end_ts_ms"] + 1 for p in intervals(feed))


def test_epoch_is_per_product_for_a_lost_subscription():
    other = "OTHER-USD"
    feed = Feed(products=(PID, other))
    feed.ack(900)
    feed.hb(1000, 10)
    feed.hb(1000, 50, pid=other)
    feed.hb(2000, 11)
    feed.hb(2000, 51, pid=other)
    feed.ack(
        2000,
        channels=[
            dict(name="ticker", product_ids=[PID, other]),
            dict(name="matches", product_ids=[other]),
            dict(name="heartbeat", product_ids=[PID, other]),
        ],
    )
    feed.ack(2000)
    feed.hb(2000, 11)
    feed.trade(2500, 11)
    feed.trade(2500, 51, pid=other)
    feed.hb(3000, 11)
    feed.hb(3000, 51, pid=other)
    assert not check(feed, 1000, 3000, 3001)["receipt_id_check_passed"]
    assert feed.monitor.assess(other, 1000, 3000, asof=3001)["receipt_id_check_passed"]


def _random_barrier_tape(seed):
    """Safety property: no proof or passing chain contains a barrier receipt."""
    rng = random.Random(seed)
    feed = started()
    now, watermark, barriers = 1000, 10, []
    for _ in range(rng.randint(6, 30)):
        now += rng.choice((0, 500, 1000))
        if rng.random() < 0.2:
            name = rng.choice(sorted(BARRIERS))
            BARRIERS[name](feed, now)
            barriers.append((feed.seq, now))
            feed.ack(now)
            feed.hb(now, watermark)
            continue
        for _ in range(rng.choice((0, 1, 2))):
            watermark += 1
            if rng.random() < 0.7:
                feed.trade(now, watermark)
        feed.hb(now, watermark)
    for proof in feed.monitor.proofs:
        inside = [
            seq
            for seq, _ in barriers
            if proof["start_heartbeat_seq"] < seq < proof["end_heartbeat_seq"]
        ]
        assert inside == [], proof
    edges = sorted(
        {p["start_ts_ms"] for p in feed.monitor.proofs}
        | {p["end_ts_ms"] for p in feed.monitor.proofs}
    )
    passes = 0
    for start in edges:
        for end in edges:
            if (
                end > start
                and check(feed, start, end, now + 1)["receipt_id_check_passed"]
            ):
                passes += 1
                assert not any(start < ts < end for _, ts in barriers)
    return passes


@pytest.mark.parametrize("seed", range(200))
def test_randomized_barriers_never_join_epochs(seed):
    _random_barrier_tape(seed)


def test_randomized_barrier_tapes_still_certify_within_epochs():
    assert sum(_random_barrier_tape(seed) for seed in range(200)) > 500


def test_contract_records_continuity_barriers_with_limits_unchanged():
    import json

    import instant_coverage

    cfg = json.loads(instant_coverage.CONTRACT.read_text(encoding="utf-8"))
    merge = cfg["reconciliation"]
    assert "continuity_barriers" in merge
    assert (merge["max_merged_proofs"], merge["max_merged_span_ms"]) == (4, 10000)
    assert cfg["feed_gate_pass"] is False
    assert cfg["live_integration"] is False
