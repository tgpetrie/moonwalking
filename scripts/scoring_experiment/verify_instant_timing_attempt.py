"""Verify a finished indexed pilot from its journal and local reader receipts."""

import argparse
from collections import Counter, defaultdict
from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3

from instant_delayed_eligibility import BASELINES, FEATURES, _component_reasons
from instant_input_evidence import BENCHMARK, DIRECTIONS, GRID_MS, _file_sha, _json
from instant_source_pilot import _summary
from instant_stream_journal import _decoded, _local_publication


def _require(condition, detail):
    if not condition:
        raise ValueError(detail)


def _index(rows, key):
    indexed = {}
    for row in rows:
        identity = row[key]
        _require(identity not in indexed, f"duplicate {key}: {identity}")
        indexed[identity] = row
    return indexed


def _verify_packets(db, asofs, plan):
    waiting = iter(sorted(set(asofs)))
    next_asof = next(waiting, None)
    prefixes = {}
    digest = hashlib.sha256()
    previous_available = count = batched = 0
    first_ack = None
    roster = set(plan["products"])
    for seq, body, row_sha in db.execute(
        "SELECT receipt_seq, body, digest FROM packets ORDER BY receipt_seq"
    ):
        row = _decoded(body, row_sha)
        packet, envelope = row["processing"], row["envelope"]
        receipt, start, end, available = (
            packet[key]
            for key in (
                "receipt_ts_ms",
                "processing_started_ts_ms",
                "processing_completed_ts_ms",
                "available_ts_ms",
            )
        )
        _require(
            count + 1 == seq == packet["receipt_seq"] == envelope["receipt_seq"]
            and receipt == envelope["receipt_ts_ms"]
            and receipt <= start <= end
            and available == max(end, receipt + 1)
            and available >= previous_available
            and packet["envelope_sha256"]
            == hashlib.sha256(_json(envelope).encode()).hexdigest(),
            f"packet identity, digest or processing clock differs at {seq}",
        )
        if "ingress_commit_observed_ts_ms" in row:
            _require(
                receipt <= row["ingress_commit_observed_ts_ms"] <= start,
                f"batch ingress clock differs at {seq}",
            )
            batched += 1
        message = envelope["message"]
        if first_ack is None and message["type"] == "subscriptions":
            channels = defaultdict(set)
            for item in message["channels"]:
                name = item["name"]
                if name == "level2_50":
                    name = "level2_batch"
                channels[name].update(item["product_ids"])
            if all(roster <= channels[name] for name in plan["channels"]):
                first_ack = receipt
        while next_asof is not None and next_asof < available:
            prefixes[next_asof] = count, digest.hexdigest()
            next_asof = next(waiting, None)
        digest.update((_json(packet) + "\n").encode("utf-8"))
        previous_available = available
        count += 1
    while next_asof is not None:
        prefixes[next_asof] = count, digest.hexdigest()
        next_asof = next(waiting, None)
    return count, batched, prefixes, first_ack


def _readiness(decision, manifest, prefixes):
    features = json.loads(decision["feature_json"])
    baseline = features["baseline"]
    asof = decision["knowledge_asof_ts_ms"]
    _require(
        (baseline["known_packet_count"], baseline["known_packet_prefix_sha256"])
        == prefixes[asof],
        "decision prefix differs from the journal",
    )
    for key in ("inventory_sha256", "inventory_recorded_ts_ms"):
        _require(
            baseline[key] == manifest[key], f"decision {key} differs from the journal"
        )
    for source in ("input", "book", "monitor"):
        for label in ("implementation", "contract"):
            key = f"{source}_{label}_sha256"
            _require(
                baseline[key] == manifest[key],
                f"decision {key} differs from the journal",
            )
    anchors = json.loads(decision["anchor_quotes_json"])
    product = decision["product_id"]
    feature_reasons = _component_reasons(
        features["features"], FEATURES, asof, "evidence_available_ts_ms"
    )
    baseline_reasons = _component_reasons(
        baseline, BASELINES, asof, "inputs_available_ts_ms"
    )
    return (
        not feature_reasons
        and not baseline_reasons
        and all(anchors[pid]["available"] is True for pid in (product, BENCHMARK))
    )


