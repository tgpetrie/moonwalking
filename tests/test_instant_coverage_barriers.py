"""Continuity barriers for amendment-1 reconciliation and assess chaining.

Codex's reproduced false pass against bfab9c8 comes first. Written
independently of the d26c57d fix on this branch (26 of 30 failed on bfab9c8)
and kept as a second probe set against the same implementation. An audit, queue or
transport failure, a connection change or a lost required subscription resets
continuity. No merged proof or assessment chain may cross that reset, even when
every event shares one millisecond, the connection ID is reused and watermarks
touch. Synthetic only; nothing here reads prices, returns or labels.
"""

import pytest

from test_instant_coverage import Feed, PID, check
from instant_coverage import MERGED_SCOPE

FAILURES = (
    "audit_parse_error",
    "audit_transport_error",
    "audit_unknown_loss",
    "queue_overflow",
    "connection_closed",
    "error",
)


def merged(feed):
    return [p for p in feed.monitor.proofs if p["scope"] == MERGED_SCOPE]


def intervals(feed):
    return [p for p in feed.monitor.proofs if p["scope"] != MERGED_SCOPE]


def _fail(feed, ts, kind):
    feed.send(ts, kind, pid=None)
    feed.ack(ts)


def _drop_and_readd(feed, ts):
    feed.ack(ts, channels=[dict(name="matches", product_ids=[])])
    feed.ack(ts)


def _drop_one_channel_membership(feed, ts):
    channels = [
        dict(name=c, product_ids=[] if c == "heartbeat" else [PID])
        for c in ("ticker", "matches", "heartbeat")
    ]
    feed.ack(ts, channels=channels)
    feed.ack(ts)


BARRIERS = [pytest.param(lambda f, ts, k=k: _fail(f, ts, k), id=k) for k in FAILURES]
BARRIERS += [
    pytest.param(_drop_and_readd, id="lost_all_membership"),
    pytest.param(_drop_one_channel_membership, id="lost_heartbeat_membership"),
]


def codex_counterexample(barrier=lambda f, ts: _fail(f, ts, "audit_parse_error")):
    """docs/research/RECONCILIATION_BOUNDARY_REVIEW_20261104.md, verbatim timing."""
    feed = Feed()
    feed.ack(900)
    feed.hb(1000, 10)
    feed.hb(2000, 11)  # Missing ID 11.
    barrier(feed, 2000)  # Continuity must reset here.
    feed.hb(2000, 11)  # New baseline, same millisecond, same connection.
    feed.trade(2500, 11)
    feed.hb(3000, 11)  # ID 11 is outside the new interval's watermarks.
    return feed


def test_codex_audit_failure_at_one_millisecond_is_never_merged_across():
    feed = codex_counterexample()
    assert [p["reason"] for p in intervals(feed)] == [
        "missing_live_match_ids",
        "receipt_ids_outside_watermarks",
    ]
    assert merged(feed) == []
    result = check(feed, 1000, 3000, 3001)
    assert result["receipt_id_check_passed"] is False
    assert result["receipt_id_check_reason"] == "missing_live_match_ids"


@pytest.mark.parametrize("barrier", BARRIERS)
def test_no_merge_across_any_barrier_at_a_shared_millisecond(barrier):
    feed = codex_counterexample(barrier)
    assert len(intervals(feed)) == 2 and merged(feed) == []
    first, second = intervals(feed)
    # The reconstruction that bfab9c8 merged: same connection, touching time
    # and watermarks, exact ID equality over the union. Only the epoch differs.
    assert first["connection_id"] == second["connection_id"] == 1
    assert first["end_ts_ms"] == second["start_ts_ms"] == 2000
    assert first["upper_trade_id_inclusive"] == second["lower_trade_id_exclusive"]
    for start, end in ((1000, 3000), (1000, 2000), (2000, 3000)):
        assert not check(feed, start, end, 3001)["receipt_id_check_passed"]


@pytest.mark.parametrize("barrier", BARRIERS)
def test_assess_never_chains_verified_intervals_across_a_barrier(barrier):
    feed = Feed()
    feed.ack(900)
    feed.hb(1000, 10)
    feed.hb(2000, 10)  # Verified, no trades.
    barrier(feed, 2000)
    feed.hb(2000, 10)
    feed.hb(3000, 10)  # Verified, no trades.
    first, second = intervals(feed)
    assert first["verified"] and second["verified"]
    assert first["upper_trade_id_inclusive"] == second["lower_trade_id_exclusive"]
    joined = check(feed, 1000, 3000, 3001)
    assert joined["receipt_id_check_passed"] is False
    assert joined["receipt_id_check_reason"] == "trade_coverage_not_yet_proven"
    # Each side is still usable on its own.
    assert check(feed, 1000, 2000, 3001)["receipt_id_check_passed"]
    assert check(feed, 2000, 3000, 3001)["receipt_id_check_passed"]


