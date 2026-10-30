"""Versioned offline reporting; does not alter target labels or live scores."""

import hashlib
import json
from pathlib import Path

import instant_targets as target


CONTRACT_PATH = target.CONTRACT_PATH.with_name(
    "INSTANT_DIAGNOSTIC_CONTRACT_V1_DRAFT.json"
)


def provenance():
    raw = CONTRACT_PATH.read_text(encoding="utf-8").encode("utf-8")
    cfg = json.loads(raw)
    return dict(
        diagnostic_version=cfg["version"],
        diagnostic_contract_sha256=hashlib.sha256(raw).hexdigest(),
        diagnostic_implementation_sha256=hashlib.sha256(
            Path(__file__).read_text(encoding="utf-8").encode("utf-8")
        ).hexdigest(),
    )


def fraction_reason(label, peak):
    if label.get("pre_window_reference_status") != "ready":
        return (
            label.get("pre_window_reference_reason")
            or "pre_window_reference_unavailable"
        )
    if not target.finite(peak):
        return "invalid_pre_window_peak"
    if peak <= 0:
        return "nonpositive_pre_window_peak"
    return None


def alert_report(evaluator, label, publish_ts_ms, *, strict_trigger=False):
    """Keep the original result intact; append explicitly named diagnostics."""
    if not evaluator.is_v2:
        raise ValueError("diagnostics require the explicit v2 target draft")
    timing = (
        evaluator.alert_timing(label, publish_ts_ms)
        if strict_trigger
        else evaluator.forward_alert_timing(label, publish_ts_ms)
    )
    output = {**timing, **provenance()}
    output.setdefault("pre_window_consumed_fraction", None)
    output.update(
        target_contract_sha256=evaluator.contract_sha256,
        target_evaluator_sha256=evaluator.implementation_sha256,
        pre_window_consumed_fraction_reason=None,
        pre_window_to_forward_peak_consumed_fraction=None,
        pre_window_to_forward_peak_consumed_fraction_reason=None,
        pre_window_to_forward_peak_ts_ms=None,
        whole_window_peak_precedes_anchor=None,
        pre_window_reference_unavailable_reason=(
            label.get("pre_window_reference_reason")
            or "pre_window_reference_unavailable"
            if label.get("pre_window_reference_status") != "ready"
            else None
        ),
        publication_unavailable_reason=(
            timing.get("reason") or "publication_unavailable"
            if timing["timing"] in ("unavailable", "outside_event_window")
            else None
        ),
    )
    whole_reason = fraction_reason(label, label.get("pre_window_peak_residual_log"))
    if timing["timing"] in ("unavailable", "outside_event_window"):
        reason = whole_reason or timing.get("reason") or "publication_unavailable"
        output["pre_window_consumed_fraction_reason"] = reason
        output["pre_window_to_forward_peak_consumed_fraction_reason"] = reason
        return output
    output["pre_window_consumed_fraction_reason"] = whole_reason
    if label.get("pre_window_reference_status") != "ready":
        output["pre_window_to_forward_peak_consumed_fraction_reason"] = whole_reason
        return output
    reference = label["pre_window_reference_ts_ms"]
    sign = 1 if label["direction"] == "up" else -1
    peak_ts = label["peak_ts_ms"]
    forward_peak = evaluator._residual(reference, peak_ts, label["beta"], sign)
    alternative_reason = fraction_reason(label, forward_peak)
    output.update(
        pre_window_to_forward_peak_ts_ms=peak_ts,
        pre_window_to_forward_peak_consumed_fraction_reason=alternative_reason,
        whole_window_peak_precedes_anchor=(
            label["pre_window_peak_ts_ms"] < label["anchor_ts_ms"]
        ),
    )
    if alternative_reason is None:
        output["pre_window_to_forward_peak_consumed_fraction"] = (
            evaluator._residual(
                reference, timing["price_snapshot_ts_ms"], label["beta"], sign
            )
            / forward_peak
        )
    return output


def forward_catalog_report(labels):
    """Annotate sampling-edge/gap censoring without changing catalog selection."""
    labels = list(labels)
    status = {}
    for row in labels:
        key = tuple(
            row[k]
            for k in ("product_id", "direction", "horizon_seconds", "anchor_ts_ms")
        )
        if key in status:
            raise ValueError("duplicate catalog anchor")
        status[key] = row.get("status")
    output = []
    for row in target.forward_event_catalog(labels):
        key = tuple(row[k] for k in ("product_id", "direction", "horizon_seconds"))
        previous = status.get((*key, row["anchor_ts_ms"] - 5000))
        output.append(
            {
                **row,
                **provenance(),
                "previous_anchor_status": previous,
                "left_censored": previous != "ready",
                "left_censor_reason": (
                    None
                    if previous == "ready"
                    else previous or "previous_anchor_missing"
                ),
            }
        )
    return output
