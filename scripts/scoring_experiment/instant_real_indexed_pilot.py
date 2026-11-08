"""Run the real indexed diagnostic and observe the outbox from another process."""

import argparse
from collections import Counter
from contextlib import closing
from datetime import datetime, timezone
import json
from pathlib import Path
from queue import Empty, Full, Queue
import sqlite3
import subprocess
import sys
from threading import Event, Thread
import time

from instant_coverage import WARMUP_PACKET_LIMIT
from instant_delayed_decision import prepare_decision
from instant_input_evidence import DIRECTIONS, GRID_MS, _file_sha
from instant_source_pilot import (
    CHANNELS,
    DURATION_S,
    LATER_ASOF_MS,
    PRODUCTS,
    URL,
    WARMUP_MS,
    QueueOverflowError,
    ReceivedFrame,
    _coverage,
    _summary,
    capture,
    utc_ms,
)
from instant_stream_journal import (
    MAX_FRAME_BYTES,
    StreamJournal,
    _local_publication,
    read_segment,
)


VERSION = "instant-real-indexed-pilot-v1"
QUEUE_CAPACITY = 128
MAX_QUEUE_CAPACITY = 256
COHORTS = 10
POLL_S = 0.025


class QueuedSocket:
    """One socket reader timestamps frames; the owner thread alone writes."""

    def __init__(self, socket, timeout_errors, *, max_frames=QUEUE_CAPACITY):
        if type(max_frames) is not int or not 1 <= max_frames <= MAX_QUEUE_CAPACITY:
            raise ValueError("reader queue size outside the supported range")
        self.socket = socket
        self.timeout_errors = timeout_errors
        self.queue = Queue(maxsize=max_frames)
        self.stopping, self.done = Event(), Event()
        self.thread = Thread(
            target=self._read, name="coinbase-diagnostic-reader", daemon=True
        )
        self.failure = None
        self.received = self.delivered = self.high_water = 0

    def send(self, raw):
        self.socket.send(raw)
        self.thread.start()

    def _read(self):
        try:
            while not self.stopping.is_set():
                try:
                    raw = self.socket.recv()
                except self.timeout_errors:
                    continue
                wall, duration = utc_ms(), time.perf_counter_ns()
                if raw in ("", b""):
                    break
                self.received += 1
                if len(raw) > MAX_FRAME_BYTES or (
                    isinstance(raw, str)
                    and len(raw.encode("utf-8", errors="surrogatepass"))
                    > MAX_FRAME_BYTES
                ):
                    raise QueueOverflowError(
                        "reader frame exceeded the journal frame bound"
                    )
                try:
                    self.queue.put_nowait(ReceivedFrame(raw, wall, duration))
                except Full as exc:
                    raise QueueOverflowError(
                        "socket reader queue reached its frame cap"
                    ) from exc
                self.high_water = max(self.high_water, self.queue.qsize())
        except Exception as exc:
            if not self.stopping.is_set():
                self.failure = exc
        finally:
            self.done.set()

    def recv(self):
        if isinstance(self.failure, QueueOverflowError):
            raise self.failure
        try:
            frame = self.queue.get(timeout=0.5)
        except Empty as exc:
            if self.done.is_set():
                if self.failure is not None:
                    raise self.failure
                return ""
            raise TimeoutError("waiting for socket reader") from exc
        self.delivered += 1
        return frame

    def close(self, timeout):
        self.stopping.set()
        if self.thread.ident is not None:
            self.thread.join(2)
        if self.thread.is_alive():
            try:
                self.socket.abort()
            except OSError:
                pass
            self.thread.join(2)
        self.socket.close(timeout=timeout)


def _observe(path, destination, stop_file):
    """A separate process observes only acknowledged, digest-checked rows."""
    seen = set()
    until = time.monotonic() + 100
    with (
        closing(
            sqlite3.connect(
                path.resolve().as_uri() + "?mode=ro", uri=True, timeout=0.04
            )
        ) as db,
        destination.open("x", encoding="utf-8") as stream,
    ):
        while time.monotonic() < until:
            try:
                rows = db.execute(
                    "SELECT publication_id FROM publications WHERE local_commit_observed_ts_ms IS NOT NULL"
                ).fetchall()
                for (pub,) in rows:
                    if pub in seen:
                        continue
                    receipt, _ = _local_publication(db, pub)
                    seen_ts_ms = utc_ms()
                    record = dict(
                        publication_id=pub,
                        decision_sha256=receipt.decision_sha256,
                        commit_observed_ts_ms=receipt.local_commit_observed_ts_ms,
                        consumer_seen_ts_ms=seen_ts_ms,
                    )
                    stream.write(json.dumps(record, separators=(",", ":")) + "\n")
                    stream.flush()
                    seen.add(pub)
            except sqlite3.OperationalError as exc:
                if "locked" not in str(exc):
                    raise
            if stop_file.exists():
                break
            time.sleep(POLL_S)


