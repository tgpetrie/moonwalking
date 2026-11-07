"""Synthetic streaming, transactional write and restart probes."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
import json
from pathlib import Path
import sqlite3
import subprocess
import sys

import pytest

from test_instant_input_evidence_review import BTC, COIN
from instant_delayed_decision import prepare_decision
from instant_stream_journal import (
    MAX_FRAME_BYTES,
    StreamJournal,
    iter_packets,
    read_local_publication,
    read_segment,
)


class Clock:
    def __init__(self):
        self.now = 0
        self.steps = []

    def __call__(self):
        if self.steps:
            self.now = self.steps.pop(0)
        return self.now

    def mono(self):
        return self.now * 1000000


def journal(path, clock, **bounds):
    return StreamJournal(
        path,
        [COIN, BTC],
        30000,
        35000,
        clock_ms=clock,
        monotonic_ns=clock.mono,
        **bounds,
    )


def send(stream, connection, **fields):
    return stream.receive(connection, json.dumps(fields))


def subscribe(stream, connection):
    send(
        stream,
        connection,
        type="subscriptions",
        channels=[
            dict(name=c, product_ids=[COIN, BTC])
            for c in ("matches", "heartbeat", "level2_batch")
        ],
    )


def test_reconnect_allocates_real_lifecycle_ids_and_persists_first_trade(tmp_path):
    path = tmp_path / "capture.sqlite"
    clock = Clock()
    with journal(path, clock) as stream:
        first = stream.open_connection()
        subscribe(stream, first)
        clock.now = 1000
        send(stream, first, type="heartbeat", product_id=COIN, last_trade_id=9)
        clock.now = 2000
        message = dict(
            type="match",
            product_id=COIN,
            trade_id=10,
            price="100",
            size="2",
            side="sell",
        )
        result = send(stream, first, **message)
        stream.end_connection(first, reason="queue_overflow")
        second = stream.open_connection()
        assert first != second
        with pytest.raises(ValueError, match="active connection"):
            send(stream, first, **message)
        subscribe(stream, second)
        duplicate = send(stream, second, **message)
        stream.end_connection(second)
        stream.finish()
        assert (
            result.receipt_ts_ms
            <= result.processing_completed_ts_ms
            <= result.commit_observed_ts_ms
        )
    rows = list(iter_packets(path))
    original, repeated = rows[result.receipt_seq - 1], rows[duplicate.receipt_seq - 1]
    assert original["trade"]["connection_id"] == first
    assert original["trade"]["taker_side"] == "buy"
    assert original["processing"]["available_ts_ms"] == 2001
    assert repeated["trade"] is None
    assert repeated["envelope"]["connection_id"] == second
    assert any(r["envelope"]["message"]["type"] == "queue_overflow" for r in rows)
    report = read_segment(path)
    assert report["status"] == "finished"
    assert report["packets"] == len(rows)
    assert report["manifest"]["synchronous"] == 3
    with pytest.raises(FileExistsError):
        journal(path, clock)


@pytest.mark.parametrize(
    "frame", [b"\xff", "[]", '{"type":"heartbeat","last_trade_id":NaN}']
)
def test_invalid_frame_leaves_a_durable_barrier_and_requires_a_new_connection(
    tmp_path, frame
):
    path = tmp_path / "capture.sqlite"
    with journal(path, Clock()) as stream:
        first = stream.open_connection()
        with pytest.raises(ValueError, match="invalid WebSocket frame"):
            stream.receive(first, frame)
        with pytest.raises(ValueError, match="active connection"):
            send(stream, first, type="heartbeat")
        second = stream.open_connection()
        assert second != first
    packets = list(iter_packets(path))
    marker = packets[1]["envelope"]["message"]
    assert marker["type"] == "audit_parse_error"
    assert marker["frame_bytes"] > 0
    assert len(marker["frame_sha256"]) == 64
    assert read_segment(path)["status"] == "recording"


@pytest.mark.parametrize(
    ("bounds", "status", "expected"),
    [
        ({"max_packets": 1}, "packet_limit", 1),
        ({"max_record_bytes": 1}, "record_byte_limit", 0),
    ],
)
def test_journal_limits_keep_only_committed_prefix(tmp_path, bounds, status, expected):
    path = tmp_path / "capture.sqlite"
    with journal(path, Clock(), **bounds) as stream:
        with pytest.raises(ValueError, match="limit exceeded"):
            connection = stream.open_connection()
            send(stream, connection, type="ticker")
        with pytest.raises(ValueError, match="not writable"):
            stream.open_connection()
        assert stream.evidence.failed
    recovered = read_segment(path)
    assert recovered["status"] == status
    assert recovered["packets"] == expected
    assert len(list(iter_packets(path))) == expected


def test_frame_bound_and_failed_packet_are_visible(tmp_path):
    path = tmp_path / "oversize.sqlite"
    with journal(path, Clock()) as stream:
        connection = stream.open_connection()
        with pytest.raises(ValueError, match="frame byte limit"):
            stream.receive(connection, b" " * (MAX_FRAME_BYTES + 1))
    assert read_segment(path)["status"] == "frame_limit"

    path = tmp_path / "invalid-match.sqlite"
    with journal(path, Clock()) as stream:
        connection = stream.open_connection()
        with pytest.raises(KeyError, match="trade_id"):
            send(stream, connection, type="match", product_id=COIN)
        assert stream.evidence.failed
    assert read_segment(path)["status"] == "packet_processing_failed"
    assert len(list(iter_packets(path))) == 1


def test_failed_transaction_cannot_acknowledge_an_uncommitted_packet(tmp_path):
    path = tmp_path / "capture.sqlite"
    with journal(path, Clock()) as stream:
        connection = stream.open_connection()
        stream._db.execute(
            """
            CREATE TRIGGER refuse_packets BEFORE INSERT ON packets
            BEGIN SELECT RAISE(ABORT, 'simulated disk write failure'); END
            """
        )
        with pytest.raises(
            sqlite3.IntegrityError, match="simulated disk write failure"
        ):
            send(stream, connection, type="ticker")
        assert stream.evidence.failed
        with pytest.raises(ValueError, match="not writable"):
            stream.end_connection(connection)
    assert read_segment(path)["status"] == "recording"
    assert len(list(iter_packets(path))) == 1


def test_local_publication_is_reopenable_and_idempotent(tmp_path, monkeypatch):
    path = tmp_path / "capture.sqlite"
    clock = Clock()
    with journal(path, clock) as stream:
        connection = stream.open_connection()
        clock.now = 30000
        decision = prepare_decision(stream.evidence, COIN, 30000, "up", asof=30000)
        other = prepare_decision(stream.evidence, COIN, 30000, "down", asof=30000)
        original_ack = stream._acknowledge

        def observe_pending(publication_id, observed):
            receipt, record = read_local_publication(path, publication_id)
            assert receipt.local_commit_observed_ts_ms is None
            assert record["decision"] == asdict(decision)
            original_ack(publication_id, observed)

        monkeypatch.setattr(stream, "_acknowledge", observe_pending)
        clock.steps = [30000, 30008]
        published = stream.append_publication("local-1", decision)
        clock.now += 7
        assert stream.append_publication("local-1", decision) == published
        with pytest.raises(ValueError, match="another decision"):
            stream.append_publication("local-1", other)
        stream.end_connection(connection)
        stream.finish()
    assert published.local_commit_observed_ts_ms == 30008
    assert read_local_publication(path, "local-1")[0] == published
    assert read_segment(path)["publications"] == 1
    assert read_local_publication(path, "missing") is None


def test_hard_exit_rolls_back_uncommitted_publication_observation(tmp_path):
    path = tmp_path / "interrupted.sqlite"
    source = str(Path(__file__).resolve().parents[1] / "scripts" / "scoring_experiment")
    child = """