def _schedule(plan, ack):
    offsets = plan.get("cohort_evidence_offsets_ms")
    if offsets is None:
        offsets = [plan["cohort_evidence_offset_ms"]] * plan["cohort_count"]
    _require(
        len(offsets) == plan["cohort_count"],
        "declared cohort count differs from its schedule",
    )
    if ack is None:
        return offsets, {}
    ready_at = ack + plan["warmup_ms"]
    first = ((ready_at + GRID_MS - 1) // GRID_MS) * GRID_MS
    step = plan.get("cohort_step_ms", GRID_MS)
    return offsets, {first + i * step: offset for i, offset in enumerate(offsets)}


def _count_two(candidates, offset):
    return {
        direction: sum(
            count >= 2
            for (wait, _, side), count in candidates.items()
            if wait == offset and side == direction
        )
        for direction in DIRECTIONS
    }


def verify(attempt, *, plan_sha256=None):
    plan_path = attempt / "PLAN.json"
    report_path = attempt / "REPORT.json"
    _require(report_path.is_file(), "capture has no final report")
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    report = json.loads(report_path.read_text(encoding="utf-8"))
    journal_path = attempt / "capture.sqlite"
    actual_plan_sha = _file_sha(plan_path)
    _require(
        plan_sha256 is None or actual_plan_sha == plan_sha256,
        "plan digest differs from the checkpoint",
    )
    _require(
        all(report.get(k) == v for k, v in plan.items()),
        "report and capture plan differ",
    )
    journal_sha = _file_sha(journal_path)
    _require(
        journal_sha == report["journal_sha256"],
        "journal digest differs from the report",
    )

    observer_path = attempt / "observed.jsonl"
    observed = _index(
        (
            (
                json.loads(line)
                for line in observer_path.read_text(encoding="utf-8").splitlines()
            )
            if observer_path.is_file()
            else ()
        ),
        "publication_id",
    )
    reported = _index(report["diagnostic_rows"], "publication_id")
    with closing(
        sqlite3.connect(
            journal_path.resolve().as_uri() + "?mode=ro&immutable=1", uri=True
        )
    ) as db:
        _require(
            db.execute("PRAGMA quick_check").fetchall() == [("ok",)],
            "SQLite quick check failed",
        )
        manifest_json, status = db.execute(
            "SELECT manifest, status FROM segment WHERE id = 1"
        ).fetchone()
        manifest = json.loads(manifest_json)
        _require(
            manifest == report["segment"]["manifest"]
            and status == report["segment"]["status"],
            "journal segment differs from the report",
        )
        _require(
            sorted(plan["products"]) == sorted(manifest["inventory"]["products"]),
            "journal roster differs from the plan",
        )
        publications = dict(
            (pub, _local_publication(db, pub))
            for (pub,) in db.execute("SELECT publication_id FROM publications")
        )
        pending = db.execute("SELECT count(*) FROM pending_ingress").fetchone()[0]
        packets, batched, prefixes, first_ack = _verify_packets(
            db,
            (
                record["decision"]["knowledge_asof_ts_ms"]
                for _, record in publications.values()
            ),
            plan,
        )

    _require(
        packets == report["segment"]["packets"]
        and len(publications) == report["segment"]["publications"]
        and pending == report["recovered_pending_ingress_frames"],
        "journal counts differ from the report",
    )
    _require(
        reported.keys() <= publications.keys()
        and observed.keys() <= publications.keys(),
        "report or observation refers to an unknown publication",
    )
    _require(
        first_ack == report["first_ack_ts_ms"],
        "subscription acknowledgment differs from the report",
    )
    offsets, schedule = _schedule(plan, first_ack)
    arms = {}
    ages = defaultdict(list)
    ready_candidates, on_time_candidates = Counter(), Counter()
    for offset, count in Counter(offsets).items():
        bound = plan.get("diagnostic_deadlines_ms", {}).get(str(offset))
        arms[str(offset)] = dict(
            planned_cohorts=count,
            consumer_age_bound_ms=bound,
            products={
                product: dict(
                    planned=count * len(DIRECTIONS),
                    journaled=0,
                    complete_inputs=0,
                    observed=0,
                    within_bound=0 if bound is not None else None,
                    complete_and_within_bound=0 if bound is not None else None,
                )
                for product in plan["products"]
            },
        )
    slots = set()
    for pub, (receipt, record) in publications.items():
        decision = record["decision"]
        cutoff, asof, completed = (
            decision[key]
            for key in (
                "feature_cutoff_ts_ms",
                "knowledge_asof_ts_ms",
                "decision_completed_ts_ms",
            )
        )
        product, direction = decision["product_id"], decision["direction"]
        offset = schedule.get(cutoff)
        slot = cutoff, product, direction
        commit = receipt.local_commit_observed_ts_ms
        _require(
            offset is not None
            and asof == cutoff + offset
            and product in plan["products"]
            and direction in DIRECTIONS
            and slot not in slots
            and asof
            <= decision["feature_computation_completed_ts_ms"]
            <= completed
            <= record["commit_requested_ts_ms"],
            f"publication slot or decision clock differs from the plan: {pub}",
        )
        slots.add(slot)
        expected = dict(
            cutoff_ts_ms=cutoff,
            knowledge_asof_ts_ms=asof,
            decision_completed_ts_ms=completed,
            product_id=product,
            direction=direction,
            decision_sha256=receipt.decision_sha256,
            commit_observed_ts_ms=commit,
        )
        if pub in reported:
            _require(
                all(reported[pub][k] == v for k, v in expected.items()),
                f"reported decision differs from the journal: {pub}",
            )
        arm = arms[str(offset)]
        stats = arm["products"][product]
        stats["journaled"] += 1
        ready = _readiness(decision, manifest, prefixes)
        stats["complete_inputs"] += ready
        candidate = ready and product != BENCHMARK
        if candidate:
            ready_candidates[offset, cutoff, direction] += 1
        if pub not in observed:
            _require(
                reported.get(pub, {}).get("consumer_seen_ts_ms") is None,
                f"reported consumer clock has no observation: {pub}",
            )
            continue
        observation = observed[pub]
        seen = observation["consumer_seen_ts_ms"]
        _require(
            observation["decision_sha256"] == receipt.decision_sha256
            and observation["commit_observed_ts_ms"] == commit
            and commit is not None
            and commit <= seen
            and (pub not in reported or reported[pub]["consumer_seen_ts_ms"] == seen),
            f"consumer observation differs from the journal or report: {pub}",
        )
        age = seen - cutoff
        stats["observed"] += 1
        ages[offset].append(age)
        bound = arm["consumer_age_bound_ms"]
        if bound is not None and age <= bound:
            stats["within_bound"] += 1
            stats["complete_and_within_bound"] += ready
            if candidate:
                on_time_candidates[offset, cutoff, direction] += 1

    for arm, stats in arms.items():
        offset = int(arm)
        stats["cutoff_to_consumer_ms"] = _summary(ages[offset])
        stats["cutoffs_with_two_ready_candidates_by_direction"] = _count_two(
            ready_candidates, offset
        )
        stats["cutoffs_with_two_on_time_candidates_by_direction"] = (
            _count_two(on_time_candidates, offset)
            if stats["consumer_age_bound_ms"] is not None
            else dict.fromkeys(DIRECTIONS)
        )
    return dict(
        stop=report["stop"],
        segment_status=status,
        plan_sha256=actual_plan_sha,
        journal_sha256=journal_sha,
        sqlite_quick_check="ok",
        packet_records_verified=packets,
        batch_ingress_clocks_verified=batched,
        pending_ingress_frames=pending,
        publication_prefixes_verified=len(publications),
        journal_only_publications=len(publications.keys() - reported.keys()),
        unacknowledged_publications=sum(
            r.local_commit_observed_ts_ms is None for r, _ in publications.values()
        ),
        local_observations_verified=len(observed),
        schedule_results=arms,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("attempt", type=Path)
    parser.add_argument("--plan-sha256")
    args = parser.parse_args()
    print(json.dumps(verify(args.attempt, plan_sha256=args.plan_sha256), indent=2))


if __name__ == "__main__":
    main()
