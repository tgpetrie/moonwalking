"""Bounded, single-writer journal for prospective instant-radar inputs."""

from contextlib import closing
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import sqlite3
from threading import get_ident
import time
from uuid import uuid4

from instant_coverage import MAX_PACKETS, _integer
from instant_delayed_decision import _check_prefix
from instant_input_evidence import InputEvidenceRecorder, _json, _sha


VERSION = "instant-stream-journal-v1-draft"
MAX_RECORD_BYTES = 256 * 1024 * 1024
MAX_FRAME_BYTES = 1024 * 1024
END_EVENTS = {
    "socket_closed": "connection_closed",
    "transport_error": "audit_transport_error",
    "queue_overflow": "queue_overflow",
}

SCHEMA = """
CREATE TABLE segment (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    manifest TEXT NOT NULL,
    status TEXT NOT NULL
);
CREATE TABLE packets (
    receipt_seq INTEGER PRIMARY KEY,
    body TEXT NOT NULL,
    digest TEXT NOT NULL
);
CREATE TABLE publications (
    publication_id TEXT PRIMARY KEY,
    decision_sha256 TEXT NOT NULL,
    body TEXT NOT NULL,
    digest TEXT NOT NULL,
    local_commit_observed_ts_ms INTEGER
);
"""


@dataclass(frozen=True)
class JournalReceipt:
    receipt_seq: int
    receipt_ts_ms: int
    processing_completed_ts_ms: int
    commit_observed_ts_ms: int
    message_type: str
    product_id: str | None
    exchange_time: str | None


@dataclass(frozen=True)
class LocalPublication:
    publication_id: str
    decision_sha256: str
    local_commit_observed_ts_ms: int | None


def _encoded(value):
    body = _json(value)
    return body, _sha(body.encode("utf-8"))


def _decoded(body, digest):
    if _sha(body.encode("utf-8")) != digest:
        raise ValueError("journal record digest mismatch")
    return json.loads(body)


def _read_connection(path):
    return sqlite3.connect(Path(path).resolve().as_uri() + "?mode=rw", uri=True)


def _local_publication(db, publication_id):
    found = db.execute(
        """
        SELECT decision_sha256, local_commit_observed_ts_ms, body, digest
        FROM publications WHERE publication_id = ?
        """,
        (publication_id,),
    ).fetchone()
    if found is None:
        return None
    decision_sha, observed, body, digest = found
    record = _decoded(body, digest)
    actual = _sha(_json(record["decision"]).encode("utf-8"))
    if record["publication_id"] != publication_id or decision_sha != actual:
        raise ValueError("journal publication identity mismatch")
    if observed is not None and observed < record["commit_requested_ts_ms"]:
        raise ValueError("journal publication clock mismatch")
    return LocalPublication(publication_id, decision_sha, observed), record


