"""Run the real indexed diagnostic and observe the outbox from another process."""

import argparse
from collections import Counter, deque
from contextlib import closing, contextmanager
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
from queue import Empty, Full, Queue
import sqlite3
import subprocess
import sys
from threading import Event, Lock, Thread
import time

from instant_coverage import TIMING_PACKET_LIMIT, WARMUP_PACKET_LIMIT
from instant_delayed_decision import prepare_decision
from instant_delayed_eligibility import LocalDelivery, assess_cohort
from instant_input_evidence import DIRECTIONS, GRID_MS, _file_sha
from instant_source_pilot import (
    CHANNELS,
    DURATION_S,
    LATER_ASOF_MS,
    PRODUCTS,
    SOFT_RECORD_BYTES,
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
    MAX_BATCH_FRAMES,
    MAX_FRAME_BYTES,
    MAX_RECORD_BYTES,
    TIMING_RECORD_LIMIT_BYTES,
    StreamJournal,
    _local_publication,
    iter_pending_ingress,
    read_segment,
)


VERSION = "instant-real-indexed-pilot-v1"
QUEUE_CAPACITY = 128
MAX_QUEUE_CAPACITY = 256
DEFAULT_PROFILE = "single-128"
TIMING_PROFILE = "eligibility-timing-256"
TIMING_VERSION = "instant-eligibility-timing-pilot-v1"
TIMING_PRODUCTS = PRODUCTS + ("LINK-USD", "AVAX-USD")
TIMING_STEP_MS = 10000
TIMING_SOFT_RECORD_BYTES = 480 * 1024 * 1024
TIMING_DEADLINES_MS = {1500: 2500, LATER_ASOF_MS: 6000}
UTC_WINDOWS = {"asia": (0, 6), "europe": (7, 13), "us": (14, 20)}
PROFILES = {
    DEFAULT_PROFILE: (QUEUE_CAPACITY, 1),
    "batched-256": (MAX_QUEUE_CAPACITY, MAX_BATCH_FRAMES),
    TIMING_PROFILE: (MAX_QUEUE_CAPACITY, MAX_BATCH_FRAMES),
}
COHORTS = 10
POLL_S = 0.025
MAX_OBSERVER_S = 240


class QueuedSocket:
    """One socket reader timestamps frames; the owner thread alone writes."""

    def __init__(
        self,
        socket,
        timeout_errors,
        *,
        max_frames=QUEUE_CAPACITY,
        monotonic_ns=time.perf_counter_ns,
    ):
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
        self._ns = monotonic_ns
        self._stats_lock = Lock()
        self._returns = deque(maxlen=MAX_QUEUE_CAPACITY + 1)
        self._writer = dict(phase="between_callbacks", started_ns=self._ns(), frames=0)
        self._last_writer = None
        self.overflow = None

    @contextmanager
    def writer_activity(self, phase, frames=0):
        """Observe the owner thread without timing/altering journal internals."""
        with self._stats_lock:
            self._writer = dict(phase=phase, started_ns=self._ns(), frames=frames)
        try:
            yield
        finally:
            with self._stats_lock:
                now = self._ns()
                self._last_writer = dict(
                    phase=phase,
                    frames=frames,
                    elapsed_ms=(now - self._writer["started_ns"]) / 1000000,
                )
                self._writer = dict(phase="between_callbacks", started_ns=now, frames=0)

    def _overflow_snapshot(self, reason, wall, now):
        # Called under _stats_lock at the failed enqueue, before shutdown/drain.
        with self.queue.mutex:
            depth = len(self.queue.queue)
            oldest = self.queue.queue[0].receipt_ns if depth else None
        arrivals = {}
        for window_ms in (100, 1000):
            boundary = now - window_ms * 1000000
            arrivals[str(window_ms)] = dict(
                returned=sum(stamp >= boundary for stamp in self._returns),
                lower_bound=(
                    len(self._returns) == self._returns.maxlen
                    and self._returns[0] >= boundary
                ),
            )
        self.overflow = dict(
            version="instant-reader-overflow-v1",
            reason=reason,
            receipt_ts_ms=wall,
            queue_capacity=self.queue.maxsize,
            queue_depth=depth,
            received=self.received,
            delivered=self.delivered,
            oldest_queued_age_ms=None if oldest is None else (now - oldest) / 1000000,
            retained_returns=len(self._returns),
            retained_return_span_ms=(now - self._returns[0]) / 1000000,
            arrival_windows_ms=arrivals,
            writer=dict(
                phase=self._writer["phase"],
                frames=self._writer["frames"],
                elapsed_ms=(now - self._writer["started_ns"]) / 1000000,
            ),
            last_completed_writer=deepcopy(self._last_writer),
        )

    def reader_report(self):
        with self._stats_lock:
            return dict(
                received=self.received,
                delivered=self.delivered,
                received_not_delivered=self.received - self.delivered,
                sampled_high_water=self.high_water,
                overflow=deepcopy(self.overflow),
            )

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
                wall, duration = utc_ms(), self._ns()
                if raw in ("", b""):
                    break
                with self._stats_lock:
                    self.received += 1
                    self._returns.append(duration)
                    if len(raw) > MAX_FRAME_BYTES or (
                        isinstance(raw, str)
                        and len(raw.encode("utf-8", errors="surrogatepass"))
                        > MAX_FRAME_BYTES
                    ):
                        self._overflow_snapshot("frame_bytes_exceeded", wall, duration)
                        raise QueueOverflowError(
                            "reader frame exceeded the journal frame bound"
                        )
                    try:
                        self.queue.put_nowait(ReceivedFrame(raw, wall, duration))
                    except Full as exc:
                        self._overflow_snapshot("queue_full", wall, duration)
                        raise QueueOverflowError(
                            "socket reader queue reached its frame cap"
                        ) from exc
                    self.high_water = max(self.high_water, self.queue.qsize())
        except Exception as exc:
            if not self.stopping.is_set():
                self.failure = exc
                if self.overflow is not None:
                    # One bounded stderr record survives a still-blocked owner.
                    try:
                        print(
                            "READER_OVERFLOW " + json.dumps(self.overflow),
                            file=sys.stderr,
                            flush=True,
                        )
                    except OSError:
                        pass  # Logging must not replace the original failure.
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
        with self._stats_lock:
            self.delivered += 1
        return frame

    def recv_ready(self, limit):
        """Drain only already queued frames, stopping at a reported overflow."""
        frames = []
        for _ in range(limit):
            if isinstance(self.failure, QueueOverflowError):
                break
            try:
                frames.append(self.queue.get_nowait())
            except Empty:
                break
        with self._stats_lock:
            self.delivered += len(frames)
        return frames

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


