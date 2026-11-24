"""Independent Claude review probes for the coverage monitor and paired samples (4ed9045).

Synthetic only; no fitting, new capture, live hook or outcome evaluation.
"""

import pytest

from test_instant_coverage import Feed, PID, check, simple
from micro_replay import ReplayStore
from instant_samples import paired_sample


def two_sessions_touching(close=False):
    """Trades 12-20 execute while no session can see them; the sessions share one ms."""
    feed = Feed()
    feed.ack(900)
    feed.hb(1000, 10)
    feed.trade(1200, 11)
    feed.hb(1500, 11)
    if close:
        feed.send(1500, "connection_closed")
    feed.ack(1500, connection=2)
    feed.hb(1500, 20, connection=2)
    feed.hb(2000, 20, connection=2)
    return feed


@pytest.mark.parametrize("close", [False, True])
def test_proofs_join_only_when_connection_and_watermark_continue(close):
    feed = two_sessions_touching(close)
    proofs = feed.monitor.proofs
    assert [(p["end_ts_ms"], p["verified"]) for p in proofs] == [
        (1500, True),
        (2000, True),
    ]
    assert proofs[0]["upper_trade_id_inclusive"] == 11
    assert proofs[1]["lower_trade_id_exclusive"] == 20
    result = check(feed)
    assert result["receipt_id_check_passed"] is False
    assert result["receipt_id_check_reason"] == "trade_coverage_not_yet_proven"
    # Each session's own interval is still individually proven.
    assert check(feed, 1000, 1500, 2001)["receipt_id_check_passed"] is True
    assert check(feed, 1500, 2000, 2001)["receipt_id_check_passed"] is True


def test_contiguous_heartbeats_on_one_connection_still_join():
    feed = simple()
    feed.hb(2500, 11)
    assert check(feed, 1000, 2500, 2501)["receipt_id_check_passed"] is True


def test_old_session_receipt_cannot_satisfy_new_session_id_check():
    """The contract scopes the check to one connection, including at a shared ms."""
    feed = Feed()
    feed.ack(900)
    feed.hb(1000, 10)
    feed.trade(1500, 11)  # Received only on the old connection.
    feed.ack(1500, connection=2)
    feed.hb(1500, 10, connection=2)
    feed.hb(2000, 11, connection=2)
    proof = feed.monitor.proofs[-1]
    assert proof["connection_id"] == 2
    assert proof["verified"] is False
    assert proof["reason"] == "missing_live_match_ids"


@pytest.mark.parametrize(
    "marker, fields",
    [
        ("audit_transport_error", dict(error="reset", error_type="OSError")),
        ("audit_parse_error", dict(raw="{not json")),
    ],
)
def test_real_recorder_failure_markers_invalidate_transport(marker, fields):
    """scripts/coinbase_feed_audit.py writes these names; they carry no product_id."""
    feed = simple()
    feed.send(2100, marker, pid=None, **fields)
    result = feed.monitor.assess(PID, 1000, 2000, asof=2101)
    assert result["transport_observed_ok"] is False
    assert result["transport_reason"] == marker
    # Evidence already completed is not rewritten, but no new pair can straddle it.
    assert result["receipt_id_check_passed"] is True
    feed.hb(2500, 11)
    assert not any(p["end_ts_ms"] == 2500 for p in feed.monitor.proofs)
    assert feed.monitor.assess(PID, 2000, 2500, asof=2501)[
        "receipt_id_check_reason"
    ] == ("trade_coverage_not_yet_proven")


def test_real_recorder_failure_markers_require_a_new_ack_and_baseline():
    feed = simple()
    feed.send(2100, "audit_transport_error", pid=None, error="x", error_type="E")
    feed.ack(2200)
    feed.hb(2300, 11)
    feed.hb(2800, 11)
    result = feed.monitor.assess(PID, 2300, 2800, asof=2801)
    assert result["receipt_id_check_passed"] and result["transport_observed_ok"]


def store_with_health(tmp_path):
    """One coin + BTC store with verified health known by the 10,000ms cutoff."""
    store = ReplayStore(tmp_path / "replay.sqlite", create=True)
    seq = 0
    for pid in (PID, "BTC-USD"):
        seq += 1
        store.ingest(
            dict(
                receipt_seq=seq,
                receipt_ts_ms=9000,
                receipt_monotonic_ns=seq,
                connection_id=1,
                message=dict(
                    type="ticker",
                    product_id=pid,
                    best_bid="100",
                    best_ask="101",
                    best_bid_size="1",
                    best_ask_size="1",
                ),
            )
        )
        store.add_health(
            product=pid,
            start=5000,
            end=10000,
            available=10000,
            verified=True,
            evidence="synthetic known-at-cutoff assertion",
        )
    return store


def test_late_negative_evidence_cannot_change_the_decision_time_sample(tmp_path):
    """Documents the open grading question: correct for inputs, unresolved for labels."""
    store = store_with_health(tmp_path)
    store.add_health(
        product=PID,
        start=5000,
        end=10000,
        available=10500,
        verified=False,
        evidence="synthetic later discovery of bad coverage",
    )
    store.finalize(dict(input_sha256={}, recorder_sha256="x", feed_gate_pass=False))
    paired = paired_sample(store, PID, 10000)
    assert paired.sample is not None
    assert paired.sample.coverage_verified is True
    assert store.coverage(PID, 5000, 10000, 10500) == (False, 10500)
    store.close()


def test_sample_availability_reflects_health_not_row_processing(tmp_path):
    """The store records no processing time, so the row's own availability is not measured."""
    store = store_with_health(tmp_path)
    store.finalize(dict(input_sha256={}, recorder_sha256="x", feed_gate_pass=False))
    paired = paired_sample(store, PID, 10000)
    assert paired.sample.available_ts_ms == 10000
    columns = {row[1] for row in store.db.execute("PRAGMA table_info(quotes)")}
    assert not any("process" in c or "available" in c for c in columns)
    store.close()