@pytest.mark.parametrize("barrier", BARRIERS)
def test_valid_races_reconcile_on_each_side_of_a_barrier(barrier):
    feed = Feed()
    feed.ack(900)
    feed.hb(1000, 10)
    feed.hb(2000, 11)  # Old epoch race: heartbeat overtakes match 11.
    feed.trade(2500, 11)
    feed.hb(3000, 11)
    barrier(feed, 3000)
    feed.hb(3000, 11)
    feed.hb(4000, 12)  # New epoch race: heartbeat overtakes match 12.
    feed.trade(4500, 12)
    feed.hb(5000, 12)
    spans = [(p["start_ts_ms"], p["end_ts_ms"]) for p in merged(feed)]
    assert spans == [(1000, 3000), (3000, 5000)]
    old, new = merged(feed)
    assert old["available_ts_ms"] == 3001 and new["available_ts_ms"] == 5001
    assert check(feed, 1000, 3000, 5001)["receipt_id_check_passed"]
    assert check(feed, 3000, 5000, 5001)["receipt_id_check_passed"]
    assert not check(feed, 1000, 5000, 5001)["receipt_id_check_passed"]


def test_healthy_repeated_acknowledgements_do_not_break_merges_or_chains():
    feed = Feed()
    feed.ack(900)
    feed.hb(1000, 10)
    feed.hb(2000, 11)
    feed.ack(2000)  # Same full membership: no reset.
    feed.ack(2200)
    feed.trade(2500, 11)
    feed.hb(3000, 11)
    feed.hb(4000, 11)
    assert len(merged(feed)) == 1
    assert check(feed, 1000, 4000, 4001)["receipt_id_check_passed"]


def test_ordinary_race_without_a_barrier_still_reconciles():
    feed = Feed()
    feed.ack(900)
    feed.hb(1000, 10)
    feed.hb(2000, 11)
    feed.trade(2500, 11)
    feed.hb(3000, 11)
    assert len(merged(feed)) == 1
    assert check(feed, 1000, 3000, 3001)["receipt_id_check_passed"]


def test_epoch_advances_at_the_reset_and_rows_stay_immutable():
    feed = codex_counterexample()
    marker = next(
        e["receipt_seq"]
        for e in feed.events
        if e["message"]["type"] == "audit_parse_error"
    )
    first, second = intervals(feed)
    # The marker and the acknowledgement that re-adds membership both advance
    # the epoch; the second interval lies strictly after both.
    assert second["continuity_epoch"] >= first["continuity_epoch"] + 2
    assert second["end_heartbeat_seq"] > marker
    healthy = Feed()
    healthy.ack(900)
    healthy.hb(1000, 10)
    healthy.hb(2000, 10)
    healthy.ack(2000)  # Same full membership: the epoch is retained.
    healthy.hb(3000, 10)
    assert len({p["continuity_epoch"] for p in healthy.monitor.proofs}) == 1
    # Original failed rows, availability and trade attribution are unchanged.
    assert (first["available_ts_ms"], second["available_ts_ms"]) == (2001, 3001)
    assert [t[:3] for t in feed.monitor.trades[PID]] == [(2500, 11, 1)]
    assert feed.monitor.times[PID] == [2500]


def test_earlier_knowledge_is_not_rewritten_by_a_later_barrier():
    feed = Feed()
    feed.ack(900)
    feed.hb(1000, 10)
    feed.hb(2000, 11)
    feed.trade(2500, 11)
    feed.hb(3000, 11)  # Merged [1000,3000), known at 3001.
    before = check(feed, 1000, 3000, 3001)
    rows = [dict(p) for p in feed.monitor.proofs]
    _fail(feed, 3000, "audit_transport_error")
    feed.hb(3000, 11)
    feed.hb(4000, 11)
    assert check(feed, 1000, 3000, 3001) == before
    assert before["receipt_id_check_passed"]
    assert [dict(p) for p in feed.monitor.proofs[: len(rows)]] == rows


def test_barrier_on_another_connection_id_also_separates_epochs():
    feed = Feed()
    feed.ack(900)
    feed.hb(1000, 10)
    feed.hb(2000, 11)
    feed.ack(2000, connection=2)
    feed.send(2000, "audit_parse_error", pid=None, connection=2)
    feed.ack(2000, connection=2)
    feed.hb(2000, 11, connection=2)
    feed.trade(2500, 11, connection=2)
    feed.hb(3000, 11, connection=2)
    assert merged(feed) == []
