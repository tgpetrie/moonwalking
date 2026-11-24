"""Offline adapters from delayed-decision rows to the accepted reporters.

Two mappings, both evaluation-only and fail-closed:

* a later-cutoff grade becomes a label row `instant_association` accepts;
* a delayed eligibility cohort becomes paired directional slots
  `instant_directional_exposure` accepts.

Neither reporter is changed. Adapted rows carry this module's version and an
evaluator digest of their own, so they cannot be mixed with native v2 labels.
Pending and unavailable rows are preserved; nothing is coerced to `False`.

Exposure clock. The directional reporter requires eligibility to be known by
its cutoff. Delayed eligibility is known later by design. Under an explicit
`allowed_wait_ms`, a cohort known by `cutoff + allowed_wait_ms` is reported in
its cutoff slot (`ts_ms = available_ts_ms = cutoff`). The true knowledge time
and the wait travel on every slot as `known_at_ts_ms` and `allowed_wait_ms`.
A flag is `True` only when the assessment showed it by that deadline.
"""

import hashlib
import json
from pathlib import Path

import instant_association as assoc
import instant_delayed_decision as delayed
import instant_delayed_eligibility as eligibility
from instant_input_evidence import BENCHMARK


version = VERSION = "instant-delayed-bridge-v1-draft"
SOURCE = Path(__file__)
GRADE_SCOPE = "offline_cutoff_outcome_diagnostic"
SELF_RESIDUAL = "benchmark_self_residual_undefined"
GRADE_KEYS = (
    "version",
    "scope",
    "product_id",
    "direction",
    "feature_cutoff_ts_ms",
    "horizon_seconds",
    "horizon_end_ts_ms",
    "status",
    "cutoff_verified_forward",
    "impulse_rule_source_sha256",
    "decision_sha256",
    "publication_id",
    "published_ts_ms",
    "knowledge_asof_ts_ms",
)
READY_DETAILS = (
    "terminal_residual_log",
    "required_terminal_log",
    "peak_residual_log",
    "retention",
    "forward_match_count",
)
COHORT_KEYS = ("version", "cutoff_ts_ms", "knowledge_asof_ts_ms", "rows")
ROW_KEYS = (
    "product_id",
    "direction",
    "role",
    "input_status",
    "baseline_reasons",
    "complete_vector_candidate",
)
INPUT_STATUSES = ("decision_missing", "input_unavailable", "ready")


def _sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def provenance():
    source = _sha(SOURCE.read_text(encoding="utf-8"))
    identity = dict(
        bridge_version=VERSION,
        bridge_implementation_sha256=source,
        source_grade_version=delayed.GRADE_VERSION,
    )
    return dict(
        **identity,
        source_eligibility_version=eligibility.VERSION,
        # Stands in the label's evaluator slot; differs from any native evaluator.
        adapted_evaluator_sha256=_sha(json.dumps(identity, sort_keys=True)),
        label_source="adapted_delayed_cutoff_grade_not_native_v2_label",
        exposure_clock="cutoff_slot_under_declared_wait_not_knowledge_time",
        evaluation_only=True,
        fitting_allowed=False,
        live_integration=False,
        study_eligible=False,
    )


def grades_to_association_labels(grades, *, v2_contract_sha256):
    """Map later-cutoff grades to `instant_association.LABEL_KEYS` rows.

    A ready grade keeps its boolean outcome. Pending and unavailable grades stay
    incomplete with their reason. A ready grade for the benchmark itself, or one
    without a forward peak time, becomes unavailable with a reason.
    """
    contract = assoc._text(v2_contract_sha256)
    meta = provenance()
    labels, seen = [], set()
    for grade in grades:
        if not isinstance(grade, dict) or any(k not in grade for k in GRADE_KEYS):
            raise ValueError("malformed delayed grade row")
        if grade["version"] != delayed.GRADE_VERSION or grade["scope"] != GRADE_SCOPE:
            raise ValueError("unsupported grade version or scope")
        if grade["impulse_rule_source_sha256"] != contract:
            raise ValueError("grade was not computed under the declared v2 contract")
        product = assoc._text(grade["product_id"])
        direction, horizon = grade["direction"], grade["horizon_seconds"]
        if (
            direction not in assoc.DIRECTIONS
            or type(horizon) is not int
            or horizon not in assoc.HORIZONS
        ):
            raise ValueError("unsupported grade direction or horizon")
        anchor = assoc._grid(grade["feature_cutoff_ts_ms"])
        maturity = assoc._integer(grade["horizon_end_ts_ms"])
        if maturity != anchor + horizon * 1000:
            raise ValueError("grade horizon end must equal cutoff plus horizon")
        key = (product, direction, horizon, anchor)
        if key in seen:
            raise ValueError("duplicate delayed grade identity")
        seen.add(key)
        status, reason = grade["status"], grade.get("reason")
        forward, peak = grade["cutoff_verified_forward"], None
        if status == "ready":
            if type(forward) is not bool:
                raise ValueError("a ready grade needs a boolean outcome; never coerce")
            peak = grade.get("peak_ts_ms")
            if product == BENCHMARK:
                status, reason = "unavailable", SELF_RESIDUAL
            elif type(peak) is not int or not anchor <= peak <= maturity:
                status, reason = "unavailable", "grade_forward_peak_time_missing"
            if status != "ready":
                forward, peak = None, None
        elif status in ("pending", "unavailable"):
            if forward is not None:
                raise ValueError("an incomplete grade cannot carry an outcome")
        else:
            raise ValueError("unknown grade status")
        label = dict(
            product_id=product,
            anchor_ts_ms=anchor,
            direction=direction,
            horizon_seconds=horizon,
            status=status,
            verified_forward=forward,
            label_maturity_ts_ms=maturity,
            contract_version=assoc.TARGET_VERSION,
            contract_sha256=contract,
            evaluator_sha256=meta["adapted_evaluator_sha256"],
            reason=reason,
            evaluation_only=True,
            bridge_version=VERSION,
            label_source=meta["label_source"],
            source_grade_version=grade["version"],
            source_grade_status=grade["status"],
            decision_sha256=grade["decision_sha256"],
            publication_id=grade["publication_id"],
            published_ts_ms=grade["published_ts_ms"],
            grade_knowledge_asof_ts_ms=grade["knowledge_asof_ts_ms"],
        )
        if status == "ready":
            label["peak_ts_ms"] = peak
            label.update({k: grade[k] for k in READY_DETAILS if k in grade})
        labels.append(label)
    return labels


