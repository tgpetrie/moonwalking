"""Dry-run the public socket callback path without opening a network socket."""

import json

import pytest

from test_instant_stream_journal import Clock
from instant_source_pilot import CHANNELS, PRODUCTS, capture, _coverage
from instant_stream_journal import StreamJournal, iter_packets


def acknowledgement():
    return dict(
        type="subscriptions",
        channels=[dict(name=channel, product_ids=PRODUCTS) for channel in CHANNELS],
    )


class FakeSocket:
    def __init__(self, clock, frames):
        self.clock = clock
        self.frames = iter(frames)
        self.closed = False
        self.sent = []

    def send(self, raw):
        self.sent.append(json.loads(raw))

    def recv(self):
        self.clock.now += 1000
        item = next(self.frames, "")
        if isinstance(item, Exception):
            raise item
        return json.dumps(item) if isinstance(item, dict) else item

    def close(self, timeout):
        self.closed = True


def run(tmp_path, frames, **options):
    path = tmp_path / "fake.sqlite"
    clock = Clock()
    sockets = [FakeSocket(clock, script) for script in frames]
    connections = iter(sockets)
    with StreamJournal(
        path, PRODUCTS, 30000, 180000, clock_ms=clock, monotonic_ns=clock.mono
    ) as journal:
        result = capture(
            journal,
            lambda: next(connections),
            monotonic=lambda: clock.now / 1000,
            monotonic_ns=clock.mono,
            progress=lambda *args, **kwargs: None,
            **options,
        )
        if result["first_ack_ts_ms"] is not None:
            result["coverage"] = _coverage(
                journal.evidence, result["first_ack_ts_ms"], clock.now
            )
        journal.finish()
    return result, list(iter_packets(path)), sockets


def test_callbacks_subscribe_record_a_reconnect_and_keep_trade_side_pairs(tmp_path):
    trade = dict(
        product_id="BTC-USD",
        trade_id=12,
        price="100",
        size="1",
        side="sell",
        time="1970-01-01T00:00:00.500Z",
    )
    result, packets, sockets = run(
        tmp_path,
        [
            [acknowledgement(), dict(type="match", **trade), OSError("lost transport")],
            [
                acknowledgement(),
                dict(type="ticker", **(trade | {"side": "buy"})),
                "",
            ],
        ],
    )
    assert all(socket.closed for socket in sockets)
    assert sockets[0].sent == [
        dict(type="subscribe", channels=list(CHANNELS), product_ids=list(PRODUCTS))
    ]
    assert result["first_ack_ts_ms"] == 1000
    assert result["stop"] == "remote_close"
    assert result["attempts"][0]["stop"] == "transport_error"
    assert (
        result["attempts"][0]["connection_id"] != result["attempts"][1]["connection_id"]
    )
    assert result["ticker_match_sides"]["BTC-USD"] == dict(paired=1, opposite=1)
    assert (
        result["latencies"]["match:BTC-USD"]["exchange_stamp_to_callback"]["p95_ms"]
        == 1500
    )
    assert any(
        r["envelope"]["message"]["type"] == "audit_transport_error" for r in packets
    )
    assert len({r["envelope"]["connection_id"] for r in packets}) == 2


def test_bounds_stop_cleanly_with_space_for_the_final_marker(tmp_path):
    result, packets, sockets = run(
        tmp_path,
        [[acknowledgement(), dict(type="ticker", product_id="BTC-USD")]],
        packet_stop=3,
    )
    assert result["stop"] == "packet_budget"
    assert len(packets) == 4
    assert packets[-1]["envelope"]["message"]["type"] == "connection_closed"
    assert sockets[0].closed


@pytest.mark.parametrize(
    ("frames", "stop"),
    [
        ([TimeoutError()] * 30, "transport_idle"),
        ([acknowledgement(), "invalid-json"], "callback_failure"),
        (
            [dict(type="error", message="invalid subscription")],
            "exchange_or_source_error",
        ),
    ],
)
def test_failed_feed_preserves_termination_evidence(tmp_path, frames, stop):
    result, packets, sockets = run(tmp_path, [frames])
    assert result["stop"] == stop
    assert sockets[0].closed
    assert packets[-1]["envelope"]["message"]["type"] in (
        "audit_parse_error",
        "audit_transport_error",
        "error",
    )


def test_duration_does_not_restart_after_first_acknowledgment(tmp_path):
    result, packets, _ = run(
        tmp_path,
        [
            [
                acknowledgement(),
                dict(type="ticker"),
                dict(type="ticker"),
                dict(type="ticker"),
            ]
        ],
        duration_s=2,
    )
    assert result["stop"] == "duration"
    assert [p["envelope"]["message"]["type"] for p in packets] == [
        "connection_opened",
        "subscriptions",
        "ticker",
        "ticker",
        "connection_closed",
    ]


def test_exchange_legacy_ack_name_activates_book_and_heartbeat(tmp_path):
    ack = acknowledgement()
    ack["channels"][0]["name"] = "level2_50"
    result, packets, _ = run(
        tmp_path,
        [
            [
                ack,
                dict(type="heartbeat", product_id="BTC-USD", last_trade_id=50),
                dict(
                    type="snapshot",
                    product_id="BTC-USD",
                    bids=[["99", "1"]],
                    asks=[["101", "2"]],
                ),
                dict(type="heartbeat", product_id="BTC-USD", last_trade_id=50),
            ]
        ],
        duration_s=3,
    )
    assert result["first_ack_ts_ms"] == 1000
    assert result["stop"] == "duration"
    assert packets[1]["envelope"]["message"]["channels"][0]["name"] == "level2_50"
    assert result["frames"]["snapshot:BTC-USD"] == 1
