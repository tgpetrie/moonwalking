"""Offline reader termination/queued-prefix probes; no live feed or DNS requests."""

import json
import sqlite3

import pytest
import websocket

from test_instant_source_pilot import acknowledgement
from test_instant_stream_journal import Clock
from instant_real_indexed_pilot import QueuedSocket
from instant_source_pilot import PRODUCTS, WARMUP_MS, capture
from instant_stream_journal import (
    StreamJournal,
    iter_packets,
    iter_pending_ingress,
    read_segment,
)


class TerminalSource:
    def __init__(self, clock, messages):
        self.clock = clock
        self.messages = iter(messages)
        self.closed = False
        self.terminal_ms = None

    def send(self, raw):
        assert json.loads(raw)["type"] == "subscribe"

    def recv(self):
        self.clock.now += 10
        message = next(self.messages, "")
        if isinstance(message, Exception):
            if not isinstance(message, websocket.WebSocketTimeoutException):
                self.terminal_ms = self.clock.now
            raise message
        if message == "":
            self.terminal_ms = self.clock.now
            return ""
        return json.dumps(message)

    def close(self, timeout):
        self.closed = True


class FinishedReader(QueuedSocket):
    def send(self, raw):
        super().send(raw)
        # Deterministically observe the queued prefix and terminal state before
        # the owner can dequeue anything; no scheduler-speed assumptions.
        assert self.done.wait(5), "synthetic reader did not terminate"


@pytest.mark.parametrize("batch_frames", [1, 16])
@pytest.mark.parametrize(
    "ending, expected_stop, expected_marker",
    [
        (
            websocket.WebSocketConnectionClosedException(
                "Connection to remote host was lost."
            ),
            "transport_error",
            "audit_transport_error",
        ),
        (
            ConnectionResetError(10054, "connection reset"),
            "transport_error",
            "audit_transport_error",
        ),
        ("", "remote_close", "connection_closed"),
    ],
    ids=["websocket-lost", "socket-reset", "empty-return"],
)
def test_transport_termination_drains_exact_prefix_then_preserves_barrier(
    tmp_path, monkeypatch, capsys, batch_frames, ending, expected_stop, expected_marker
):
    clock = Clock()
    monkeypatch.setattr("instant_real_indexed_pilot.utc_ms", clock)
    messages = [acknowledgement()] + [
        dict(type="ticker", product_id="BTC-USD", diagnostic_index=i) for i in range(32)
    ]
    source = TerminalSource(clock, [*messages, ending])
    socket = FinishedReader(
        source,
        (websocket.WebSocketTimeoutException,),
        max_frames=256,
        monotonic_ns=clock.mono,
    )
    path = tmp_path / "capture.sqlite"
    connections = []

    def connect():
        connections.append(True)
        return socket

    def after_commit(_):
        # A delayed owner sees the error later than the actual reader detects it.
        clock.now += 100

    with StreamJournal(
        path,
        PRODUCTS,
        30000,
        35000,
        clock_ms=clock,
        monotonic_ns=clock.mono,
        indexed=True,
        batch_frames=batch_frames,
    ) as journal:
        result = capture(
            journal,
            connect,
            monotonic=lambda: clock.now / 1000,
            duration_ns=clock.mono,
            timeout_errors=(TimeoutError,),
            transport_errors=(OSError, websocket.WebSocketException),
            max_connections=1,
            after_commit=after_commit,
            progress=lambda *args, **kwargs: None,
        )
        journal.finish()
    assert result["stop"] == expected_stop
    assert len(connections) == 1
    attempt = result["attempts"][0]
    if isinstance(ending, Exception):
        assert socket.failure is ending
        assert attempt["error"] == str(ending)
        # This is a diagnostic limitation, not evidence of a new connection bug:
        # the reader keeps an exception object but the report only saves text.
        assert "error_type" not in attempt and "errno" not in attempt
    else:
        assert socket.failure is None and "error" not in attempt
    assert socket.reader_report() == dict(
        received=33,
        delivered=33,
        received_not_delivered=0,
        sampled_high_water=33,
        overflow=None,
    )
    packets = list(iter_packets(path))
    assert [row["envelope"]["message"] for row in packets[1:-1]] == json.loads(
        json.dumps(messages)
    )
    assert packets[-1]["envelope"]["message"] == {"type": expected_marker}
    assert packets[-1]["envelope"]["receipt_ts_ms"] > source.terminal_ms
    assert result["last_reader_receipt_ts_ms"] == 330
    assert result["last_reader_receipt_ts_ms"] - result["first_ack_ts_ms"] < WARMUP_MS
    assert len({row["envelope"]["connection_id"] for row in packets}) == 1
    assert read_segment(path)["status"] == "finished"
    assert not list(iter_pending_ingress(path))
    with sqlite3.connect(path) as db:
        assert db.execute("PRAGMA quick_check").fetchone() == ("ok",)
        assert db.execute("SELECT count(*) FROM publications").fetchone() == (0,)
    assert source.closed
    # Transport loss has no immediate stderr event in the current reader.
    assert capsys.readouterr().err == ""


def test_socket_timeout_is_retried_without_poisoning_later_data(monkeypatch):
    clock = Clock()
    monkeypatch.setattr("instant_real_indexed_pilot.utc_ms", clock)
    source = TerminalSource(
        clock, [websocket.WebSocketTimeoutException("idle"), acknowledgement(), ""]
    )
    socket = FinishedReader(
        source, (websocket.WebSocketTimeoutException,), monotonic_ns=clock.mono
    )
    try:
        socket.send('{"type":"subscribe"}')
        assert socket.failure is None
        assert json.loads(socket.recv().raw) == json.loads(
            json.dumps(acknowledgement())
        )
        assert socket.recv() == ""
        assert socket.reader_report()["received"] == 1
    finally:
        socket.close(timeout=1)


def test_immediate_disconnect_is_rethrown_after_empty_queue_without_new_frames(
    monkeypatch,
):
    clock = Clock()
    monkeypatch.setattr("instant_real_indexed_pilot.utc_ms", clock)
    ending = websocket.WebSocketConnectionClosedException(
        "Connection to remote host was lost."
    )
    socket = FinishedReader(
        TerminalSource(clock, [ending]), (), monotonic_ns=clock.mono
    )
    try:
        socket.send('{"type":"subscribe"}')
        with pytest.raises(websocket.WebSocketConnectionClosedException) as caught:
            socket.recv()
        assert caught.value is ending
        assert socket.recv_ready(16) == []
        assert socket.reader_report()["received"] == 0
        assert socket.reader_report()["overflow"] is None
    finally:
        socket.close(timeout=1)


@pytest.mark.parametrize(
    "wire_bytes", [b"", b"\x88\x02\x03\xe8"], ids=["stream-eof", "websocket-close-1000"]
)
def test_pinned_websocket_library_distinguishes_stream_eof_and_close_frame(wire_bytes):
    class Wire:
        def __init__(self, data):
            self.data = data

        def recv(self, size):
            result, self.data = self.data[:size], self.data[size:]
            return result

        def send(self, data):
            return len(data)

        def gettimeout(self):
            return 1

        def close(self):
            pass

    ws = websocket.WebSocket()
    ws.sock = Wire(wire_bytes)
    ws.connected = True
    try:
        if wire_bytes:
            # recv() intentionally discards the protocol close code/reason.
            assert ws.recv() == ""
        else:
            with pytest.raises(
                websocket.WebSocketConnectionClosedException,
                match="Connection to remote host was lost",
            ):
                ws.recv()
    finally:
        ws.shutdown()
