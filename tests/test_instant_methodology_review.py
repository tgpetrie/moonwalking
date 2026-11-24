"""Contract counterexamples for the November 6 static methodology review.

These synthetic checks preserve existing clocks. They do not implement a
delayed-decision adapter, select a lag threshold or test predictive value.
"""

from dataclasses import replace
import sys

import pytest

from test_instant_targets import ANCHOR, ROOT, baseline, samples, target

sys.path.insert(0, str(ROOT / "scripts/scoring_experiment"))
import instant_directional_exposure as directional
from instant_publication import publication_timing


@pytest.mark.parametrize("contract", [target.CONTRACT_PATH, target.V2_CONTRACT_PATH])
@pytest.mark.parametrize("direction", ["up", "down"])
def test_sample_availability_cannot_be_redefined_as_just_receipt(contract, direction):
    rows = samples(direction=direction)
    engine = target.TargetEvaluator(rows, contract_path=contract)
    base = baseline(
        end_ts_ms=(
            (ANCHOR - 35000) // 60000 * 60000
            if contract == target.V2_CONTRACT_PATH
            else ANCHOR
        )
    )
    assert (
        engine.evaluate(ANCHOR, base, direction, 300, ANCHOR + 300000)["status"]
        == "ready"
    )
    # Even grading much later cannot make the anchor's delayed input known then.
    late = [
        replace(r, available_ts_ms=ANCHOR + 180) if r.ts_ms == ANCHOR else r
        for r in rows
    ]
    result = target.TargetEvaluator(late, contract_path=contract).evaluate(
        ANCHOR, base, direction, 300, ANCHOR + 900000
    )
    assert result["status"] == "unavailable"
    assert result["reason"] == "future_receipt"


def test_publication_chronology_does_not_authorize_late_cutoff_eligibility():
    timing = publication_timing(
        publication_id="synthetic",
        product_id="TEST-USD",
        feature_cutoff=ANCHOR,
        inputs_available=ANCHOR + 180,
        decision_completed=ANCHOR + 210,
        published=ANCHOR + 250,
    )
    assert timing.legacy_cutoff_inputs_compatible is False
    assert timing.eligible_for_fitting is False
    records = [
        dict(
            product_id="TEST-USD",
            direction=d,
            ts_ms=ANCHOR,
            available_ts_ms=ANCHOR + 180,
            universe_member=True,
            warmup_complete=True,
            health_verified=True,
            candidate_eligible=True,
        )
        for d in ("up", "down")
    ]
    with pytest.raises(ValueError, match="known by its cutoff"):
        directional.exposure_report([], records, asof_ts_ms=ANCHOR + 900000)


def test_one_hour_merge_wait_cannot_guarantee_a_2500ms_publication_budget():
    # Hypothetical 1s wait for the boundary heartbeat plus 1,993ms merge wait.
    # The preserved-hour maximum is an observed component, not a whole-pipeline cap.
    available = ANCHOR + 1000 + 1993
    timing = publication_timing(
        publication_id="synthetic-budget",
        product_id="TEST-USD",
        feature_cutoff=ANCHOR,
        inputs_available=available,
        decision_completed=available + 20,
        published=available + 40,
        max_feature_age_ms=2500,
    )
    assert timing.verification_lag_from_cutoff_ms == 2993
    assert timing.within_declared_feature_age is False
    assert timing.readiness_reason == "feature_window_too_old"
    assert timing.eligible_for_fitting is False