def _slot_reason(member, on_time, row):
    if not member:
        return SELF_RESIDUAL
    if not on_time:
        return "known_after_allowed_wait"
    if row["input_status"] == "decision_missing":
        return "decision_missing"
    if row["baseline_reasons"]:
        return "baseline_unavailable"
    return None if row["complete_vector_candidate"] else "input_unavailable"


def delayed_eligibility_to_directional_slots(cohort_assessments, *, allowed_wait_ms):
    """Map `assess_cohort` results to directional eligibility records.

    Every planned row is kept. The benchmark is recorded outside the decision
    universe. A cohort known after `cutoff + allowed_wait_ms` keeps its slots
    with nothing verified. The input is not modified.
    """
    wait = assoc._integer(allowed_wait_ms)
    slots, cutoffs = [], set()
    for cohort in cohort_assessments:
        if not isinstance(cohort, dict) or any(k not in cohort for k in COHORT_KEYS):
            raise ValueError("malformed delayed eligibility cohort")
        if cohort["version"] != eligibility.VERSION:
            raise ValueError("unsupported delayed eligibility version")
        cutoff = assoc._grid(cohort["cutoff_ts_ms"])
        known = assoc._integer(cohort["knowledge_asof_ts_ms"])
        if known < cutoff:
            raise ValueError("eligibility cannot be known before its cutoff")
        if cutoff in cutoffs:
            raise ValueError("duplicate cohort cutoff")
        cutoffs.add(cutoff)
        on_time = known <= cutoff + wait
        seen = set()
        for row in cohort["rows"]:
            if not isinstance(row, dict) or any(k not in row for k in ROW_KEYS):
                raise ValueError("malformed delayed eligibility row")
            product, direction = assoc._text(row["product_id"]), row["direction"]
            role, status = row["role"], row["input_status"]
            candidate = row["complete_vector_candidate"]
            if (
                direction not in assoc.DIRECTIONS
                or status not in INPUT_STATUSES
                or type(candidate) is not bool
                or role != ("benchmark" if product == BENCHMARK else "non_benchmark")
            ):
                raise ValueError("unsupported delayed eligibility row")
            member = product != BENCHMARK
            if candidate != (status == "ready" and member):
                raise ValueError("inconsistent delayed eligibility row")
            if (product, direction) in seen:
                raise ValueError("duplicate delayed eligibility slot")
            seen.add((product, direction))
            decided = on_time and status != "decision_missing"
            warm = decided and not row["baseline_reasons"]
            healthy = warm and status == "ready"
            slots.append(
                dict(
                    product_id=product,
                    direction=direction,
                    ts_ms=cutoff,
                    available_ts_ms=cutoff,
                    universe_member=member,
                    warmup_complete=warm,
                    health_verified=healthy,
                    candidate_eligible=healthy and member and candidate,
                    known_at_ts_ms=known,
                    allowed_wait_ms=wait,
                    known_within_allowed_wait=on_time,
                    bridge_reason=_slot_reason(member, on_time, row),
                    bridge_version=VERSION,
                )
            )
        if any(
            (product, other) not in seen
            for product, _ in seen
            for other in assoc.DIRECTIONS
        ):
            raise ValueError("both directions required for every cohort product")
    return slots
