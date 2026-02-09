import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import _has_numeric_evidence, _is_number


def test_has_numeric_evidence_false_without_numeric_values():
    alert = {
        "type": "whale_move",
        "symbol": "BTC-USD",
        "evidence": {
            "note": "flow spike",
            "baseline_ready": True,
            "details": {"regime": "hot"},
        },
    }
    assert _has_numeric_evidence(alert) is False


def test_has_numeric_evidence_true_with_numeric_values():
    alert = {
        "type": "whale_move",
        "symbol": "BTC-USD",
        "evidence": {
            "volume_change_1h_pct": 132.4,
            "details": {"pct_3m": 0.22},
        },
    }
    assert _has_numeric_evidence(alert) is True


def test_is_number_rejects_bool_values():
    assert _is_number(True) is False
    assert _is_number(False) is False
