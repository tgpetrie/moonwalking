"""Hand-computed books, atomic batches, lifecycle/knowledge and publication clocks."""

from dataclasses import FrozenInstanceError
from pathlib import Path
import sys

import pytest

sys.path.insert(
    0, str(Path(__file__).resolve().parents[1] / "scripts/scoring_experiment")
)
from instant_book import BookReplay
from instant_publication import publication_timing


PID = "TEST-USD"


class Feed:
    def __init__(self, products=(PID,)):
        self.now = 0
        self.seq = 0
        self.book = BookReplay(products, clock_ms=lambda: self.now)
        self.products = products

    def send(self, ts, kind, *, pid=PID, connection=1, source="ws", lag=0, **fields):
        self.seq += 1
        self.now = ts + lag
        env = dict(
            receipt_seq=self.seq,
            receipt_ts_ms=ts,
            receipt_monotonic_ns=ts * 1000000,
            connection_id=connection,
            source=source,
            message=dict(type=kind, product_id=pid, **fields),
        )
        self.book.ingest(env)

    def ack(self, ts, *, products=None, connection=1):
        self.send(
            ts,
            "subscriptions",
            connection=connection,
            channels=[
                dict(
                    name=c,
                    product_ids=list(self.products if products is None else products),
                )
                for c in ("level2_batch", "matches", "heartbeat")
            ],
        )

    def hb(self, ts, *, pid=PID, connection=1):
        self.send(ts, "heartbeat", pid=pid, connection=connection, last_trade_id=10)

    def snapshot(self, ts, **kw):
        fields = dict(
            bids=[["99", "2"], ["98", "7"]], asks=[["101", "1"], ["102", "8"]]
        )
        fields.update(kw)
        self.send(ts, "snapshot", **fields)

    def update(self, ts, changes, **kw):
        self.send(ts, "l2update", changes=changes, **kw)


def ready():
    feed = Feed()
    feed.ack(100)
    feed.hb(1000)
    feed.snapshot(1200)
    feed.hb(4500)
    return feed


def test_hand_computed_snapshot_is_sorted_has_sizes_and_preserves_source_scope():
    feed = ready()
    view = feed.book.view(PID, 5000)
    assert view.book_state_available and view.mid == 100
    assert (view.bid, view.ask, view.bid_size, view.ask_size) == ("99", "101", "2", "1")
    assert view.sampled_pressure == pytest.approx(1 / 3)
    assert view.observation_age_ms == 3800 and view.available_ts_ms == 1201
    assert not view.full_feed_verified and not view.target_sample_adapter_supported
    with pytest.raises(FrozenInstanceError):
        view.bid = "100"
    with pytest.raises(FrozenInstanceError):
        feed.book.history[PID][-1].reason = "fake"


def test_absolute_updates_zero_deletion_and_repeated_price_last_wins():
    feed = ready()
    feed.update(
        4600,
        [
            ["buy", "99", "3"],
            ["buy", "99", "5"],
            ["sell", "101", "0"],
            ["sell", "101.5", "4"],
        ],
    )
    view = feed.book.view(PID, 5000)
    assert (view.bid_size, view.ask, view.ask_size) == ("5", "101.5", "4")
    assert view.sampled_pressure == pytest.approx(1 / 9)
    assert view.mid == 100.25


def test_whole_batch_is_atomic_when_an_intermediate_state_would_cross():
    feed = ready()
    feed.update(
        4600,
        [
            ["buy", "102", "3"],
            ["sell", "101", "0"],
            ["sell", "102", "0"],
            ["sell", "103", "4"],
        ],
    )
    view = feed.book.view(PID, 5000)
    assert view.book_state_available and view.bid == "102" and view.ask == "103"
    # Only the final packet state is observable; no intrabatch peak is created.
    assert len([r for r in feed.book.history[PID] if r.receipt_ts_ms == 4600]) == 1


@pytest.mark.parametrize(
    "changes",
    [
        [["buy", "105", "3"]],
        [["buy", "101", "3"]],
        [["sell", "101", "0"], ["sell", "102", "0"]],
        [["buy", "99", "3"], ["invalid", "100", "2"]],
        [["buy", "NaN", "1"]],
        [["sell", "101", "-1"]],
        [],
        [["buy", "99", "Infinity"]],
        [["buy", "99", True]],
        [["buy", "1e9999", "1"]],
        [["buy", "1e-9999", "1"]],
    ],
)
def test_invalid_batch_discards_book_and_requires_a_new_snapshot(changes):
    feed = ready()
    before = feed.book.view(PID, 5000)
    feed.update(5100, changes)
    feed.hb(9000)
    failed = feed.book.view(PID, 10000)
    assert failed.reason == "invalid_book_update" and failed.bid is None
    feed.update(9100, [["buy", "99", "2"]])
    assert feed.book.view(PID, 10000).reason == "awaiting_snapshot"
    feed.snapshot(9200)
    assert feed.book.view(PID, 10000).book_state_available
    assert feed.book.view(PID, 5000) == before