class StreamJournal:
    """A fresh segment consumes frames from one caller-owned socket at a time.

    The synchronous API provides backpressure at this boundary. Each call must
    finish before the producer dispatches the next frame or lifecycle event.
    """

    def __init__(
        self,
        path,
        products,
        first_cutoff,
        stop_cutoff,
        *,
        max_packets=MAX_PACKETS,
        max_record_bytes=MAX_RECORD_BYTES,
        clock_ms=None,
        monotonic_ns=None,
    ):
        if not 1 <= _integer(max_packets) <= MAX_PACKETS or not (
            1 <= _integer(max_record_bytes) <= MAX_RECORD_BYTES
        ):
            raise ValueError("journal bounds exceed the supported range")
        self.evidence = InputEvidenceRecorder(
            products, first_cutoff, stop_cutoff, clock_ms=clock_ms
        )
        self._monotonic = monotonic_ns or time.monotonic_ns
        self._max_packets = max_packets
        self._max_record_bytes = max_record_bytes
        self._bytes = self._packet_count = self._connection_count = 0
        self._active = None
        self._status = "recording"
        self._owner_thread = get_ident()
        self._segment_id = uuid4().hex

        path = Path(path).resolve()
        with path.open("xb"):
            pass
        self._db = sqlite3.connect(path)
        try:
            mode = self._db.execute("PRAGMA journal_mode = DELETE").fetchone()[0]
            self._db.execute("PRAGMA synchronous = EXTRA")
            sync = self._db.execute("PRAGMA synchronous").fetchone()[0]
            if (mode, sync) != ("delete", 3):
                raise RuntimeError("journal durability settings unavailable")
            self._db.executescript(SCHEMA)
            manifest = dict(
                version=VERSION,
                segment_id=self._segment_id,
                inventory=json.loads(self.evidence.inventory),
                inventory_sha256=self.evidence.inventory_sha256,
                inventory_recorded_ts_ms=self.evidence.inventory_recorded_ts_ms,
                input_implementation_sha256=self.evidence.source_sha256,
                input_contract_sha256=self.evidence.contract_sha256,
                book_implementation_sha256=self.evidence.book.source_sha256,
                book_contract_sha256=self.evidence.book.contract_sha256,
                monitor_implementation_sha256=self.evidence.book.monitor.source_sha256,
                monitor_contract_sha256=self.evidence.book.monitor.contract_sha256,
                journal_implementation_sha256=_sha(
                    Path(__file__).read_text(encoding="utf-8").encode("utf-8")
                ),
                max_packets=max_packets,
                max_record_bytes=max_record_bytes,
                max_frame_bytes=MAX_FRAME_BYTES,
                journal_mode=mode,
                synchronous=sync,
            )
            with self._db:
                self._db.execute(
                    "INSERT INTO segment VALUES (1, ?, 'recording')", (_json(manifest),)
                )
        except BaseException:
            self._db.close()
            raise

    @property
    def packet_count(self):
        return self._packet_count

    @property
    def record_bytes(self):
        return self._bytes

    @property
    def connection_active(self):
        return self._active is not None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def close(self):
        self._db.close()
        self._status = "closed_handle"

    def _writable(self):
        if get_ident() != self._owner_thread:
            raise ValueError("journal writes require the owner thread")
        if self._status != "recording" or self.evidence.failed:
            raise ValueError("journal segment is not writable")

    def _stop(self, status):
        self._status = status
        with self._db:
            self._db.execute("UPDATE segment SET status = ? WHERE id = 1", (status,))

    def _fail(self, status):
        self.evidence.failed = True
        self._stop(status)

    def _check_bytes(self, size):
        if self._bytes + size > self._max_record_bytes:
            self._fail("record_byte_limit")
            raise ValueError("journal record byte limit exceeded")

    def _record(self, connection_id, message, receipt, mono):
        self._writable()
        if self._packet_count >= self._max_packets:
            self._fail("packet_limit")
            raise ValueError("journal packet limit exceeded")
        seq = self._packet_count + 1
        envelope = dict(
            connection_id=connection_id,
            receipt_seq=seq,
            receipt_ts_ms=receipt,
            receipt_monotonic_ns=mono,
            source="ws",
            message=message,
        )
        previous_trade_count = len(self.evidence.trades)
        try:
            self.evidence.ingest(envelope)
            packet = self.evidence.packets[-1]
            trade = (
                asdict(self.evidence.trades[-1])
                if len(self.evidence.trades) > previous_trade_count
                else None
            )
            body, digest = _encoded(
                dict(envelope=envelope, processing=asdict(packet), trade=trade)
            )
        except Exception:
            self._fail("packet_processing_failed")
            raise

        size = len(body.encode("utf-8"))
        self._check_bytes(size)
        try:
            with self._db:
                self._db.execute(
                    "INSERT INTO packets VALUES (?, ?, ?)", (seq, body, digest)
                )
            observed = self.evidence._now()
        except Exception:
            # A commit error may be ambiguous. Only a reopened journal can
            # determine whether the row committed. Stop accepting new input.
            self.evidence.failed = True
            self._status = "write_failed"
            raise

        self._bytes += size
        self._packet_count = seq
        return JournalReceipt(
            seq,
            receipt,
            packet.processing_completed_ts_ms,
            observed,
            message["type"],
            message.get("product_id"),
            message.get("time"),
        )

    def _check_connection(self, connection_id):
        self._writable()
        if self._active is None or connection_id != self._active:
            raise ValueError("frame does not belong to the active connection")

    def open_connection(self):
        """Call once after opening a fresh transport instance."""
        self._writable()
        if self._active is not None:
            raise ValueError("close the active connection before opening another")
        self._connection_count += 1
        connection_id = f"{self._segment_id}/{self._connection_count}"
        self._record(
            connection_id,
            {"type": "connection_opened"},
            self.evidence._now(),
            self._monotonic(),
        )
        self._active = connection_id
        return connection_id

    def receive(self, connection_id, raw):
        """Stamp a frame at callback entry and commit its processing evidence."""
        self._check_connection(connection_id)
        receipt, mono = self.evidence._now(), self._monotonic()
        if not isinstance(raw, (str, bytes)):
            raise TypeError("expected a WebSocket text frame")
        if len(raw) > MAX_FRAME_BYTES:
            self._fail("frame_limit")
            raise ValueError("WebSocket frame byte limit exceeded")
        encoded = (
            raw.encode("utf-8", errors="surrogatepass") if isinstance(raw, str) else raw
        )
        if len(encoded) > MAX_FRAME_BYTES:
            self._fail("frame_limit")
            raise ValueError("WebSocket frame byte limit exceeded")
        try:
            message = json.loads(encoded.decode("utf-8"))
            if not isinstance(message, dict) or not isinstance(
                message.get("type"), str
            ):
                raise ValueError("expected an object with a message type")
            _json(message)
        except (ValueError, RecursionError):
            self._record(
                connection_id,
                dict(
                    type="audit_parse_error",
                    frame_bytes=len(encoded),
                    frame_sha256=_sha(encoded),
                ),
                receipt,
                mono,
            )
            self._active = None
            raise ValueError("invalid WebSocket frame; reopen the connection") from None
        result = self._record(connection_id, message, receipt, mono)
        if message["type"] in ("error", "queue_overflow", "connection_closed") or (
            message["type"].startswith("audit_")
        ):
            self._active = None
        return result

    def end_connection(self, connection_id, *, reason="socket_closed"):
        self._check_connection(connection_id)
        if reason not in END_EVENTS:
            raise ValueError("unknown connection end reason")
        receipt = self._record(
            connection_id,
            {"type": END_EVENTS[reason]},
            self.evidence._now(),
            self._monotonic(),
        )
        self._active = None
        return receipt

    def finish(self):
        """Close this segment explicitly after its last socket is closed."""
        self._writable()
        if self._active is not None:
            raise ValueError("close the active connection before finishing")
        self._stop("finished")

    def _acknowledge(self, publication_id, observed):
        with self._db:
            self._db.execute(
                """
                UPDATE publications SET local_commit_observed_ts_ms = ?
                WHERE publication_id = ? AND local_commit_observed_ts_ms IS NULL
                """,
                (observed, publication_id),
            )

    def append_publication(self, publication_id, decision):
        """Commit a local outbox entry and then persist its commit observation."""
        self._writable()
        if not isinstance(publication_id, str) or not 1 <= len(publication_id) <= 128:
            raise ValueError("a bounded publication ID is required")
        decision_sha = decision.sha256
        existing = _local_publication(self._db, publication_id)
        if existing is not None:
            receipt, _ = existing
            if receipt.decision_sha256 != decision_sha:
                raise ValueError("publication ID already refers to another decision")
            return receipt
        _check_prefix(self.evidence, decision, json.loads(decision.feature_json))
        requested = self.evidence._now()
        if requested < decision.decision_completed_ts_ms:
            raise ValueError("decision preparation has not completed")
        body, digest = _encoded(
            dict(
                publication_id=publication_id,
                decision=asdict(decision),
                commit_requested_ts_ms=requested,
            )
        )
        size = len(body.encode("utf-8"))
        self._check_bytes(size)
        try:
            with self._db:
                self._db.execute(
                    "INSERT INTO publications VALUES (?, ?, ?, ?, NULL)",
                    (publication_id, decision_sha, body, digest),
                )
            self._bytes += size
            observed = self.evidence._now()
            self._acknowledge(publication_id, observed)
        except Exception:
            self.evidence.failed = True
            self._status = "write_failed"
            raise
        return LocalPublication(publication_id, decision_sha, observed)


