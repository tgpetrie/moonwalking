"""Offline association and exposure reporting. No labels, fits or live code change.

Each alert keeps its primary pointwise outcome at its declared decision-cutoff
anchor and fixed horizon. Forward-window coverage is a separately named
diagnostic; it never forgives a pointwise failure and defines no physical onset.
"""

from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path

import instant_diagnostics as diag


VERSION = "instant-association-exposure-v1-draft"
CONTRACT = (
    Path(__file__).resolve().parents[2]
    / "docs/research/INSTANT_ASSOCIATION_CONTRACT_V1_DRAFT.json"
)
TARGET_VERSION = "instant-target-v2-draft"
GRID_MS = 5000
HORIZONS = (300, 900)
LEAD_LIMIT_SECONDS = 180
DIRECTIONS = ("up", "down")
LABEL_KEYS = (
    "product_id",
    "anchor_ts_ms",
    "direction",
    "horizon_seconds",
    "status",
    "verified_forward",
    "label_maturity_ts_ms",
    "contract_version",
    "contract_sha256",
    "evaluator_sha256",
)
ALERT_KEYS = (
    "publication_id",
    "product_id",
    "direction",
    "anchor_ts_ms",
    "inputs_available_ts_ms",
    "published_ts_ms",
)
ELIGIBILITY_FLAGS = (
    "universe_member",
    "warmup_complete",
    "health_verified",
    "candidate_eligible",
)


def _integer(value):
    if type(value) is not int or value < 0:
        raise ValueError("nonnegative integer required")
    return value


def _grid(value):
    if _integer(value) % GRID_MS:
        raise ValueError("timestamps must lie on the 5s grid")
    return value


def _text(value):
    if not isinstance(value, str) or not value:
        raise ValueError("nonempty string identity required")
    return value


def _hours(slot_count):
    return slot_count * GRID_MS / 3_600_000


def provenance():
    raw = CONTRACT.read_text(encoding="utf-8").encode("utf-8")
    cfg = json.loads(raw)
    if (
        cfg["version"] != VERSION
        or cfg["target_version"] != TARGET_VERSION
        or cfg["grid_ms"] != GRID_MS
        or tuple(cfg["horizons_seconds"]) != HORIZONS
        or cfg["lead_limit_seconds"] != LEAD_LIMIT_SECONDS
        or cfg["fitting_allowed"] is not False
        or cfg["operational_missed_move_rates_enabled"] is not False
    ):
        raise ValueError("association contract and implementation differ")
    return dict(
        association_version=VERSION,
        association_contract_sha256=hashlib.sha256(raw).hexdigest(),
        association_implementation_sha256=hashlib.sha256(
            Path(__file__).read_text(encoding="utf-8").encode("utf-8")
        ).hexdigest(),
        evaluation_only=True,
        physical_onset_defined=False,
        operational_missed_move_rates_enabled=False,
        fitting_allowed=False,
    )


def _labels(labels, asof):
    """Index complete v2 labels by identity; reject mixed or malformed rows."""
    rows, contracts, evaluators = {}, set(), set()
    for row in labels:
        if not isinstance(row, dict) or any(k not in row for k in LABEL_KEYS):
            raise ValueError("malformed label row")
        if row["contract_version"] != TARGET_VERSION:
            raise ValueError("labels must come from the explicit v2 target draft")
        product, direction, horizon = (
            _text(row["product_id"]),
            row["direction"],
            row["horizon_seconds"],
        )
        if (
            direction not in DIRECTIONS
            or type(horizon) is not int
            or horizon not in HORIZONS
        ):
            raise ValueError("unsupported label direction or horizon")
        anchor, maturity = _grid(row["anchor_ts_ms"]), _integer(
            row["label_maturity_ts_ms"]
        )
        if maturity != anchor + horizon * 1000:
            raise ValueError("label maturity must equal anchor plus horizon")
        status, forward = row["status"], row["verified_forward"]
        if status == "ready":
            if type(forward) is not bool:
                raise ValueError("a ready label needs a boolean outcome; never coerce")
            if maturity > asof:
                raise ValueError("a ready label cannot mature after the report as-of")
            peak = row.get("peak_ts_ms")
            if type(peak) is not int or not anchor <= peak <= maturity:
                raise ValueError("a ready label needs a forward peak inside its window")
        elif status in ("pending", "unavailable"):
            if forward is not None:
                raise ValueError("an incomplete label cannot carry an outcome")
        else:
            raise ValueError("unknown label status")
        contracts.add(_text(row["contract_sha256"]))
        evaluators.add(_text(row["evaluator_sha256"]))
        key = (product, direction, horizon, anchor)
        if key in rows:
            raise ValueError("duplicate label identity")
        rows[key] = row
    if len(contracts) > 1 or len(evaluators) > 1:
        raise ValueError("cannot mix target contract or evaluator provenance")
    return rows, next(iter(contracts), None), next(iter(evaluators), None)


