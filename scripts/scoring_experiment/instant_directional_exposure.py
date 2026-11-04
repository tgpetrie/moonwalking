"""Opt-in directional exposure draft from explicit caller eligibility assertions.

No feed-evidence producer, target change, fitting or live integration. The
existing association module's joint exposure report retains its semantics.
"""

from collections import Counter
import hashlib
import json
from pathlib import Path

import instant_association as assoc


VERSION = "instant-directional-exposure-v1-draft"
CONTRACT = (
    Path(__file__).resolve().parents[2]
    / "docs/research/INSTANT_DIRECTIONAL_EXPOSURE_CONTRACT_V1_DRAFT.json"
)


def provenance():
    raw = CONTRACT.read_text(encoding="utf-8").encode("utf-8")
    cfg = json.loads(raw)
    if (
        cfg["version"] != VERSION
        or cfg["association_version"] != assoc.VERSION
        or cfg["grid_ms"] != assoc.GRID_MS
        or tuple(cfg["directions"]) != assoc.DIRECTIONS
        or tuple(cfg["horizons_seconds"]) != assoc.HORIZONS
        or cfg["fitting_allowed"] is not False
        or cfg["live_integration"] is not False
        or cfg["feed_gate_pass"] is not False
    ):
        raise ValueError("directional contract and implementation differ")
    return dict(
        version=VERSION,
        contract_sha256=hashlib.sha256(raw).hexdigest(),
        implementation_sha256=hashlib.sha256(
            Path(__file__).read_text(encoding="utf-8").encode("utf-8")
        ).hexdigest(),
        association_dependency=assoc.provenance(),
        eligibility_source="caller_assertions_not_authenticated_feed_evidence",
        eligibility_producer_implemented=False,
        evaluation_only=True,
        physical_onset_defined=False,
        operational_missed_move_rates_enabled=False,
        feed_gate_pass=False,
        study_frozen=False,
        fitting_allowed=False,
        live_integration=False,
    )


def _key(product, direction, ts):
    if direction not in assoc.DIRECTIONS:
        raise ValueError("unsupported eligibility direction")
    return assoc._text(product), direction, assoc._grid(ts)


def _slots(records, asof):
    slots = {}
    for record in records:
        if (
            not isinstance(record, dict)
            or any(
                key not in record
                for key in ("product_id", "direction", "ts_ms", "available_ts_ms")
            )
            or any(
                type(record.get(flag)) is not bool for flag in assoc.ELIGIBILITY_FLAGS
            )
        ):
            raise ValueError(
                "identity, clocks and explicit boolean eligibility flags required"
            )
        key = _key(record["product_id"], record["direction"], record["ts_ms"])
        available = assoc._integer(record["available_ts_ms"])
        if available > key[2] or key[2] > asof:
            raise ValueError("eligibility must be known by its cutoff <= as-of")
        if key in slots:
            raise ValueError("duplicate directional eligibility slot")
        slots[key] = {flag: record[flag] for flag in assoc.ELIGIBILITY_FLAGS}
    # Both boards must explicitly account for every submitted product/cutoff.
    # A missing eligibility row is never silently treated as an excluded coin.
    for product, direction, ts in slots:
        other = "down" if direction == "up" else "up"
        counterpart = slots.get((product, other, ts))
        if counterpart is None:
            raise ValueError("both directional eligibility records required")
        if (
            slots[(product, direction, ts)]["universe_member"]
            != counterpart["universe_member"]
        ):
            raise ValueError("boards must share the declared decision universe")
    return slots


