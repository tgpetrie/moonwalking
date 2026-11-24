"""Protect the outcome-blind episode mask and frozen timing rules."""
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("freeze_live", ROOT / "scripts/scoring_experiment/freeze_live_contract.py")
freeze = importlib.util.module_from_spec(spec)
spec.loader.exec_module(freeze)
CFG = json.loads((ROOT / "docs/research/results/live_movers_contract_20261027/CONTRACT_PRODUCTION.json").read_text())


def row(ts=None):
    ts = ts or freeze.stamp("2026-09-01T12:00:00+00:00")
    return dict(id=1, product_id="AAA-USD", board="confirmation_3m_up", direction="up", entered_ts=ts,
                feature_schema_version="live-strength-v1-snapshot-v2", start_price=10,
                feature_snapshot_json=json.dumps(dict(captured_ts=ts-1, model_version="live-strength-v1", live_score=62,
                    raw_inputs=dict(pct_1m=1, pct_3m=2, volume_change_1h_pct=20))),
                gross_return_5m=1, gross_return_15m=-1)


def test_magnitudes_and_signs_do_not_change_eligibility():
    a = row()
    b = {**a, "gross_return_5m": -95, "gross_return_15m": 200}
    assert freeze.classify(a, CFG, {})[:2] == freeze.classify(b, CFG, {})[:2] == ("train", None)


def test_future_snapshot_is_rejected():
    a = row()
    snap = json.loads(a["feature_snapshot_json"])
    snap["captured_ts"] = a["entered_ts"] + 1
    a["feature_snapshot_json"] = json.dumps(snap)
    assert freeze.classify(a, CFG, {})[1] == "snapshot_timestamp"


def test_missing_first_episode_does_not_select_a_more_complete_duplicate():
    a = row()
    b = row(a["entered_ts"] + 30)
    a["feature_snapshot_json"] = None
    cooldown = {}
    assert freeze.classify(a, CFG, cooldown)[1] == "missing_snapshot"
    assert freeze.classify(b, CFG, cooldown)[1] == "rolling_cooldown"


def test_missing_required_feature_is_not_imputed():
    a = row()
    snap = json.loads(a["feature_snapshot_json"])
    snap["raw_inputs"]["volume_change_1h_pct"] = None
    a["feature_snapshot_json"] = json.dumps(snap)
    assert freeze.classify(a, CFG, {})[1] == "required_features_missing"


def test_purge_and_test_boundaries():
    boundary = freeze.stamp(CFG["phases"]["discovery"][0])
    assert freeze.phase_at(boundary-1801, CFG) == "train"
    assert freeze.phase_at(boundary-1800, CFG) is None
    assert freeze.phase_at(boundary, CFG) == "discovery"
    assert freeze.phase_at(freeze.stamp(CFG["decision_cutoff_exclusive_utc"]), CFG) is None


def test_primary_contract_excludes_unretained_microstructure():
    assert {"pct_30s", "spread_bps", "signed_taker_flow"} <= set(CFG["excluded_primary_features"])
    assert not set(CFG["required_raw_features"]) & set(CFG["forward_only_features"])
