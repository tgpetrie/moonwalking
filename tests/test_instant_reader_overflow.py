"""Offline, event-gated queue overloads; no network or scheduler-speed assertions."""

import json
import sqlite3
from threading import Event

import pytest

from test_instant_source_pilot import acknowledgement
from instant_real_indexed_pilot import QueuedSocket
from instant_source_pilot import PRODUCTS, QueueOverflowError, capture
from instant_stream_journal import (
    MAX_FRAME_BYTES,
    StreamJournal,
    iter_packets,
    iter_pending_ingress,
)


class ArrivalClock:
    """Only the synthetic socket advances elapsed time; no real sleeps."""

    def __init__(self):
        self.ns = 1_000_000_000

    def mono(self):
        return self.ns

    def wall(self):
        return self.ns // 1_000_000


class GatedFrames:
    def __init__(self, clock, count, interval_ns, *, ack=False):
        self.clock, self.count, self.interval_ns = clock, count, interval_ns
        self.ack = ack
        self.release = Event()
        self.closed = False

    def send(self, raw):
        pass

    def recv(self):
        if self.ack:
            self.ack = False
            return json.dumps(acknowledgement())
        assert self.release.wait(5), "writer never released the synthetic source"
        if not self.count:
            return ""
        self.count -= 1
        self.clock.ns += self.interval_ns
        return '{"type":"ticker","product_id":"BTC-USD"}'

    def abort(self):
        self.release.set()

    def close(self, timeout):
        self.closed = True


def legacy_counts(report):
    return {
        key: report[key]
        for key in (
            "received",
            "delivered",
            "received_not_delivered",
            "sampled_high_water",
        )
    }


def test_burst_without_writer_and_slow_arrivals_during_stall_share_old_counts(
    monkeypatch, capsys
):
    reports = []
    for phase, interval_ns in (
        ("between_callbacks", 100_000),
        ("journal_callback", 20_000_000),
    ):
        clock = ArrivalClock()
        monkeypatch.setattr("instant_real_indexed_pilot.utc_ms", clock.wall)
        source = GatedFrames(clock, 257, interval_ns)
        socket = QueuedSocket(
            source, (TimeoutError,), max_frames=256, monotonic_ns=clock.mono
        )
        try:
            # For the stall case this labels the blocked owner. The integration
            # test below also stalls the real journal's persistence operation.
            with socket.writer_activity(phase, 1 if phase == "journal_callback" else 0):
                socket.send("{}")
                source.release.set()
                assert socket.done.wait(5)
                reports.append(socket.reader_report())
            with pytest.raises(QueueOverflowError, match="frame cap"):
                socket.recv()
            assert socket.recv_ready(16) == []
        finally:
            socket.close(timeout=1)
        assert source.closed
    burst, stall = reports
    assert (
        legacy_counts(burst)
        == legacy_counts(stall)
        == dict(
            received=257,
            delivered=0,
            received_not_delivered=257,
            sampled_high_water=256,
        )
    )
    burst, stall = burst["overflow"], stall["overflow"]
    assert burst["arrival_windows_ms"]["100"] == {"returned": 257, "lower_bound": True}
    assert burst["retained_return_span_ms"] == pytest.approx(25.6)
    assert burst["writer"]["phase"] == "between_callbacks"
    assert stall["arrival_windows_ms"]["100"] == {"returned": 6, "lower_bound": False}
    assert stall["retained_return_span_ms"] == 5120
    assert stall["writer"] == {
        "phase": "journal_callback",
        "frames": 1,
        "elapsed_ms": 5140,
    }
    assert stall["oldest_queued_age_ms"] == 5120
    logs = [
        json.loads(line.removeprefix("READER_OVERFLOW "))
        for line in capsys.readouterr().err.splitlines()
    ]
    assert logs == [burst, stall]