@pytest.mark.parametrize(
    "fields",
    [
        dict(bids=[]),
        dict(asks=[]),
        dict(bids=[["99", "0"]]),
        dict(bids=[["99", "2"], ["99.0", "2"]]),
        dict(bids=[["101", "2"]]),
        dict(asks=[["98", "1"]]),
        dict(bids=[["-1", "2"]]),
        dict(asks=[["101", None]]),
    ],
)
def test_invalid_snapshots_do_not_create_usable_quotes(fields):
    feed = ready()
    feed.snapshot(4600, **fields)
    assert feed.book.view(PID, 5000).reason == "invalid_book_snapshot"


def test_observation_whole_book_and_bbo_change_clocks_are_distinct():
    feed = ready()
    feed.update(4600, [["buy", "98", "8"]])
    view = feed.book.view(PID, 5000)
    assert view.observation_ts_ms == view.book_change_ts_ms == 4600
    assert view.bbo_change_ts_ms == 1200
    feed.update(
        4700, [["buy", "98", "8"]]
    )  # Actual no-op observation renews observation only.
    view = feed.book.view(PID, 5000)
    assert (view.observation_ts_ms, view.book_change_ts_ms, view.bbo_change_ts_ms) == (
        4700,
        4600,
        1200,
    )
    feed.update(4800, [["buy", "99", "4"]])
    assert feed.book.view(PID, 5000).bbo_change_ts_ms == 4800


def test_heartbeats_do_not_refresh_book_quote_age():
    feed = Feed()
    feed.ack(100)
    feed.hb(1000)
    feed.hb(5000)
    feed.snapshot(5000)
    for ts in (9000, 13000, 14999):
        feed.hb(ts)
    assert feed.book.view(PID, 15000).book_state_available  # Exact 10s allowed.
    feed.hb(19000)
    view = feed.book.view(PID, 20000)
    assert view.reason == "stale_book_observation" and view.observation_ts_ms == 5000
    assert view.mid is None and view.observation_age_ms == 15000


def test_same_cutoff_packet_is_excluded_even_with_later_knowledge():
    feed = ready()
    early = feed.book.view(PID, 5000)
    feed.update(5000, [["buy", "99", "4"]])
    assert feed.book.view(PID, 5000) == early
    later = feed.book.view(PID, 5000, asof=6000)
    assert later.bid_size == "2"


def test_later_processing_and_retro_view_do_not_rewrite_earlier_knowledge():
    feed = ready()
    before = feed.book.view(PID, 5000)
    feed.update(4600, [["buy", "99", "4"]], lag=1000)
    assert feed.book.view(PID, 5000) == before
    retrospective = feed.book.view(PID, 5000, asof=5600)
    assert retrospective.bid_size == "4" and retrospective.available_ts_ms == 5600
    assert feed.book.view(PID, 5000) == before


def test_availability_is_measured_after_book_computation():
    feed = ready()
    clock = iter(
        (4600, 4700, 5500)
    )  # Monitor start, monitor completion, book completion.
    feed.book.monitor.clock_ms = lambda: next(clock)
    feed.update(4600, [["buy", "99", "4"]])
    assert feed.book.view(PID, 5000).bid_size == "2"
    assert feed.book.view(PID, 5000, asof=5500).available_ts_ms == 5500


@pytest.mark.parametrize(
    "kind",
    [
        "connection_closed",
        "error",
        "queue_overflow",
        "audit_parse_error",
        "audit_transport_error",
        "audit_unknown_loss",
    ],
)
def test_lifecycle_failures_require_new_ack_and_snapshot(kind):
    feed = ready()
    before = feed.book.view(PID, 5000)
    feed.send(5100, kind)
    feed.snapshot(5200)
    feed.hb(9000)
    assert not feed.book.view(PID, 10000).book_state_available
    feed.ack(9100)
    feed.hb(9200)
    feed.update(9300, [["buy", "99", "3"]])
    assert feed.book.view(PID, 10000).reason == "awaiting_snapshot"
    feed.snapshot(9400)
    assert feed.book.view(PID, 10000).book_state_available
    assert feed.book.view(PID, 5000) == before