import os
import sys
sys.path.insert(0, sys.argv[1])
from instant_delayed_decision import prepare_decision
from instant_stream_journal import StreamJournal
with StreamJournal(sys.argv[2], ['ALT-USD', 'BTC-USD'], 30000, 35000, clock_ms=lambda: 30000) as journal:
    journal.open_connection()
    decision = prepare_decision(journal.evidence, 'ALT-USD', 30000, 'up', asof=30000)
    def interrupt(publication_id, observed):
        journal._db.execute(
            'UPDATE publications SET local_commit_observed_ts_ms = ? WHERE publication_id = ?',
            (observed, publication_id),
        )
        os._exit(23)
    journal._acknowledge = interrupt
    journal.append_publication('interrupted', decision)
"""
    result = subprocess.run(
        [sys.executable, "-c", child, source, str(path)],
        capture_output=True,
        timeout=30,
    )
    assert result.returncode == 23, result.stderr.decode()
    assert read_segment(path)["status"] == "recording"
    assert len(list(iter_packets(path))) == 1
    receipt, _ = read_local_publication(path, "interrupted")
    assert receipt.local_commit_observed_ts_ms is None
    with journal(tmp_path / "new.sqlite", Clock()) as stream:
        first = next(iter_packets(path))["envelope"]["connection_id"]
        assert stream.open_connection() != first


def test_archive_reader_detects_packet_damage(tmp_path):
    path = tmp_path / "capture.sqlite"
    with journal(path, Clock()) as stream:
        stream.open_connection()
    db = sqlite3.connect(path)
    try:
        with db:
            db.execute("UPDATE packets SET body = '{}'")
    finally:
        db.close()
    with pytest.raises(ValueError, match="digest mismatch"):
        list(iter_packets(path))


def test_foreign_writer_cannot_mutate_the_in_memory_or_committed_prefix(tmp_path):
    path = tmp_path / "capture.sqlite"
    with journal(path, Clock()) as stream:
        connection = stream.open_connection()
        with ThreadPoolExecutor(max_workers=1) as workers:
            write = workers.submit(send, stream, connection, type="ticker")
            with pytest.raises(ValueError, match="owner thread"):
                write.result()
        assert len(stream.evidence.packets) == 1
        assert send(stream, connection, type="ticker").receipt_seq == 2
    assert read_segment(path)["packets"] == 2


def test_explicit_warmup_capacity_reaches_the_monitor_without_changing_legacy_cap(
    tmp_path, monkeypatch
):
    import instant_coverage

    clock = Clock()
    with (
        journal(
            tmp_path / "extended.sqlite",
            clock,
            max_packets=instant_coverage.WARMUP_PACKET_LIMIT,
        ) as extended,
        journal(tmp_path / "ordinary.sqlite", clock) as ordinary,
    ):
        direct = instant_coverage.CoverageMonitor([COIN])
        monkeypatch.setattr(instant_coverage, "MAX_PACKETS", 1)
        connection = extended.open_connection()
        send(extended, connection, type="ticker")
        assert extended.evidence.book.monitor.packet_count == 2
        assert ordinary.evidence.book.monitor._packet_limit == 100000
        assert direct._packet_limit is None
    report = read_segment(tmp_path / "extended.sqlite")
    assert report["manifest"]["max_packets"] == 250000
    with pytest.raises(ValueError, match="bounds"):
        journal(tmp_path / "oversize.sqlite", clock, max_packets=250001)