@pytest.mark.parametrize("capacity", [4, 256])
@pytest.mark.parametrize("interval_ns", [100_000, 20_000_000], ids=["burst", "paced"])
@pytest.mark.parametrize("phase", ["journal_callback", "after_commit"])
def test_real_capture_freezes_failure_context_before_stalled_owner_recovers(
    tmp_path, monkeypatch, capsys, capacity, interval_ns, phase
):
    clock = ArrivalClock()
    monkeypatch.setattr("instant_real_indexed_pilot.utc_ms", clock.wall)
    source = GatedFrames(clock, capacity + 1, interval_ns, ack=True)
    socket = QueuedSocket(
        source, (TimeoutError,), max_frames=capacity, monotonic_ns=clock.mono
    )
    path = tmp_path / "capture.sqlite"
    frozen = []

    def stall_owner():
        source.release.set()
        assert socket.done.wait(5), "reader failed to fill bounded queue"
        # Snapshot and stderr must already exist before the journal/hook resumes.
        frozen.append(socket.reader_report()["overflow"])
        assert frozen[-1]["writer"]["phase"] == phase
        log = capsys.readouterr().err.strip()
        assert json.loads(log.removeprefix("READER_OVERFLOW ")) == frozen[-1]
        clock.ns += 100_000_000  # Recovery must not rewrite failure-time clocks.

    with StreamJournal(
        path,
        PRODUCTS,
        30000,
        35000,
        clock_ms=clock.wall,
        monotonic_ns=clock.mono,
        indexed=True,
        batch_frames=16,
    ) as journal:
        persist = journal._persist

        def blocked_persist(rows, *, pending=False):
            if pending and phase == "journal_callback":
                stall_owner()
            return persist(rows, pending=pending)

        monkeypatch.setattr(journal, "_persist", blocked_persist)
        result = capture(
            journal,
            lambda: socket,
            monotonic=lambda: clock.ns / 1e9,
            duration_ns=clock.mono,
            max_connections=1,
            after_commit=(lambda _: stall_owner()) if phase == "after_commit" else None,
            progress=lambda *args, **kwargs: None,
        )
        assert result["stop"] == "queue_overflow"
        journal.finish()
    report = socket.reader_report()
    assert report["overflow"] == frozen[0]
    assert report["overflow"]["writer"]["frames"] == (
        1 if phase == "journal_callback" else 0
    )
    assert report["overflow"]["queue_depth"] == capacity
    assert (
        report["overflow"]["received"] == capacity + 2
    )  # ACK, queued prefix, rejected frame
    assert report["overflow"]["delivered"] == 1
    assert report["received_not_delivered"] == capacity + 1
    assert result["attempts"][0]["error"] == "socket reader queue reached its frame cap"
    legacy_callback_ms = result["latencies"]["subscriptions"][
        "callback_through_commit"
    ]["max_ms"]
    if phase == "journal_callback":
        assert legacy_callback_ms == pytest.approx(
            (capacity + 1) * interval_ns / 1e6 + 100, abs=0.001
        )
    else:
        # The old callback metric entirely misses a stalled post-commit hook.
        assert legacy_callback_ms == 0
    packets = list(iter_packets(path))
    assert [row["envelope"]["message"]["type"] for row in packets] == [
        "connection_opened",
        "subscriptions",
        "queue_overflow",
    ]
    assert not list(iter_pending_ingress(path))
    with sqlite3.connect(path) as db:
        assert db.execute("PRAGMA quick_check").fetchone() == ("ok",)
    # A caller mutating its report cannot change the retained evidence.
    report["overflow"]["writer"]["phase"] = "changed"
    assert socket.reader_report()["overflow"] == frozen[0]


def test_oversize_is_distinct_from_queue_saturation(monkeypatch, capsys):
    clock = ArrivalClock()
    monkeypatch.setattr("instant_real_indexed_pilot.utc_ms", lambda: 123)
    source = GatedFrames(clock, 0, 0)
    source.recv = lambda: "x" * (MAX_FRAME_BYTES + 1)
    socket = QueuedSocket(source, (TimeoutError,), monotonic_ns=clock.mono)
    try:
        socket.send("{}")
        assert socket.done.wait(5)
        with pytest.raises(QueueOverflowError, match="frame bound"):
            socket.recv()
        snapshot = socket.reader_report()["overflow"]
        assert snapshot["reason"] == "frame_bytes_exceeded"
        assert snapshot["queue_depth"] == 0
        assert snapshot["oldest_queued_age_ms"] is None
        assert snapshot["receipt_ts_ms"] == 123
        assert snapshot["writer"]["elapsed_ms"] == 0
    finally:
        socket.close(timeout=1)
    assert capsys.readouterr().err.count("READER_OVERFLOW ") == 1


def test_subcapacity_burst_drains_in_order_without_loss(monkeypatch):
    clock = ArrivalClock()
    monkeypatch.setattr("instant_real_indexed_pilot.utc_ms", clock.wall)
    source = GatedFrames(clock, 16, 100_000)
    socket = QueuedSocket(
        source, (TimeoutError,), max_frames=16, monotonic_ns=clock.mono
    )
    try:
        socket.send("{}")
        source.release.set()
        assert socket.done.wait(5)
        frames = [socket.recv(), *socket.recv_ready(15)]
        assert [frame.receipt_ns for frame in frames] == [
            1_000_000_000 + i * 100_000 for i in range(1, 17)
        ]
        assert socket.recv() == ""
        assert socket.reader_report() == dict(
            received=16,
            delivered=16,
            received_not_delivered=0,
            sampled_high_water=16,
            overflow=None,
        )
    finally:
        socket.close(timeout=1)