def test_new_connection_never_reuses_old_subscription_or_book():
    feed = ready()
    feed.hb(5100, connection=2)
    feed.snapshot(5200, connection=2)
    assert not feed.book.view(PID, 10000).book_state_available
    feed.ack(5300, connection=2)
    feed.hb(9000, connection=2)
    feed.update(9100, [["buy", "99", "4"]], connection=2)
    assert not feed.book.view(PID, 10000).book_state_available
    feed.snapshot(9200, connection=2)
    assert feed.book.view(PID, 10000).connection_id == 2


def test_lost_subscription_does_not_bridge_a_gap():
    feed = ready()
    feed.ack(5100, products=())
    feed.ack(5200)
    feed.hb(9000)
    feed.update(9100, [["buy", "99", "4"]])
    assert not feed.book.view(PID, 10000).book_state_available
    feed.snapshot(9200)
    assert feed.book.view(PID, 10000).book_state_available


def test_heartbeat_gap_requires_snapshot_and_staleness_is_separate():
    feed = ready()
    assert feed.book.view(PID, 10000).reason == "stale_heartbeat"
    feed.hb(11000)  # >5s from 4500; book continuity is unknown.
    feed.update(11100, [["buy", "99", "4"]])
    assert feed.book.view(PID, 15000).reason == "awaiting_snapshot"
    feed.snapshot(11200)
    assert feed.book.view(PID, 15000).book_state_available


def test_rest_snapshots_and_tickers_never_replace_book_state():
    feed = ready()
    old = feed.book.view(PID, 5000)
    feed.send(4600, "snapshot", source="rest", bids=[["100", "1"]], asks=[["102", "1"]])
    feed.send(4700, "ticker", best_bid="100", best_ask="102", last_size="9999")
    assert feed.book.view(PID, 5000) == old


def test_book_underflow_bound_and_logger_failure_are_explicit(monkeypatch):
    import instant_book

    feed = ready()
    monkeypatch.setattr(instant_book, "MAX_LEVELS", 2)
    feed.update(4600, [["buy", "97", "2"]])
    assert feed.book.view(PID, 5000).reason == "invalid_book_update"
    feed.now = 4700
    with pytest.raises(ValueError, match="sequence"):
        feed.book.ingest(
            dict(
                receipt_seq=100,
                receipt_ts_ms=4700,
                receipt_monotonic_ns=4700000000,
                connection_id=1,
                message=dict(type="heartbeat", product_id=PID, last_trade_id=10),
            )
        )
    with pytest.raises(ValueError, match="failed book"):
        feed.book.view(PID, 5000)


def timing(**kw):
    args = dict(
        publication_id="alert-1",
        product_id=PID,
        feature_cutoff=10000,
        inputs_available=10060,
        decision_completed=10080,
        published=10100,
    )
    args.update(kw)
    return publication_timing(**args)


def test_late_proof_is_recorded_without_backdating_or_approving_fit():
    row = timing()
    assert row.feature_age_at_publication_ms == 100
    assert row.verification_lag_from_cutoff_ms == 60
    assert row.decision_to_publication_ms == 20
    assert not row.legacy_cutoff_inputs_compatible
    assert row.publication_target_amendment_required and not row.eligible_for_fitting
    assert row.within_declared_feature_age is None
    with pytest.raises(FrozenInstanceError):
        row.feature_cutoff_ts_ms = 10100


@pytest.mark.parametrize("age,within", [(99, False), (100, True), (101, True)])
def test_age_boundaries_are_exact_but_a_bound_is_not_a_study_freeze(age, within):
    row = timing(max_feature_age_ms=age)
    assert row.within_declared_feature_age is within
    assert not row.eligible_for_fitting


def test_legacy_same_cutoff_timing_can_be_described_without_changing_labels():
    row = timing(inputs_available=10000, decision_completed=10000, published=10000)
    assert (
        row.legacy_cutoff_inputs_compatible
        and not row.publication_target_amendment_required
    )


@pytest.mark.parametrize(
    "changes",
    [
        dict(feature_cutoff=10001),
        dict(feature_cutoff=True),
        dict(inputs_available=9999),
        dict(inputs_available=10081),
        dict(decision_completed=10059),
        dict(published=10079),
        dict(publication_id=""),
        dict(product_id=""),
        dict(published=float("inf")),
        dict(max_feature_age_ms=-1),
        dict(max_feature_age_ms=True),
    ],
)
def test_publication_chronology_and_metadata_are_validated(changes):
    with pytest.raises(ValueError):
        timing(**changes)
