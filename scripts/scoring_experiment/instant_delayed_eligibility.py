"""Research-only delayed eligibility for an explicitly planned cutoff cohort."""

from dataclasses import dataclass
import json

from instant_coverage import _integer
from instant_delayed_decision import _check_prefix
from instant_input_evidence import BENCHMARK, DIRECTIONS


VERSION = "instant-delayed-eligibility-v1-draft"
FEATURES = ("F1", "F2", "F3", "F4", "F5")
BASELINES = ("volatility", "pace")


@dataclass(frozen=True)
class LocalDelivery:
    decision_sha256: str
    commit_observed_ts_ms: int
    consumer_seen_ts_ms: int | None


def _component_reasons(components, names, asof, clock):
    reasons = {}
    for name in names:
        row = components[name]
        if row["status"] == "ready":
            if _integer(row[clock]) > asof:
                raise ValueError("component evidence is later than decision as-of")
        elif row["status"] == "unavailable":
            reasons[name] = row["reason"]
        else:
            raise ValueError("unsupported component status")
    return reasons


def _delivery(decision, observation, deadline_age_ms):
    if observation is None:
        return dict(status="not_measured", commit_age_ms=None, consumer_age_ms=None)
    if observation.decision_sha256 != decision.sha256:
        raise ValueError("local delivery does not match decision digest")
    commit = _integer(observation.commit_observed_ts_ms)
    seen = observation.consumer_seen_ts_ms
    if commit < decision.decision_completed_ts_ms or (
        seen is not None and _integer(seen) < commit
    ):
        raise ValueError("local delivery clock precedes its input")
    cutoff = decision.feature_cutoff_ts_ms
    age = None if seen is None else seen - cutoff
    if age is None:
        status = "consumer_unobserved"
    elif deadline_age_ms is None:
        status = "observed"
    else:
        status = "within_bound" if age <= deadline_age_ms else "after_bound"
    return dict(status=status, commit_age_ms=commit - cutoff, consumer_age_ms=age)


def assess_cohort(
    recorder, cutoff, *, asof, decisions, local_deliveries=None, deadline_age_ms=None
):
    """Account for every recorder-declared product and direction at one cutoff.

    The caller chooses a post-warmup research cutoff. These are scoped input
    and local delivery diagnostics; this adapter emits no study eligibility.
    """
    _integer(cutoff)
    _integer(asof)
    if (
        recorder.failed
        or cutoff not in recorder.cutoffs
        or not recorder.inventory_recorded_ts_ms <= cutoff <= asof <= recorder._now()
    ):
        raise ValueError("declared cutoff and elapsed evidence as-of required")
    if deadline_age_ms is not None and _integer(deadline_age_ms) < 0:
        raise ValueError("nonnegative diagnostic deadline required")

    planned = [
        (product, direction)
        for product in recorder.products
        for direction in DIRECTIONS
    ]
    by_slot = {}
    for decision in decisions:
        key = (decision.product_id, decision.direction)
        if key not in planned or key in by_slot:
            raise ValueError("decision is outside the cohort or duplicated")
        if (decision.feature_cutoff_ts_ms, decision.knowledge_asof_ts_ms) != (
            cutoff,
            asof,
        ) or not asof <= decision.feature_computation_completed_ts_ms <= decision.decision_completed_ts_ms:
            raise ValueError("decision clocks do not match the cohort")
        by_slot[key] = decision
    deliveries = {} if local_deliveries is None else local_deliveries
    if deliveries.keys() - by_slot.keys():
        raise ValueError("local delivery without a planned decision")

    rows = []
    for key in planned:
        product, direction = key
        decision = by_slot.get(key)
        row = dict(
            product_id=product,
            direction=direction,
            role="benchmark" if product == BENCHMARK else "non_benchmark",
            input_status="decision_missing",
            feature_reasons=None,
            baseline_reasons=None,
            anchor_reasons=None,
            complete_vector_candidate=False,
            delivery=_delivery(decision, deliveries.get(key), deadline_age_ms),
        )
        if decision is not None:
            features = json.loads(decision.feature_json)
            _check_prefix(recorder, decision, features)
            row["feature_reasons"] = _component_reasons(
                features["features"], FEATURES, asof, "evidence_available_ts_ms"
            )
            row["baseline_reasons"] = _component_reasons(
                features["baseline"], BASELINES, asof, "inputs_available_ts_ms"
            )
            anchors = json.loads(decision.anchor_quotes_json)
            row["anchor_reasons"] = {
                pid: anchors[pid]["reason"]
                for pid in dict.fromkeys((product, BENCHMARK))
                if anchors[pid]["available"] is not True
            }
            ready = not (
                row["feature_reasons"]
                or row["baseline_reasons"]
                or row["anchor_reasons"]
            )
            row["input_status"] = "ready" if ready else "input_unavailable"
            row["complete_vector_candidate"] = ready and product != BENCHMARK
        rows.append(row)
    return dict(
        version=VERSION,
        cutoff_ts_ms=cutoff,
        knowledge_asof_ts_ms=asof,
        planned_rows=len(planned),
        deadline_age_ms=deadline_age_ms,
        inventory_sha256=recorder.inventory_sha256,
        study_eligible=False,
        rows=rows,
    )
