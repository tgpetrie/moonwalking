"""Measure indexed preparation on a continuously committed synthetic stream."""

import argparse
import json
from pathlib import Path
import subprocess
import time

from instant_coverage import WARMUP_PACKET_LIMIT
from instant_delayed_decision import prepare_decision
from instant_input_evidence import DIRECTIONS, GRID_MS, _file_sha
from instant_source_pilot import LATER_ASOF_MS, PRODUCTS, WARMUP_MS, _summary, capture
from instant_stream_journal import StreamJournal, read_segment
from instant_warmup_capacity import PACKET_STOP, SyntheticSocket


COHORTS = 10


def _measure(operation, *args, **kwargs):
    started = time.perf_counter_ns()
    result = operation(*args, **kwargs)
    return result, (time.perf_counter_ns() - started) / 1000000


def _content(decision):
    # Compare the whole output except the actual processing timestamps, which
    # naturally differ because the oracle runs after the capture.
    row = json.loads(decision.feature_json)
    row.pop("computation_completed_ts_ms")
    row["baseline"].pop("computation_completed_ts_ms")
    return row, decision.anchor_quotes_json


def _batch_compare(recorder, measured):
    timings = []
    index = recorder._index
    try:
        # The recorder is sealed for ingest at this point. Use the same
        # immutable evidence and the unindexed lookup/calculation path.
        recorder._index = None
        for cohort in (measured[0], measured[-1]):
            for snapshot in cohort:
                batch, elapsed = _measure(
                    prepare_decision,
                    recorder,
                    snapshot.product_id,
                    snapshot.feature_cutoff_ts_ms,
                    snapshot.direction,
                    asof=snapshot.knowledge_asof_ts_ms,
                )
                if _content(snapshot) != _content(batch):
                    raise ValueError(
                        f"batch parity failed for {batch.product_id} "
                        f"{batch.direction} at {batch.feature_cutoff_ts_ms}"
                    )
                timings.append(elapsed)
    finally:
        recorder._index = index
    return timings


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    out = args.out_dir.resolve()
    out.mkdir(parents=True, exist_ok=False)
    path = out / "indexed.sqlite"
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    source = SyntheticSocket()
    next_cutoff = WARMUP_MS
    prepare_times, outbox_times, cohort_times, release_lags = [], [], [], []
    snapshots = []
    started = time.perf_counter()
    with StreamJournal(
        path,
        PRODUCTS,
        WARMUP_MS,
        WARMUP_MS + COHORTS * GRID_MS,
        max_packets=WARMUP_PACKET_LIMIT,
        clock_ms=source.wall_ms,
        monotonic_ns=source.monotonic_ns,
        indexed=True,
    ) as journal:

        def after_commit():
            nonlocal next_cutoff
            if len(snapshots) == COHORTS or source.now < next_cutoff + LATER_ASOF_MS:
                return
            asof = next_cutoff + LATER_ASOF_MS
            release_lags.append(source.now - asof)
            cohort_started = time.perf_counter_ns()
            prepared = []
            for product in PRODUCTS:
                for direction in DIRECTIONS:
                    snapshot, elapsed = _measure(
                        prepare_decision,
                        journal.evidence,
                        product,
                        next_cutoff,
                        direction,
                        asof=asof,
                    )
                    prepare_times.append(elapsed)
                    prepared.append(snapshot)
                    receipt, elapsed = _measure(
                        journal.append_publication,
                        f"synthetic-{next_cutoff}-{product}-{direction}",
                        snapshot,
                    )
                    if receipt.local_commit_observed_ts_ms is None:
                        raise ValueError("diagnostic outbox entry was not acknowledged")
                    outbox_times.append(elapsed)
            cohort_times.append((time.perf_counter_ns() - cohort_started) / 1000000)
            snapshots.append(prepared)
            next_cutoff += GRID_MS
            print(
                f"Committed diagnostic cohort {len(snapshots)} of {COHORTS}.",
                flush=True,
            )

        run = capture(
            journal,
            lambda: source,
            monotonic=source.monotonic,
            packet_stop=PACKET_STOP,
            after_commit=after_commit,
        )
        capture_seconds = time.perf_counter() - started
        if not journal.evidence.failed:
            journal.finish()
        timings = (
            _batch_compare(journal.evidence, snapshots)
            if len(snapshots) == COHORTS and run["stop"] == "duration"
            else []
        )
        logical_bytes = journal.record_bytes
    report = dict(
        version="instant-indexed-latency-v1-draft",
        scope="synthetic_receipt_clock_real_serial_journal_and_computation",
        implementation_commit=commit,
        stop=run["stop"],
        connections=run["attempts"],
        simulated_ms=source.now,
        host_capture_seconds=round(capture_seconds, 3),
        planned_cohorts=COHORTS,
        committed_cohorts=len(snapshots),
        index_decision_preparation=_summary(prepare_times),
        local_outbox_write_and_ack=_summary(outbox_times),
        full_serial_cohort=_summary(cohort_times),
        synthetic_release_after_planned_asof=_summary(release_lags),
        batch_decision_preparation_after_capture=_summary(timings),
        exact_content_parity_cases=len(timings),
        callback_through_commit={
            key: data["callback_through_commit"]
            for key, data in run["latencies"].items()
        },
        logical_record_bytes=logical_bytes,
        journal_sha256=_file_sha(path),
        journal_bytes=path.stat().st_size,
        segment=read_segment(path),
        feed_gate_pass=False,
        fitting_allowed=False,
        external_publication_measured=False,
    )
    (out / "REPORT.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    print(
        f"Indexed latency run stopped: {run['stop']}. Report at {out / 'REPORT.json'}",
        flush=True,
    )


if __name__ == "__main__":
    main()
