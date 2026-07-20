import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app


def test_prune_drops_old_keys():
    app._ALERT_STREAM_LAST_SEEN.clear()
    app._ALERT_STREAM_LAST_PRUNE_S = 0.0
    app._ALERT_STREAM_DEDUPE_WINDOW_S = 60
    app._ALERT_STREAM_DEDUPE_PRUNE_INTERVAL_S = 0

    now_s = 10_000.0
    # Older than 2x window => should be removed.
    app._ALERT_STREAM_LAST_SEEN["old"] = (now_s - 121.0, 1.0)
    # Inside retention window => should stay.
    app._ALERT_STREAM_LAST_SEEN["fresh"] = (now_s - 10.0, 1.0)

    app._prune_alert_stream_dedupe(now_s)

    assert "old" not in app._ALERT_STREAM_LAST_SEEN
    assert "fresh" in app._ALERT_STREAM_LAST_SEEN


def test_prune_enforces_max_key_cap():
    app._ALERT_STREAM_LAST_SEEN.clear()
    app._ALERT_STREAM_LAST_PRUNE_S = 0.0
    app._ALERT_STREAM_DEDUPE_WINDOW_S = 60
    app._ALERT_STREAM_DEDUPE_PRUNE_INTERVAL_S = 0
    app._ALERT_STREAM_DEDUPE_MAX_KEYS = 3

    now_s = 20_000.0
    # Keep all keys "fresh" so only cap logic applies.
    app._ALERT_STREAM_LAST_SEEN["k1"] = (now_s - 1.0, 1.0)
    app._ALERT_STREAM_LAST_SEEN["k2"] = (now_s - 2.0, 1.0)
    app._ALERT_STREAM_LAST_SEEN["k3"] = (now_s - 3.0, 1.0)
    app._ALERT_STREAM_LAST_SEEN["k4"] = (now_s - 4.0, 1.0)
    app._ALERT_STREAM_LAST_SEEN["k5"] = (now_s - 5.0, 1.0)

    app._prune_alert_stream_dedupe(now_s)

    assert len(app._ALERT_STREAM_LAST_SEEN) == 3
    # Oldest keys should be evicted first.
    assert "k5" not in app._ALERT_STREAM_LAST_SEEN
    assert "k4" not in app._ALERT_STREAM_LAST_SEEN


def test_active_reducer_honors_alert_expiry_over_endpoint_fallback(monkeypatch):
    now_ms = 1_800_000_000_000
    monkeypatch.setattr(app, "_utc_now_ts_ms", lambda: now_ms)
    rows = [
        {
            "id": "expired",
            "symbol": "SOL-USD",
            "type_key": "breakout",
            "severity": "high",
            "event_ts_ms": now_ms - 30_000,
            "expires_at": now_ms - 1_000,
            "evidence": {},
        },
        {
            "id": "still-live",
            "symbol": "BTC-USD",
            "type_key": "breakout",
            "severity": "high",
            "event_ts_ms": now_ms - 500_000,
            "expires_at": now_ms + 10_000,
            "evidence": {},
        },
    ]

    active = app._reduce_active_alerts(rows, ttl_s=120)

    assert [row["id"] for row in active] == ["still-live"]
