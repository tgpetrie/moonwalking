"""Compare two bounded queue sizes on a declared synthetic arrival burst."""

import argparse
from itertools import islice
import json
from pathlib import Path
import sqlite3
import subprocess
from threading import Event
import time

from instant_input_evidence import GRID_MS, _file_sha
from instant_real_indexed_pilot import MAX_QUEUE_CAPACITY, QUEUE_CAPACITY, QueuedSocket
from instant_source_pilot import PRODUCTS, capture, utc_ms
from instant_stream_journal import StreamJournal, iter_packets, read_segment
from instant_warmup_capacity import frames


BURST_COUNT = 160
BURST_S = 0.100
TAIL_COUNT = 40
TAIL_S = 1
STALL_MS = (0, 450)
REPETITIONS = 3


def workload():
    boot = [message for _, message in islice(frames(), 5)]
    # The actual startup had ALCX's only full snapshot immediately before ACK.
    alcx = next(row for row in boot if row.get("product_id") == PRODUCTS[2])
    boot.remove(alcx)
    boot.insert(0, alcx)
    suffix = []
    for i, (_, message) in enumerate(islice(frames(), 5, 5 + BURST_COUNT + TAIL_COUNT)):
        if i < BURST_COUNT:
            delay = i * BURST_S / (BURST_COUNT - 1)
        else:
            delay = BURST_S + (i - BURST_COUNT + 1) * TAIL_S / TAIL_COUNT
        suffix.append((delay, message))
    return boot, suffix


class BurstSocket:
    def __init__(self, boot, suffix):
        self.boot = iter(boot)
        self.suffix = iter(suffix)
        self.release = Event()
        self.started = None
        self.burst_receipts_ns = []

    def send(self, raw):
        if json.loads(raw)["type"] != "subscribe":
            raise ValueError("expected the subscription command")

    def recv(self):
        initial = next(self.boot, None)
        if initial is not None:
            return json.dumps(initial, separators=(",", ":"))
        if not self.release.wait(timeout=0.2):
            raise TimeoutError("waiting for startup frames to commit")
        if self.started is None:
            self.started = time.perf_counter()
        item = next(self.suffix, None)
        if item is None:
            return ""
        delay, message = item
        time.sleep(max(0.0, self.started + delay - time.perf_counter()))
        if delay <= BURST_S:
            self.burst_receipts_ns.append(time.perf_counter_ns())
        return json.dumps(message, separators=(",", ":"))

    def abort(self):
        self.release.set()

    def close(self, timeout):
        pass


def experiment(path, capacity, stall_ms):
    boot, suffix = workload()
    source = BurstSocket(boot, suffix)
    queue = QueuedSocket(source, (TimeoutError,), max_frames=capacity)
    first = (utc_ms() // GRID_MS + 1) * GRID_MS
    with StreamJournal(
        path,
        PRODUCTS,
        first,
        first + GRID_MS,
        indexed=True,
        monotonic_ns=time.perf_counter_ns,
    ) as journal:

        def release_burst():
            if journal.packet_count == len(boot) + 1:
                source.release.set()
                if stall_ms:
                    time.sleep(stall_ms / 1000)

        result = capture(
            journal,
            lambda: queue,
            timeout_errors=(TimeoutError,),
            max_connections=1,
            duration_s=10,
            after_commit=release_burst,
            progress=lambda *args, **kwargs: None,
        )
        if not journal.evidence.failed:
            journal.finish()

    rows = [row["envelope"] for row in iter_packets(path)]
    committed = [row["message"] for row in rows[1:-1]]
    sent = boot + [message for _, message in suffix]
    if committed != sent[: len(committed)]:
        raise ValueError("journal differs from the source's ordered prefix")
    if len({row["connection_id"] for row in rows}) != 1:
        raise ValueError("one connection required")
    with sqlite3.connect(path) as db:
        if db.execute("PRAGMA quick_check").fetchall() != [("ok",)]:
            raise ValueError("journal quick check failed")
    latency = {
        kind: group["reader_to_writer"]
        for kind, group in result["latencies"].items()
        if "reader_to_writer" in group
    }
    return dict(
        capacity=capacity,
        requested_stall_ms=stall_ms,
        stop=result["stop"],
        final_marker=rows[-1]["message"]["type"],
        source_frames=len(sent),
        synthetic_burst_frames_returned=len(source.burst_receipts_ns),
        synthetic_burst_return_span_ms=(
            (source.burst_receipts_ns[-1] - source.burst_receipts_ns[0]) / 1000000
            if source.burst_receipts_ns
            else None
        ),
        reader_received=queue.received,
        writer_delivered=queue.delivered,
        journal_committed_data=len(committed),
        observed_queue_high_water=queue.high_water,
        worst_measured_queue_ms=max(row["max_ms"] for row in latency.values()),
        reader_to_writer_by_kind=latency,
        digest=_file_sha(path),
        segment=read_segment(path),
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    out = args.out_dir.resolve()
    out.mkdir(parents=True, exist_ok=False)
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    reports = []
    for repeat in range(1, REPETITIONS + 1):
        for stall in STALL_MS:
            for capacity in (QUEUE_CAPACITY, MAX_QUEUE_CAPACITY):
                name = f"r{repeat}-stall{stall}-queue{capacity}"
                report = experiment(out / f"{name}.sqlite", capacity, stall)
                reports.append(dict(name=name, **report))
                print(
                    f"{name}: {report['stop']}, {report['journal_committed_data']} committed data frames",
                    flush=True,
                )
    result = dict(
        version="instant-queue-burst-test-v1-draft",
        implementation_commit=commit,
        scope="synthetic_queued_socket_real_indexed_sqlite_writer",
        burst_frames=BURST_COUNT,
        burst_target_ms=BURST_S * 1000,
        tail_frames=TAIL_COUNT,
        tail_target_ms=TAIL_S * 1000,
        repetitions=REPETITIONS,
        reports=reports,
        live_queue_profile=QUEUE_CAPACITY,
        fitting_allowed=False,
    )
    (out / "REPORT.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