class DiagnosticCohorts:
    def __init__(self, journal, out):
        self.journal = journal
        self.out = out
        self.next_cutoff = None
        self.observer = None
        self.rows = []
        self.elapsed = []

    def after_commit(self):
        if self.next_cutoff is None:
            ack = self.journal.evidence.packets[-1].receipt_ts_ms
            self.next_cutoff = ((ack + WARMUP_MS + GRID_MS - 1) // GRID_MS) * GRID_MS
        if len(self.elapsed) == COHORTS:
            return
        now = utc_ms()
        if self.observer is None and now >= self.next_cutoff - GRID_MS:
            self.observer = subprocess.Popen(
                [
                    sys.executable,
                    str(Path(__file__).resolve()),
                    "--observe",
                    str(self.out),
                ],
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        asof = self.next_cutoff + LATER_ASOF_MS
        if now < asof:
            return
        # A clock passing the planned as-of can coexist with queued packets.
        # Use the declared knowledge time and leave unavailable features null.
        started = time.perf_counter_ns()
        for product in PRODUCTS:
            for direction in DIRECTIONS:
                begin = time.perf_counter_ns()
                snapshot = prepare_decision(
                    self.journal.evidence,
                    product,
                    self.next_cutoff,
                    direction,
                    asof=asof,
                )
                prepared_ns = time.perf_counter_ns()
                pub = f"diagnostic-{self.next_cutoff}-{product}-{direction}"
                receipt = self.journal.append_publication(pub, snapshot)
                committed_ns = time.perf_counter_ns()
                features = json.loads(snapshot.feature_json)
                self.rows.append(
                    dict(
                        publication_id=pub,
                        decision_sha256=receipt.decision_sha256,
                        product_id=product,
                        direction=direction,
                        cutoff_ts_ms=self.next_cutoff,
                        knowledge_asof_ts_ms=asof,
                        cohort_start_ts_ms=now,
                        decision_completed_ts_ms=snapshot.decision_completed_ts_ms,
                        commit_observed_ts_ms=receipt.local_commit_observed_ts_ms,
                        prepare_ms=(prepared_ns - begin) / 1000000,
                        outbox_ms=(committed_ns - prepared_ns) / 1000000,
                        readiness={
                            name: item.get("reason", "ready")
                            for name, item in features["features"].items()
                        },
                        evidence_available_ts_ms={
                            name: item.get("evidence_available_ts_ms")
                            for name, item in features["features"].items()
                        },
                        baseline={
                            name: features["baseline"][name].get("reason", "ready")
                            for name in ("volatility", "pace")
                        },
                    )
                )
        self.elapsed.append((time.perf_counter_ns() - started) / 1000000)
        self.next_cutoff += GRID_MS
        print(
            f"Committed live-source diagnostic cohort {len(self.elapsed)} of {COHORTS}.",
            flush=True,
        )

    def stop_observer(self):
        if self.observer is None:
            return None
        (self.out / "observer.stop").touch()
        try:
            return self.observer.wait(timeout=6)
        except subprocess.TimeoutExpired:
            self.observer.terminate()
            return self.observer.wait(timeout=6)


def _observation_report(path, rows):
    data = path / "observed.jsonl"
    lines = data.read_text(encoding="utf-8").splitlines() if data.is_file() else []
    prepared = {row["publication_id"]: row for row in rows}
    commit_to_seen, cutoff_to_seen = [], []
    discrepancies = Counter()
    observed_ids = set()
    for line in lines:
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            discrepancies["unreadable_observation"] += 1
            continue
        pub = entry["publication_id"]
        if pub in observed_ids:
            discrepancies["duplicate"] += 1
            continue
        observed_ids.add(pub)
        row = prepared.get(pub)
        if row is None or any(
            entry[key] != row[key]
            for key in ("decision_sha256", "commit_observed_ts_ms")
        ):
            discrepancies["identity_or_receipt_mismatch"] += 1
            continue
        if entry["consumer_seen_ts_ms"] < entry["commit_observed_ts_ms"]:
            discrepancies["wall_clock_regression"] += 1
            continue
        commit_to_seen.append(
            entry["consumer_seen_ts_ms"] - entry["commit_observed_ts_ms"]
        )
        cutoff_to_seen.append(entry["consumer_seen_ts_ms"] - row["cutoff_ts_ms"])
        row["consumer_seen_ts_ms"] = entry["consumer_seen_ts_ms"]
    return dict(
        reader_poll_ms=POLL_S * 1000,
        commit_observed_to_reader_seen=_summary(commit_to_seen),
        cutoff_to_reader_seen=_summary(cutoff_to_seen),
        missing_or_invalid=len(rows) - len(commit_to_seen),
        discrepancies=dict(discrepancies),
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    paths = parser.add_mutually_exclusive_group(required=True)
    paths.add_argument("--out-dir", type=Path)
    paths.add_argument("--observe", type=Path)
    args = parser.parse_args()
    if args.observe is not None:
        out = args.observe.resolve()
        _observe(out / "capture.sqlite", out / "observed.jsonl", out / "observer.stop")
        return

    import websocket

    out = args.out_dir.resolve()
    out.mkdir(parents=True, exist_ok=False)
    db = out / "capture.sqlite"
    first = (utc_ms() // GRID_MS + 1) * GRID_MS
    plan = dict(
        version=VERSION,
        implementation_commit=subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True
        ).strip(),
        started_utc=datetime.now(timezone.utc).isoformat(),
        endpoint=URL,
        products=PRODUCTS,
        channels=CHANNELS,
        duration_s=DURATION_S,
        packet_stop=WARMUP_PACKET_LIMIT - 10,
        max_reader_queue_frames=QUEUE_CAPACITY,
        cohort_evidence_offset_ms=LATER_ASOF_MS,
        local_consumer_poll_ms=POLL_S * 1000,
    )
    (out / "PLAN.json").write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
    sockets = []

    def connect():
        ws = websocket.create_connection(URL, timeout=5, enable_multithread=True)
        ws.settimeout(1)
        socket = QueuedSocket(ws, (websocket.WebSocketTimeoutException,))
        sockets.append(socket)
        return socket

    with StreamJournal(
        db,
        PRODUCTS,
        first,
        first + 4320000,
        max_packets=WARMUP_PACKET_LIMIT,
        indexed=True,
        monotonic_ns=time.perf_counter_ns,
    ) as journal:
        cohorts = DiagnosticCohorts(journal, out)
        try:
            result = capture(
                journal,
                connect,
                timeout_errors=(TimeoutError,),
                transport_errors=(OSError, websocket.WebSocketException),
                packet_stop=WARMUP_PACKET_LIMIT - 10,
                after_commit=cohorts.after_commit,
                max_connections=1,
            )
        finally:
            observer_exit = cohorts.stop_observer()
        result["coverage"] = None
        if not journal.evidence.failed:
            journal.finish()
            if (
                result["first_ack_ts_ms"] is not None
                and result["last_reader_receipt_ts_ms"] is not None
            ):
                result["coverage"] = _coverage(
                    journal.evidence,
                    result["first_ack_ts_ms"],
                    result["last_reader_receipt_ts_ms"],
                )
    result.update(plan)
    result["segment"] = read_segment(db)
    result["journal_sha256"] = _file_sha(db)
    result["journal_bytes"] = db.stat().st_size
    result["reader"] = [
        dict(
            received=socket.received,
            delivered=socket.delivered,
            sampled_high_water=socket.high_water,
        )
        for socket in sockets
    ]
    result["diagnostic_cohorts"] = dict(planned=COHORTS, complete=len(cohorts.elapsed))
    result["cohort_serial"] = _summary(cohorts.elapsed)
    result["decision_preparation"] = _summary(
        [row["prepare_ms"] for row in cohorts.rows]
    )
    result["outbox_commit"] = _summary([row["outbox_ms"] for row in cohorts.rows])
    result["local_reader"] = _observation_report(out, cohorts.rows)
    result["local_reader"]["process_exit_code"] = observer_exit
    result["diagnostic_rows"] = cohorts.rows
    result["feed_gate_pass"] = False
    result["fitting_allowed"] = False
    result["public_delivery_measured"] = False
    (out / "REPORT.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )
    print(
        f"Indexed real pilot stopped: {result['stop']}. Report at {out / 'REPORT.json'}",
        flush=True,
    )


if __name__ == "__main__":
    main()
