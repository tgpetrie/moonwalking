"""Exercise reader timing, overflow and separate outbox observation."""

from dataclasses import asdict
import json

import pytest

from test_instant_source_pilot import FakeSocket, acknowledgement
from test_instant_stream_journal import Clock
from instant_delayed_decision import prepare_decision
from instant_real_indexed_pilot import (
    QUEUE_CAPACITY,
    QueuedSocket,
    _observe,
    _observation_report,
)
from instant_source_pilot import (
    PRODUCTS,
    PilotCallbacks,
    QueueOverflowError,
    ReceivedFrame,
    capture,
)
from instant_stream_journal import StreamJournal, iter_packets


def test_original_reader_stamp_survives_the_writer_queue(tmp_path):
    clock = Clock()
    journal = StreamJournal(
        tmp_path / "capture.sqlite",
        PRODUCTS,
        30000,
        35000,
        clock_ms=clock,
        monotonic_ns=clock.mono,
        indexed=True,
    )
    with journal:
        callbacks = PilotCallbacks(journal, duration_ns=clock.mono)
        callbacks.on_open(FakeSocket(clock, []))
        clock.now = 180
        callbacks.on_message(
            ReceivedFrame(json.dumps(acknowledgement()), 100, 100000000)
        )
        assert callbacks.ack == 100
        assert callbacks.last_reader_receipt_ts_ms == 100
        assert (
            callbacks.report()["latencies"]["subscriptions"]["reader_to_writer"][
                "p95_ms"
            ]
            == 80
        )
        callbacks.on_close()
    row = list(iter_packets(tmp_path / "capture.sqlite"))[1]
    assert row["processing"]["receipt_ts_ms"] == 100
    assert row["processing"]["available_ts_ms"] == 180


def test_reader_overflow_stops_before_dequeueing_across_loss():
    raw = FakeSocket(Clock(), [dict(type="ticker")] * (QUEUE_CAPACITY + 1))
    socket = QueuedSocket(raw, (TimeoutError,))
    socket.send("{}")
    assert socket.done.wait(2)
    with pytest.raises(QueueOverflowError, match="frame cap"):
        socket.recv()
    assert socket.delivered == 0
    socket.close(timeout=1)
    assert raw.closed


def test_capture_persists_queue_loss_as_explicit_barrier(tmp_path):
    clock = Clock()
    path = tmp_path / "capture.sqlite"
    raw = FakeSocket(clock, [acknowledgement(), QueueOverflowError("limit")])
    with StreamJournal(
        path,
        PRODUCTS,
        30000,
        35000,
        clock_ms=clock,
        monotonic_ns=clock.mono,
    ) as journal:
        result = capture(
            journal,
            lambda: raw,
            monotonic=lambda: clock.now / 1000,
            duration_ns=clock.mono,
            max_connections=1,
            progress=lambda *args, **kwargs: None,
        )
        assert result["stop"] == "queue_overflow"
        assert result["attempts"][0]["error"] == "limit"
    assert (
        list(iter_packets(path))[-1]["envelope"]["message"]["type"] == "queue_overflow"
    )


def test_observer_excludes_pending_and_detects_bad_clock(tmp_path):
    path = tmp_path / "capture.sqlite"
    clock = Clock()
    with StreamJournal(
        path,
        PRODUCTS,
        30000,
        35000,
        clock_ms=clock,
        monotonic_ns=clock.mono,
        indexed=True,
    ) as journal:
        clock.now = 30000
        snapshot = prepare_decision(
            journal.evidence, PRODUCTS[0], 30000, "up", asof=30000
        )
        receipt = journal.append_publication("ready", snapshot)
        with journal._db:
            journal._db.execute(
                "INSERT INTO publications SELECT 'pending', decision_sha256, body, digest, NULL FROM publications"
            )
        stop = tmp_path / "observer.stop"
        stop.touch()
        _observe(path, tmp_path / "observed.jsonl", stop)
    original = dict(asdict(receipt))
    original["commit_observed_ts_ms"] = original.pop("local_commit_observed_ts_ms")
    rows = [dict(original, cutoff_ts_ms=30000)]
    report = _observation_report(tmp_path, rows)
    assert report["missing_or_invalid"] == 0
    assert report["commit_observed_to_reader_seen"]["n"] == 1
    assert rows[0]["consumer_seen_ts_ms"] > 30000
    with (tmp_path / "observed.jsonl").open("a", encoding="utf-8") as out:
        out.write('{"unfinished":\n')
    assert _observation_report(tmp_path, rows)["discrepancies"] == {
        "unreadable_observation": 1
    }