def _observe(path, destination, stop_file, *, limit_s=100):
    """A separate process observes only acknowledged, digest-checked rows."""
    seen = set()
    until = time.monotonic() + limit_s
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
    def __init__(
        self, journal, out, *, products=PRODUCTS, offsets=None, step_ms=GRID_MS
    ):
        self.journal = journal
        self.out = out
        self.products = products
        self.offsets = (LATER_ASOF_MS,) * COHORTS if offsets is None else offsets
        self.step_ms = step_ms
        self.first_cutoff = self.next_cutoff = None
        self.snapshots = {}
        self.observer = None
        self.rows = []
        self.elapsed = []

    def after_commit(self, first_ack_ts_ms):
        if self.next_cutoff is None:
            ready_at = first_ack_ts_ms + WARMUP_MS
            self.first_cutoff = self.next_cutoff = (
                (ready_at + GRID_MS - 1) // GRID_MS
            ) * GRID_MS
        if len(self.elapsed) == len(self.offsets):
            return
        now = utc_ms()
        if self.observer is None and now >= self.next_cutoff - GRID_MS:
            args = [
                sys.executable,
                str(Path(__file__).resolve()),
                "--observe",
                str(self.out),
            ]
            if len(self.offsets) > COHORTS:
                args += ["--observer-limit-s", str(MAX_OBSERVER_S)]
            self.observer = subprocess.Popen(
                args,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        asof = self.next_cutoff + self.offsets[len(self.elapsed)]
        if now < asof:
            return
        # A clock passing the planned as-of can coexist with queued packets.
        # Use the declared knowledge time and leave unavailable features null.
        started = time.perf_counter_ns()
        for product in self.products:
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
                self.snapshots[pub] = snapshot
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
        self.next_cutoff += self.step_ms
        print(
            f"Committed live-source diagnostic cohort {len(self.elapsed)} of {len(self.offsets)}.",
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


def _timing_readiness(cohorts):
    """Summarize both schedules against their full declared slot denominators."""
    recorder = cohorts.journal.evidence
    rows_by_cutoff = {}
    for row in cohorts.rows:
        rows_by_cutoff.setdefault(row["cutoff_ts_ms"], []).append(row)
    report = {}
    ages_by_offset = {offset: [] for offset in TIMING_DEADLINES_MS}
    for offset, deadline in TIMING_DEADLINES_MS.items():
        planned_cohorts = cohorts.offsets.count(offset)
        report[str(offset)] = dict(
            deadline_age_ms=deadline,
            planned_cohorts=planned_cohorts,
            products={
                product: dict(
                    planned_rows=planned_cohorts * len(DIRECTIONS),
                    committed_rows=0,
                    observed_rows=0,
                    observed_by_bound_rows=0,
                    complete_inputs_rows=0 if not recorder.failed else None,
                    complete_non_benchmark_observed_by_bound_rows=(
                        0 if not recorder.failed else None
                    ),
                )
                for product in cohorts.products
            },
            cutoff_comparisons=[],
        )
    for index, offset in enumerate(cohorts.offsets):
        result = report[str(offset)]
        cutoff = (
            None
            if cohorts.first_cutoff is None
            else cohorts.first_cutoff + index * cohorts.step_ms
        )
        rows = rows_by_cutoff.get(cutoff, ())
        for row in rows:
            product = result["products"][row["product_id"]]
            product["committed_rows"] += 1
            observed = row.get("consumer_seen_ts_ms")
            if observed is not None:
                age = observed - cutoff
                ages_by_offset[offset].append(age)
                product["observed_rows"] += 1
                product["observed_by_bound_rows"] += age <= TIMING_DEADLINES_MS[offset]
        on_time = dict.fromkeys(DIRECTIONS, None if recorder.failed else 0)
        summary = dict(
            cutoff_ts_ms=cutoff,
            committed_rows=len(rows),
            on_time_complete_non_benchmark_products_by_direction=on_time,
        )
        if rows and not recorder.failed:
            decisions, deliveries = [], {}
            for row in rows:
                snapshot = cohorts.snapshots[row["publication_id"]]
                decisions.append(snapshot)
                deliveries[(snapshot.product_id, snapshot.direction)] = LocalDelivery(
                    row["decision_sha256"],
                    row["commit_observed_ts_ms"],
                    row.get("consumer_seen_ts_ms"),
                )
            assessment = assess_cohort(
                recorder,
                cutoff,
                asof=cutoff + offset,
                decisions=decisions,
                local_deliveries=deliveries,
                deadline_age_ms=TIMING_DEADLINES_MS[offset],
            )
            summary["eligibility"] = assessment
            for row in assessment["rows"]:
                product = result["products"][row["product_id"]]
                product["complete_inputs_rows"] += row["input_status"] == "ready"
                on_time_candidate = (
                    row["complete_vector_candidate"]
                    and row["delivery"]["status"] == "within_bound"
                )
                product[
                    "complete_non_benchmark_observed_by_bound_rows"
                ] += on_time_candidate
                on_time[row["direction"]] += on_time_candidate
        result["cutoff_comparisons"].append(summary)
    for offset, ages in ages_by_offset.items():
        report[str(offset)]["cutoff_to_consumer"] = _summary(ages)
    return report


def _timing_options(parser, args, now):
    timing = args.profile == TIMING_PROFILE
    if not timing and (args.window is not None or args.startup_smoke):
        parser.error("window and startup smoke require the eligibility timing profile")
    if not timing:
        return PRODUCTS, (LATER_ASOF_MS,) * COHORTS, GRID_MS, DURATION_S
    if args.startup_smoke:
        if args.window is not None:
            parser.error("startup smoke is separate from the declared windows")
        return TIMING_PRODUCTS, (), TIMING_STEP_MS, 60
    if args.window is None:
        parser.error("the eligibility timing profile requires a declared UTC window")
    start, end = UTC_WINDOWS[args.window]
    seconds = now.hour * 3600 + now.minute * 60 + now.second
    # Leave a minute for the socket and subscription before the timed session.
    if not start * 3600 <= seconds <= end * 3600 - DURATION_S - 60:
        parser.error("start early enough to finish the attempt inside its UTC window")
    pair = (LATER_ASOF_MS, 1500) if args.window == "europe" else (1500, LATER_ASOF_MS)
    return TIMING_PRODUCTS, pair * COHORTS, TIMING_STEP_MS, DURATION_S


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    paths = parser.add_mutually_exclusive_group(required=True)
    paths.add_argument("--out-dir", type=Path)
    paths.add_argument("--observe", type=Path)
    parser.add_argument("--profile", choices=PROFILES, default=DEFAULT_PROFILE)
    parser.add_argument("--window", choices=UTC_WINDOWS)
    parser.add_argument("--startup-smoke", action="store_true")
    parser.add_argument("--observer-limit-s", type=int, choices=(100, MAX_OBSERVER_S))
    args = parser.parse_args()
    if args.observe is not None:
        out = args.observe.resolve()
        _observe(
            out / "capture.sqlite",
            out / "observed.jsonl",
            out / "observer.stop",
            limit_s=args.observer_limit_s or 100,
        )
        return
    if args.observer_limit_s is not None:
        parser.error("observer lifetime is only for the read process")

    import websocket

    now = datetime.now(timezone.utc)
    products, offsets, step_ms, duration_s = _timing_options(parser, args, now)
    timing = args.profile == TIMING_PROFILE
    extended = timing and not args.startup_smoke
    packet_limit = TIMING_PACKET_LIMIT if extended else WARMUP_PACKET_LIMIT
    record_limit = TIMING_RECORD_LIMIT_BYTES if extended else MAX_RECORD_BYTES
    out = args.out_dir.resolve()
    out.mkdir(parents=True, exist_ok=False)
    db = out / "capture.sqlite"
    queue_frames, batch_frames = PROFILES[args.profile]
    first = (utc_ms() // GRID_MS + 1) * GRID_MS
    plan = dict(
        version=TIMING_VERSION if timing else VERSION,
        implementation_commit=subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True
        ).strip(),
        started_utc=datetime.now(timezone.utc).isoformat(),
        endpoint=URL,
        products=products,
        channels=CHANNELS,
        profile=args.profile,
        duration_s=duration_s,
        max_connections=1,
        packet_stop=packet_limit - 10,
        byte_stop=TIMING_SOFT_RECORD_BYTES if extended else SOFT_RECORD_BYTES,
        max_reader_queue_frames=queue_frames,
        max_batch_frames=batch_frames,
        warmup_ms=WARMUP_MS,
        cohort_count=len(offsets),
        cohort_evidence_offset_ms=None if timing else LATER_ASOF_MS,
        local_consumer_poll_ms=POLL_S * 1000,
    )
    if timing:
        plan.update(
            window_utc=args.window,
            startup_smoke=args.startup_smoke,
            extended_capacity=extended,
            cohort_step_ms=step_ms,
            cohort_evidence_offsets_ms=offsets,
            diagnostic_deadlines_ms=TIMING_DEADLINES_MS,
            observer_limit_s=MAX_OBSERVER_S if offsets else None,
        )
    (out / "PLAN.json").write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
    sockets = []

    def connect():
        ws = websocket.create_connection(URL, timeout=5, enable_multithread=True)
        ws.settimeout(1)
        socket = QueuedSocket(
            ws, (websocket.WebSocketTimeoutException,), max_frames=queue_frames
        )
        sockets.append(socket)
        return socket

    with StreamJournal(
        db,
        products,
        first,
        first + (69 * 60000 if timing else 4320000),
        max_packets=packet_limit,
        max_record_bytes=record_limit,
        indexed=True,
        extended_capacity=extended,
        batch_frames=batch_frames,
        monotonic_ns=time.perf_counter_ns,
    ) as journal:
        cohorts = DiagnosticCohorts(
            journal, out, products=products, offsets=offsets, step_ms=step_ms
        )
        try:
            result = capture(
                journal,
                connect,
                timeout_errors=(TimeoutError,),
                transport_errors=(OSError, websocket.WebSocketException),
                duration_s=plan["duration_s"],
                packet_stop=plan["packet_stop"],
                byte_stop=plan["byte_stop"],
                after_commit=cohorts.after_commit,
                max_connections=plan["max_connections"],
                products=products,
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
                    products=products,
                )
    result.update(plan)
    result["segment"] = read_segment(db)
    result["recovered_pending_ingress_frames"] = sum(
        1 for _ in iter_pending_ingress(db)
    )
    result["journal_sha256"] = _file_sha(db)
    result["journal_bytes"] = db.stat().st_size
    result["reader"] = [socket.reader_report() for socket in sockets]
    result["diagnostic_cohorts"] = dict(
        planned=len(offsets), complete=len(cohorts.elapsed)
    )
    result["cohort_serial"] = _summary(cohorts.elapsed)
    result["decision_preparation"] = _summary(
        [row["prepare_ms"] for row in cohorts.rows]
    )
    result["outbox_commit"] = _summary([row["outbox_ms"] for row in cohorts.rows])
    result["local_reader"] = _observation_report(out, cohorts.rows)
    result["local_reader"]["process_exit_code"] = observer_exit
    result["diagnostic_rows"] = cohorts.rows
    if timing and not args.startup_smoke:
        result["timing_readiness"] = _timing_readiness(cohorts)
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