def _alerts(alerts, asof):
    """Retain anchor, input availability and actual publication separately."""
    out = {}
    for row in alerts:
        if not isinstance(row, dict) or any(k not in row for k in ALERT_KEYS):
            raise ValueError("malformed alert row")
        pid = _text(row["publication_id"])
        if pid in out:
            raise ValueError("duplicate publication identity")
        if row["direction"] not in DIRECTIONS:
            raise ValueError("unsupported alert direction")
        anchor, inputs, published = (
            _grid(row["anchor_ts_ms"]),
            _integer(row["inputs_available_ts_ms"]),
            _integer(row["published_ts_ms"]),
        )
        if not anchor <= inputs <= published <= asof:
            raise ValueError(
                "alert clocks must satisfy anchor <= inputs available <= published"
                " <= as-of; no late feature is known at an earlier anchor"
            )
        out[pid] = dict(
            publication_id=pid,
            product_id=_text(row["product_id"]),
            direction=row["direction"],
            anchor_ts_ms=anchor,
            inputs_available_ts_ms=inputs,
            published_ts_ms=published,
            input_lag_ms=inputs - anchor,
            publication_delay_ms=published - anchor,
            inputs_known_at_anchor=inputs == anchor,
        )
    return sorted(
        out.values(), key=lambda a: (a["published_ts_ms"], a["publication_id"])
    )


def _primary(label):
    if label is None:
        return "ungradable", "label_missing"
    if label["status"] == "ready":
        return ("success" if label["verified_forward"] else "failure"), None
    return "ungradable", f"{label['status']}:{label.get('reason') or 'no_reason'}"


def _ratio(numerator, denominator):
    return numerator / denominator if denominator else None