def exposure_report(labels, eligibility, *, asof_ts_ms, ranker_slots=None):
    """Per-board causal exposure and own-direction retrospective gradability.

    Eligibility needs (product_id, direction, ts_ms, available_ts_ms) and four
    explicit booleans. Ranker slots are (product_id, direction, ts_ms) triples.
    Both directions are recorded for each submitted product/cutoff. This does
    not prove that the caller supplied the complete intended market universe.
    """
    assoc._integer(asof_ts_ms)
    metadata = provenance()
    rows, contract, evaluator = assoc._labels(labels, asof_ts_ms)
    slots = _slots(eligibility, asof_ts_ms)
    rankers = {}
    for name, records in (ranker_slots or {}).items():
        parsed = [_key(*record) for record in records]
        scored = set(parsed)
        if len(parsed) != len(scored):
            raise ValueError("duplicate directional ranker slot")
        if not scored <= slots.keys():
            raise ValueError("ranker slots must be recorded eligibility slots")
        rankers[assoc._text(name)] = scored
    boards, all_eligible_times = {}, set()
    for direction in assoc.DIRECTIONS:
        board = {(p, ts): f for (p, d, ts), f in slots.items() if d == direction}
        eligible, exclusions = set(), Counter()
        for key, flags in board.items():
            failed = next((f for f in assoc.ELIGIBILITY_FLAGS if not flags[f]), None)
            if failed is None:
                eligible.add(key)
            else:
                exclusions[failed] += 1
        all_eligible_times.update(ts for _, ts in eligible)
        scored_by_ranker = {
            name: {(p, ts) for p, d, ts in scored if d == direction}
            for name, scored in rankers.items()
        }
        shared = (
            set.intersection(*scored_by_ranker.values())
            if scored_by_ranker
            else set(eligible)
        )
        horizons = {}
        for horizon in assoc.HORIZONS:
            gradable, reasons = set(), Counter()
            for product, ts in sorted(eligible):
                label = rows.get((product, direction, horizon, ts))
                if ts + horizon * 1000 > asof_ts_ms:
                    reason = "immature_trailing_horizon"
                else:
                    outcome, reason = assoc._primary(label)
                    if outcome != "ungradable":
                        gradable.add((product, ts))
                if reason:
                    reasons[reason] += 1
            horizons[str(horizon)] = dict(
                horizon_seconds=horizon,
                gradable_slot_count=len(gradable),
                gradable_product_hours=assoc._hours(len(gradable)),
                ungradable_eligible_slot_count=len(eligible) - len(gradable),
                ungradable_reasons=dict(sorted(reasons.items())),
                gradable_fraction_of_eligible=assoc._ratio(
                    len(gradable), len(eligible)
                ),
                comparison=dict(
                    identical_complete_rows=[
                        list(k) for k in sorted(shared & gradable)
                    ],
                    identical_complete_row_count=len(shared & gradable),
                    definition="eligible_own_direction_ready_and_scored_by_every_ranker",
                    natural_ranker_coverage={
                        name: dict(
                            eligible_scored_slot_count=len(scored & eligible),
                            gradable_scored_slot_count=len(scored & gradable),
                        )
                        for name, scored in sorted(scored_by_ranker.items())
                    },
                ),
            )
        boards[direction] = dict(
            recorded_slot_count=len(board),
            decision_eligible_slot_count=len(eligible),
            decision_eligible_product_hours=assoc._hours(len(eligible)),
            board_wall_clock_hours_with_any_eligible_product=assoc._hours(
                len({ts for _, ts in eligible})
            ),
            exclusions_by_first_failed_flag={
                flag: exclusions[flag] for flag in assoc.ELIGIBILITY_FLAGS
            },
            horizons=horizons,
        )
    universe = Counter(
        ts
        for (_, direction, ts), flags in slots.items()
        if direction == "up" and flags["universe_member"]
    )
    return dict(
        **metadata,
        knowledge_asof_ts_ms=asof_ts_ms,
        target_contract_sha256=contract,
        target_evaluator_sha256=evaluator,
        universe_size_by_cutoff=[
            [ts, universe[ts]] for ts in sorted({ts for _, _, ts in slots})
        ],
        wall_clock_hours_with_either_board_eligible=assoc._hours(
            len(all_eligible_times)
        ),
        decision_universe_independent_of_future_labels=True,
        opposite_direction_label_required=False,
        legacy_joint_report_changed=False,
        boards=boards,
    )
