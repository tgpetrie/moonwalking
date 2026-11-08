"""Causal handling of a recorder-owned socket's pre-acknowledgment book."""

import pytest

from test_instant_book import Feed, PID


def test_same_ms_snapshot_before_ack_is_activated_without_backdating():
    feed = Feed()
    feed.send(1000, "connection_opened")
    feed.snapshot(4900)
    feed.send(
        4900,
        "subscriptions",
        lag=200,
        channels=[
            dict(name=c, product_ids=[PID])
            for c in ("level2_50", "matches", "heartbeat")
        ],
    )
    feed.send(4950, "heartbeat", lag=250, last_trade_id=10)
    assert feed.book.view(PID, 5000).reason == "subscription_unconfirmed"
    after_ack = feed.book.view(PID, 5000, asof=5100)
    assert after_ack.reason == "heartbeat_unavailable"
    quote = feed.book.view(PID, 5000, asof=5200)
    assert quote.book_state_available and quote.mid == 100
    assert quote.observation_ts_ms == 4900
    assert quote.available_ts_ms == 5100
    assert feed.book.history[PID][-1].receipt_seq == 3


def test_pre_ack_update_keeps_its_observation_time_but_activates_at_ack():
    feed = Feed()
    feed.send(1000, "connection_opened")
    feed.snapshot(1500)
    feed.update(2700, [["buy", "99", "3"]])
    feed.ack(5000)
    feed.hb(8000)
    assert feed.book.view(PID, 5000, asof=8500).reason == "subscription_unconfirmed"
    quote = feed.book.view(PID, 10000)
    assert quote.book_state_available and quote.bid_size == "3"
    assert quote.observation_ts_ms == 2700 and quote.observation_age_ms == 7300
    assert feed.book.history[PID][-1].receipt_ts_ms == 5000


@pytest.mark.parametrize(
    "barrier", ["queue_overflow", "connection_change", "partial_ack", "invalid_update"]
)
def test_staged_snapshot_cannot_cross_a_loss_or_missing_membership(barrier):
    feed = Feed()
    feed.send(1000, "connection_opened")
    feed.snapshot(1500)
    conn = 1
    if barrier == "queue_overflow":
        feed.send(1600, "queue_overflow")
    elif barrier == "connection_change":
        conn = 2
        feed.send(1600, "connection_opened", connection=conn)
    elif barrier == "partial_ack":
        feed.ack(1600, products=())
    else:
        feed.update(1600, [["buy", "103", "1"]])
    feed.ack(2000, connection=conn)
    feed.hb(3000, connection=conn)
    assert feed.book.view(PID, 5000).reason == "awaiting_snapshot"