def association_report(labels, alerts, *, asof_ts_ms):
    """Primary pointwise outcomes per horizon plus forward-window coverage."""
    _integer(asof_ts_ms)
    rows, contract_sha256, evaluator_sha256 = _labels(labels, asof_ts_ms)
    pubs = _alerts(alerts, asof_ts_ms)
    windows = {}
    for window in diag.forward_catalog_report(list(rows.values())):
        key = window["product_id"], window["direction"], window["horizon_seconds"]
        windows.setdefault(key, []).append(window)
    lead_ms = LEAD_LIMIT_SECONDS * 1000
    tables, forgiven = {}, 0
    for horizon in HORIZONS:
        outcomes, counts, reasons = [], Counter(), Counter()
        for alert in pubs:
            label = rows.get(
                (
                    alert["product_id"],
                    alert["direction"],
                    horizon,
                    alert["anchor_ts_ms"],
                )
            )
            outcome, reason = _primary(label)
            counts[outcome] += 1
            if reason:
                reasons[reason] += 1
            outcomes.append(
                {
                    **alert,
                    "horizon_seconds": horizon,
                    "primary_outcome": outcome,
                    "ungradable_reason": reason,
                    "label_status": label["status"] if label else None,
                    "verified_forward": label["verified_forward"] if label else None,
                    "covers_forward_window_anchor_ts_ms": None,
                }
            )
        covered, uncovered, used = [], [], {}
        for (product, direction, h), group in sorted(windows.items()):
            if h != horizon:
                continue
            candidates = [
                a
                for a in pubs
                if a["product_id"] == product and a["direction"] == direction
            ]
            for window in sorted(group, key=lambda w: w["anchor_ts_ms"]):
                start, peak = window["anchor_ts_ms"] - lead_ms, window["peak_ts_ms"]
                chosen = next(
                    (
                        a
                        for a in candidates
                        if a["publication_id"] not in used
                        and start <= a["published_ts_ms"] <= peak
                    ),
                    None,
                )
                record = dict(
                    product_id=product,
                    direction=direction,
                    horizon_seconds=horizon,
                    anchor_ts_ms=window["anchor_ts_ms"],
                    forward_peak_ts_ms=peak,
                    label_maturity_ts_ms=window["label_maturity_ts_ms"],
                    edge_start_ts_ms=start,
                    left_censored=window["left_censored"],
                    left_censor_reason=window["left_censor_reason"],
                    covering_publication_id=None,
                    covering_published_ts_ms=None,
                    covering_offset_from_anchor_seconds=None,
                )
                if chosen is None:
                    uncovered.append(record)
                    continue
                used[chosen["publication_id"]] = window["anchor_ts_ms"]
                record.update(
                    covering_publication_id=chosen["publication_id"],
                    covering_published_ts_ms=chosen["published_ts_ms"],
                    covering_offset_from_anchor_seconds=(
                        chosen["published_ts_ms"] - window["anchor_ts_ms"]
                    )
                    / 1000,
                )
                covered.append(record)
        for row in outcomes:
            row["covers_forward_window_anchor_ts_ms"] = used.get(row["publication_id"])
            if row["primary_outcome"] == "failure" and row["publication_id"] in used:
                forgiven += 1
        unmatched = [
            a["publication_id"] for a in pubs if a["publication_id"] not in used
        ]
        window_count = len(covered) + len(uncovered)
        success, failure = counts["success"], counts["failure"]
        tables[str(horizon)] = dict(
            horizon_seconds=horizon,
            primary_pointwise=dict(
                alert_count=len(pubs),
                success_count=success,
                failure_count=failure,
                ungradable_count=counts["ungradable"],
                ungradable_reasons=dict(sorted(reasons.items())),
                graded_fraction=_ratio(success + failure, len(pubs)),
                success_rate_among_graded=_ratio(success, success + failure),
                outcomes=outcomes,
            ),
            forward_window_coverage=dict(
                association_kind="forward_window_not_physical_impulse",
                window_count=window_count,
                covered_count=len(covered),
                uncovered_count=len(uncovered),
                uncovered_forward_window_rate=_ratio(len(uncovered), window_count),
                conditional_catalog_coverage_rate=_ratio(len(covered), window_count),
                left_censored_window_count=sum(
                    w["left_censored"] for w in covered + uncovered
                ),
                alerts_without_forward_window_count=len(unmatched),
                alerts_without_forward_window=unmatched,
                covered_windows=covered,
                uncovered_windows=uncovered,
                physical_missed_move_rate=None,
            ),
        )
    return dict(
        **provenance(),
        knowledge_asof_ts_ms=asof_ts_ms,
        target_contract_sha256=contract_sha256,
        target_evaluator_sha256=evaluator_sha256,
        label_count=len(rows),
        alert_count=len(pubs),
        failed_alerts_that_cover_a_forward_window=forgiven,
        association_alters_primary_outcomes=False,
        horizons=tables,
    )