def read_segment(path):
    """Recover committed metadata and counts, including an unfinished prefix."""
    with closing(_read_connection(path)) as db:
        body, status, packets, publications = db.execute(
            """
            SELECT manifest, status, (SELECT count(*) FROM packets),
                (SELECT count(*) FROM publications) FROM segment WHERE id = 1
            """
        ).fetchone()
        manifest = json.loads(body)
        if manifest["version"] != VERSION:
            raise ValueError("unsupported journal version")
        return dict(
            manifest=manifest, status=status, packets=packets, publications=publications
        )


def iter_packets(path):
    """Yield committed envelopes and original processing evidence in order."""
    with closing(_read_connection(path)) as db:
        for expected, (seq, body, digest) in enumerate(
            db.execute(
                "SELECT receipt_seq, body, digest FROM packets ORDER BY receipt_seq"
            ),
            1,
        ):
            row = _decoded(body, digest)
            if (
                not expected
                == seq
                == row["envelope"]["receipt_seq"]
                == row["processing"]["receipt_seq"]
            ):
                raise ValueError("journal packet sequence mismatch")
            yield row


def read_local_publication(path, publication_id):
    """Recover a local entry and its possibly absent commit observation."""
    with closing(_read_connection(path)) as db:
        return _local_publication(db, publication_id)
