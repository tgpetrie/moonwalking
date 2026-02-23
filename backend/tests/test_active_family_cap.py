import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import _cap_active_alert_families


def _mk_alert(alert_id: str, symbol: str, typ: str, pct: float = 1.0) -> dict:
    return {
        "id": alert_id,
        "symbol": symbol,
        "type": typ,
        "severity": "high",
        "event_ts_ms": 1771372800000,
        "evidence": {"pct_1m": pct},
    }


def test_active_family_cap_limits_whale_and_stealth():
    items = [
        _mk_alert("w1", "BTC-USD", "whale_move", 2.1),
        _mk_alert("w2", "ETH-USD", "whale_move", 1.8),
        _mk_alert("w3", "SOL-USD", "whale_move", 1.7),
        _mk_alert("w4", "ADA-USD", "whale_move", 1.6),  # should be capped out
        _mk_alert("s1", "BTC-USD", "stealth_move", 0.9),
        _mk_alert("s2", "ETH-USD", "stealth_move", 0.8),
        _mk_alert("s3", "SOL-USD", "stealth_move", 0.7),
        _mk_alert("s4", "ADA-USD", "stealth_move", 0.6),  # should be capped out
    ]

    out = _cap_active_alert_families(
        items,
        capped_families={"whale", "stealth"},
        per_symbol_family_max=1,
        per_family_max=3,
    )

    whale = [a for a in out if a.get("type") == "whale_move"]
    stealth = [a for a in out if a.get("type") == "stealth_move"]
    assert len(whale) == 3
    assert len(stealth) == 3


def test_active_family_cap_keeps_non_capped_families():
    items = [
        _mk_alert("c1", "BTC-USD", "coin_persistent_gainer", 2.0),
        _mk_alert("c2", "ETH-USD", "coin_persistent_loser", -2.1),
        _mk_alert("d1", "SOL-USD", "divergence", 1.2),
    ]

    out = _cap_active_alert_families(items, capped_families={"whale", "stealth"})
    assert len(out) == len(items)
