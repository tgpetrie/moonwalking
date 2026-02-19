import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import _json_sanitize_for_api, _normalize_alert


def test_json_sanitize_collapses_binary_float_noise():
    payload = {
        "vol1h_now": 652863.3300000001,
        "nested": {"pct": 0.30000000000000004},
        "price_now": 0.1234567890123,
        "z_vol": 3.1415926535,
    }

    out = _json_sanitize_for_api(payload)

    assert out["vol1h_now"] == 652863.33
    assert out["nested"]["pct"] == 0.3
    assert out["price_now"] == 0.123457
    assert out["z_vol"] == 3.14


def test_normalize_alert_cleans_message_float_artifacts():
    raw = {
        "id": "x1",
        "symbol": "BTC-USD",
        "type": "whale_move",
        "severity": "high",
        "message": "BTC-USD up +0.30000000000000004% on 652863.3300000001 units",
        "ts": "2026-02-18T00:00:00+00:00",
        "event_ts_ms": 1771372800000,
        "evidence": {"vol1h_now": 652863.3300000001},
    }

    norm = _normalize_alert(raw)
    msg = norm["message"]

    assert "0.30000000000000004" not in msg
    assert "652863.3300000001" not in msg
    assert "+0.3%" in msg
    assert "652863.33" in msg
