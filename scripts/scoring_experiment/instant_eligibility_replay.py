"""Compare four evidence waits on a preserved, digest-pinned local journal."""

import argparse
from collections import Counter
from dataclasses import asdict
import json
from pathlib import Path
from shutil import copyfile
from tempfile import TemporaryDirectory
import time

from instant_delayed_decision import DecisionEvidence, prepare_decision
from instant_delayed_eligibility import FEATURES, LocalDelivery, assess_cohort
from instant_input_evidence import DIRECTIONS, GRID_MS, InputEvidenceRecorder, _file_sha
from instant_stream_journal import iter_packets, read_local_publication, read_segment


OFFSETS_MS = (0, 1500, 2500, 5000)


class RecordedClock:
    """Rebuild fully processed packet prefixes using their recorded end times."""

    def __init__(self, recorded):
        self.recorded = recorded
        self.steps = iter(())
        self.replaying = False

    def __call__(self):
        if self.replaying:
            return next(self.steps)
        return max(self.recorded, time.time_ns() // 1_000_000)

    def feed(self, recorder, row):
        packet = row["processing"]
        start = packet["processing_started_ts_ms"]
        end = packet["processing_completed_ts_ms"]
        # The journal did not persist the intermediate monitor and book
        # completion clocks. Treat both as known at full payload completion.
        self.steps = iter((start, start, end, end, end))
        self.replaying = True
        prior = len(recorder.trades)
        recorder.ingest(row["envelope"])
        actual_trade = (
            asdict(recorder.trades[-1]) if len(recorder.trades) > prior else None
        )
        if (
            next(self.steps, None) is not None
            or asdict(recorder.packets[-1]) != packet
            or actual_trade != row["trade"]
        ):
            raise ValueError(
                "recorded packet or first-receipt trade differs from replay"
            )


def _reconstruct(db, segment):
    manifest = segment["manifest"]
    plan = manifest["inventory"]
    clock = RecordedClock(manifest["inventory_recorded_ts_ms"])
    clock.steps = iter((clock.recorded,))
    clock.replaying = True
    recorder = InputEvidenceRecorder(
        plan["products"],
        plan["first_cutoff"],
        plan["stop_cutoff"],
        clock_ms=clock,
        packet_limit=manifest["max_packets"],
        indexed=True,
    )
    for prefix, provider in (
        ("input", recorder),
        ("book", recorder.book),
        ("monitor", recorder.book.monitor),
    ):
        if (
            manifest[f"{prefix}_implementation_sha256"] != provider.source_sha256
            or manifest[f"{prefix}_contract_sha256"] != provider.contract_sha256
        ):
            raise ValueError(f"recorded {prefix} provenance differs from replay")
    if (
        recorder.inventory_sha256 != manifest["inventory_sha256"]
        or recorder._index.source_sha256 != manifest["index_implementation_sha256"]
    ):
        raise ValueError("recorded inventory or index differs from replay")
    first_ack = None
    for row in iter_packets(db):
        clock.feed(recorder, row)
        envelope = row["envelope"]
        if (
            first_ack is None
            and envelope["message"]["type"] == "subscriptions"
            and recorder.book.monitor.active == set(recorder.products)
        ):
            first_ack = envelope["receipt_ts_ms"]
    clock.replaying = False
    if len(recorder.packets) != segment["packets"] or first_ack is None:
        raise ValueError("incomplete replay or no full subscription acknowledgment")
    return recorder, first_ack


def _feature_signature(decision):
    data = json.loads(decision.feature_json)
    return {
        name: (row["status"], row.get("reason"), row.get("value"))
        for name, row in data["features"].items()
    }


def _observed(db, cutoff, replay, observers):
    decisions, deliveries = [], {}
    for simulated in replay:
        slot = (simulated.product_id, simulated.direction)
        identity = f"diagnostic-{cutoff}-{slot[0]}-{slot[1]}"
        receipt, record = read_local_publication(db, identity)
        actual = DecisionEvidence(**record["decision"])
        if (actual.product_id, actual.direction) != slot or _feature_signature(
            actual
        ) != _feature_signature(simulated):
            raise ValueError("replayed +5s feature status, reason, or value differs")
        decisions.append(actual)
        observed = observers.pop(identity)
        if (
            observed["decision_sha256"] != receipt.decision_sha256
            or observed["commit_observed_ts_ms"] != receipt.local_commit_observed_ts_ms
        ):
            raise ValueError("local observer is not linked to the original outbox row")
        deliveries[slot] = LocalDelivery(
            receipt.decision_sha256,
            receipt.local_commit_observed_ts_ms,
            observed["consumer_seen_ts_ms"],
        )
    return decisions, deliveries


def _summary(cohorts):
    products = {}
    for cohort in cohorts:
        for row in cohort["rows"]:
            item = products.setdefault(
                row["product_id"],
                dict(
                    planned=0,
                    full_inputs_ready=0,
                    non_benchmark_candidates=0,
                    feature_ready=dict.fromkeys(FEATURES, 0),
                    feature_missing=Counter(),
                ),
            )
            item["planned"] += 1
            item["full_inputs_ready"] += row["input_status"] == "ready"
            item["non_benchmark_candidates"] += row["complete_vector_candidate"]
            for feature in FEATURES:
                reason = (
                    row["feature_reasons"][feature]
                    if feature in row["feature_reasons"]
                    else None
                )
                if reason is None:
                    item["feature_ready"][feature] += 1
                else:
                    item["feature_missing"][f"{feature}:{reason}"] += 1
    return products


def compare(db, *, expected_sha256, attempt, observations):
    # The journal readers also support crash recovery. Use a verified scratch
    # copy so SQLite cannot change the preserved source, even on open.
    with TemporaryDirectory(prefix="moonwalking-eligibility-") as temporary:
        scratch = Path(temporary) / "replay.sqlite"
        copyfile(db, scratch)
        if (
            _file_sha(scratch) != expected_sha256
            or attempt["journal_sha256"] != expected_sha256
        ):
            raise ValueError("preserved journal digest differs")
        segment = read_segment(scratch)
        if segment["status"] != "finished":
            raise ValueError("only a finished preserved journal can be compared")
        recorder, ack = _reconstruct(scratch, segment)
        if (
            ack != attempt["first_ack_ts_ms"]
            or set(recorder.products) != set(attempt["products"])
            or attempt["cohort_evidence_offset_ms"] != OFFSETS_MS[-1]
            or segment["publications"] != len(observations)
        ):
            raise ValueError("preserved run does not match its attempt report")
        observers = {row["publication_id"]: row for row in observations}
        first = ((ack + attempt["warmup_ms"] + GRID_MS - 1) // GRID_MS) * GRID_MS
        cutoffs = range(first, first + GRID_MS * attempt["cohort_count"], GRID_MS)
        by_offset = {}
        archived = []
        for offset in OFFSETS_MS:
            cohorts = []
            for cutoff in cutoffs:
                asof = cutoff + offset
                if asof > recorder.packets[-1].available_ts_ms:
                    raise ValueError("as-of exceeds the captured evidence prefix")
                count, digest, following = recorder._prefix_at(asof)
                decisions = [
                    prepare_decision(recorder, product, cutoff, direction, asof=asof)
                    for product in recorder.products
                    for direction in DIRECTIONS
                ]
                cohort = assess_cohort(recorder, cutoff, asof=asof, decisions=decisions)
                cohort.update(
                    known_packet_count=count,
                    known_packet_prefix_sha256=digest,
                    payload_in_progress=bool(
                        following
                        and following.processing_started_ts_ms
                        <= asof
                        < following.processing_completed_ts_ms
                    ),
                )
                cohorts.append(cohort)
                if offset == OFFSETS_MS[-1]:
                    original, delivered = _observed(
                        scratch, cutoff, decisions, observers
                    )
                    archived.append(
                        assess_cohort(
                            recorder,
                            cutoff,
                            asof=asof,
                            decisions=original,
                            local_deliveries=delivered,
                            deadline_age_ms=6000,
                        )
                    )
            by_offset[str(offset)] = dict(products=_summary(cohorts), cohorts=cohorts)
        if observers:
            raise ValueError("unaccounted original local observations")
        real_rows = [row for cohort in archived for row in cohort["rows"]]
        return dict(
            scope="preserved_journal_fully_processed_prefix_diagnostic",
            journal_sha256=expected_sha256,
            packets=segment["packets"],
            first_ack_ts_ms=ack,
            offsets_ms=list(OFFSETS_MS),
            replay_by_offset=by_offset,
            original_plus_5s_observed=dict(
                rows=len(real_rows),
                replay_feature_status_reason_value_parity=len(real_rows),
                max_commit_age_ms=max(
                    row["delivery"]["commit_age_ms"] for row in real_rows
                ),
                max_consumer_age_ms=max(
                    row["delivery"]["consumer_age_ms"] for row in real_rows
                ),
                consumer_within_6000ms=sum(
                    row["delivery"]["status"] == "within_bound" for row in real_rows
                ),
            ),
            feed_gate_pass=False,
            study_frozen=False,
            fitting_allowed=False,
        )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("journal", type=Path)
    parser.add_argument("attempt", type=Path)
    parser.add_argument("observations", type=Path)
    parser.add_argument("--sha256", required=True)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    attempt = json.loads(args.attempt.read_text(encoding="utf-8"))
    observations = [
        json.loads(line)
        for line in args.observations.read_text(encoding="utf-8").splitlines()
    ]
    report = compare(
        args.journal,
        expected_sha256=args.sha256,
        attempt=attempt,
        observations=observations,
    )
    with args.out.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
