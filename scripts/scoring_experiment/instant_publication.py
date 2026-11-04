"""Offline publication-clock diagnostics. No target labels or live decisions."""

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path

from instant_coverage import _integer


VERSION = "instant-publication-clock-v1-draft"
CONTRACT = (
    Path(__file__).resolve().parents[2]
    / "docs/research/INSTANT_PUBLICATION_CONTRACT_V1_DRAFT.json"
)


@dataclass(frozen=True)
class PublicationTiming:
    version: str
    publication_id: str
    product_id: str
    feature_cutoff_ts_ms: int
    inputs_available_ts_ms: int
    decision_completed_ts_ms: int
    published_ts_ms: int
    feature_age_at_publication_ms: int
    verification_lag_from_cutoff_ms: int
    decision_to_publication_ms: int
    legacy_cutoff_inputs_compatible: bool
    publication_target_amendment_required: bool
    max_feature_age_ms: int | None
    within_declared_feature_age: bool | None
    readiness_reason: str
    eligible_for_fitting: bool
    contract_sha256: str
    implementation_sha256: str


def publication_timing(
    *,
    publication_id,
    product_id,
    feature_cutoff,
    inputs_available,
    decision_completed,
    published,
    max_feature_age_ms=None
):
    """Record explicit clocks; a supplied age bound is not study approval.

    Caller clocks/provenance remain trusted. A later proof is representable
    here but must never be put into an old Sample as if known at its cutoff.
    This validates chronology only; it does not prove durable publication.
    """
    raw = CONTRACT.read_text(encoding="utf-8").encode("utf-8")
    cfg = json.loads(raw)
    if (
        cfg["version"] != VERSION
        or cfg["grid_ms"] != 5000
        or cfg["fitting_allowed"] is not False
    ):
        raise ValueError("publication contract and implementation differ")
    for value in (feature_cutoff, inputs_available, decision_completed, published):
        _integer(value)
    if (
        not isinstance(publication_id, str)
        or not publication_id
        or not isinstance(product_id, str)
        or not product_id
        or feature_cutoff % 5000
        or not feature_cutoff <= decision_completed <= published
        or not feature_cutoff <= inputs_available <= decision_completed
    ):
        raise ValueError(
            "identity, grid cutoff and causal processing/publication clocks required"
        )
    if max_feature_age_ms is not None:
        _integer(max_feature_age_ms)
    age = published - feature_cutoff
    within = age <= max_feature_age_ms if max_feature_age_ms is not None else None
    return PublicationTiming(
        VERSION,
        publication_id,
        product_id,
        feature_cutoff,
        inputs_available,
        decision_completed,
        published,
        age,
        max(0, inputs_available - feature_cutoff),
        published - decision_completed,
        inputs_available <= feature_cutoff,
        published != feature_cutoff or inputs_available > feature_cutoff,
        max_feature_age_ms,
        within,
        (
            "publication_age_policy_unfrozen"
            if within is None
            else (
                "feature_window_too_old"
                if not within
                else "study_and_source_gates_unfrozen"
            )
        ),
        False,
        hashlib.sha256(raw).hexdigest(),
        hashlib.sha256(
            Path(__file__).read_text(encoding="utf-8").encode("utf-8")
        ).hexdigest(),
    )
