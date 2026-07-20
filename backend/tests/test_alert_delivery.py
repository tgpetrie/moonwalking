from __future__ import annotations

try:
    from alert_delivery import AlertDeliveryDispatcher, format_delivery
except Exception:  # pragma: no cover
    from backend.alert_delivery import AlertDeliveryDispatcher, format_delivery


def _event(event_id="event-1", state="Moonwalking", ts_ms=1_800_000_000_000):
    return {
        "id": event_id,
        "event_id": "sol-event",
        "symbol": "SOL-USD",
        "primary_state": state,
        "modifier": "Flow",
        "confidence": 91,
        "alert_count": 4,
        "event_ts_ms": ts_ms,
        "latest_transition_ts_ms": ts_ms,
        "message": "SOL Building -> Breakout -> Moonwalking",
        "evidence": {"event_path": "Building -> Breakout -> Moonwalking"},
    }


def test_delivery_message_explains_event_evolution():
    subject, body = format_delivery(_event())
    assert "SOL Moonwalking" in subject
    assert "Evolution: Building -> Breakout -> Moonwalking" in body
    assert "Confidence: 91" in body


def test_dispatch_dedupes_transition_and_allows_risk_flip(monkeypatch):
    monkeypatch.setenv("MW_ALERT_NOTIFY_ENABLED", "1")
    monkeypatch.setenv("MW_DISCORD_WEBHOOK_URL", "https://example.invalid/webhook")
    monkeypatch.setenv("MW_NOTIFY_SYMBOL_COOLDOWN_SECONDS", "900")
    dispatcher = AlertDeliveryDispatcher()
    sent = []
    dispatcher._send_discord = lambda event: sent.append(event["id"])
    now = 1_800_000_000.0

    assert dispatcher.dispatch([_event()], now=now) == 1
    assert dispatcher.dispatch([_event()], now=now + 5) == 0
    risk = _event("event-risk", "Reversal Risk", int((now + 10) * 1000))
    assert dispatcher.dispatch([risk], now=now + 10) == 1
    assert sent == ["event-1", "event-risk"]


def test_dispatch_respects_global_hourly_budget(monkeypatch):
    monkeypatch.setenv("MW_ALERT_NOTIFY_ENABLED", "1")
    monkeypatch.setenv("MW_DISCORD_WEBHOOK_URL", "https://example.invalid/webhook")
    monkeypatch.setenv("MW_NOTIFY_MAX_PER_HOUR", "1")
    monkeypatch.setenv("MW_NOTIFY_SYMBOL_COOLDOWN_SECONDS", "0")
    dispatcher = AlertDeliveryDispatcher()
    dispatcher._send_discord = lambda _event: None
    now = 1_800_000_000.0

    assert dispatcher.dispatch([_event()], now=now) == 1
    second = {**_event("event-2", ts_ms=int((now + 5) * 1000)), "symbol": "BTC-USD"}
    assert dispatcher.dispatch([second], now=now + 5) == 0