def exposure_report(labels, eligibility, *, asof_ts_ms, ranker_slots=None):
    """Causal decision-eligible exposure, separately from retrospective gradability."""
    _integer(asof_ts_ms)
    rows, contract_sha256, evaluator_sha256 = _labels(labels, asof_ts_ms)
    slots = {}
    for record in eligibility:
        if (
            not isinstance(record, dict)
            or "product_id" not in record
            or "ts_ms" not in record
            or any(type(record.get(flag)) is not bool for flag in ELIGIBILITY_FLAGS)
        ):
            raise ValueError(
                "explicit boolean eligibility flags required; never coerce"
            )
        key = _text(record["product_id"]), _grid(record["ts_ms"])
        if key[1] > asof_ts_ms:
            raise ValueError("eligibility after the report as-of is not known")
        if key in slots:
            raise ValueError("duplicate or overlapping eligibility slot")
        slots[key] = {flag: record[flag] for flag in ELIGIBILITY_FLAGS}
    universe = Counter(ts for (_, ts), f in slots.items() if f["universe_member"])
    cutoffs = sorted({ts for _, ts in slots})
    sizes = [[ts, universe.get(ts, 0)] for ts in cutoffs]
    eligible, exclusions = set(), Counter()
    for key, flags in slots.items():
        failed = next((flag for flag in ELIGIBILITY_FLAGS if not flags[flag]), None)
        if failed is None:
            eligible.add(key)
        else:
            exclusions[failed] += 1
    rankers = {}
    for name, scored in (ranker_slots or {}).items():
        records = [(_text(p), _grid(ts)) for p, ts in scored]
        scored = set(records)
        if len(scored) != len(records):
            raise ValueError("duplicate ranker slot")
        if not scored <= set(slots):
            raise ValueError("ranker slots must be recorded eligibility slots")
        rankers[_text(name)] = scored
    horizons = {}
    for horizon in HORIZONS:
        gradable, reasons = set(), Counter()
        for product, ts in sorted(eligible):
            reason = None
            if ts + horizon * 1000 > asof_ts_ms:
                reason = "immature_trailing_horizon"
            for direction in DIRECTIONS if reason is None else ():
                label = rows.get((product, direction, horizon, ts))
                if label is None:
                    reason = f"label_missing:{direction}"
                elif label["status"] != "ready":
                    reason = f"{label['status']}:{direction}:{label.get('reason')}"
                if reason:
                    break
            if reason:
                reasons[reason] += 1
            else:
                gradable.add((product, ts))
        shared = set.intersection(*rankers.values()) if rankers else set(eligible)
        horizons[str(horizon)] = dict(
            horizon_seconds=horizon,
            gradable_slot_count=len(gradable),
            gradable_product_hours=_hours(len(gradable)),
            ungradable_eligible_slot_count=len(eligible) - len(gradable),
            ungradable_reasons=dict(sorted(reasons.items())),
            gradable_fraction_of_eligible=_ratio(len(gradable), len(eligible)),
            comparison=dict(
                identical_complete_row_count=len(shared & gradable),
                identical_complete_rows_definition=(
                    "decision_eligible_and_gradable_and_scored_by_every_ranker"
                ),
                natural_ranker_coverage={
                    name: dict(
                        eligible_scored_slot_count=len(scored & eligible),
                        gradable_scored_slot_count=len(scored & gradable),
                    )
                    for name, scored in sorted(rankers.items())
                },
            ),
        )
    return dict(
        **provenance(),
        knowledge_asof_ts_ms=asof_ts_ms,
        target_contract_sha256=contract_sha256,
        target_evaluator_sha256=evaluator_sha256,
        recorded_slot_count=len(slots),
        decision_eligible_slot_count=len(eligible),
        decision_eligible_product_hours=_hours(len(eligible)),
        board_wall_clock_hours_with_any_eligible_product=_hours(
            len({ts for _, ts in eligible})
        ),
        board_wall_clock_hours_with_any_verified_health=_hours(
            len({ts for (_, ts), f in slots.items() if f["health_verified"]})
        ),
        exclusions_by_first_failed_flag=dict(
            (flag, exclusions[flag]) for flag in ELIGIBILITY_FLAGS
        ),
        universe_size_by_cutoff=sizes,
        universe_size_first=sizes[0][1] if sizes else None,
        universe_size_last=sizes[-1][1] if sizes else None,
        universe_size_min=min((s for _, s in sizes), default=None),
        universe_size_max=max((s for _, s in sizes), default=None),
        decision_universe_independent_of_future_labels=True,
        horizons=horizons,
    )


def report(labels, alerts, eligibility, *, asof_ts_ms, ranker_slots=None):
    labels = list(labels)
    return dict(
        **provenance(),
        knowledge_asof_ts_ms=asof_ts_ms,
        association=association_report(labels, alerts, asof_ts_ms=asof_ts_ms),
        exposure=exposure_report(
            labels, eligibility, asof_ts_ms=asof_ts_ms, ranker_slots=ranker_slots
        ),
    )
