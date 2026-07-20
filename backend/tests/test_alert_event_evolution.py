from __future__ import annotations

from datetime import datetime, timezone

try:
    from alert_events import (
        build_event_evolution,
        derive_event_read,
        enrich_event,
        notification_candidates,
    )
except Exception:  # pragma: no cover
    from backend.alert_events import (
        build_event_evolution,
        derive_event_read,
        enrich_event,
        notification_candidates,
    )


NOW = 1_800_000_000_000


def _alert(offset_s: int, typ: str, *, severity: str = "medium", direction: str = "up"):
    ts_ms = NOW + (offset_s * 1000)
    return {
        "id": f"{typ}-{offset_s}",
        "symbol": "SOL-USD",
        "type": typ,
        "type_key": typ,
        "severity": severity,
        "direction": direction,
        "event_ts_ms": ts_ms,
        "expires_at": datetime.fromtimestamp(
            (ts_ms + 900_000) / 1000, tz=timezone.utc
        ).isoformat(),
        "evidence": {"pct_1m": 1.2},
    }


def test_event_evolves_instead_of_publishing_disconnected_alerts():
    alerts = [
        _alert(0, "coin_volatility_expansion"),
        _alert(60, "breakout", severity="high"),
        _alert(120, "whale_move", severity="high"),
        _alert(180, "moonshot", severity="critical"),
        _alert(240, "coin_reversal_down", severity="high", direction="down"),
    ]

    events = build_event_evolution(alerts, now_ms=NOW + 250_000)

    assert len(events) == 1
    event = events[0]
    assert event["primary_state"] == "Reversal Risk"
    assert event["modifier"] == "Flow"
    assert [step["to"] for step in event["evolution"]] == [
        "Building",
        "Breakout",
        "Moonwalking",
        "Reversal Risk",
    ]
    assert event["alert_count"] == 5
    assert event["confidence"] >= 80


def test_repeated_same_state_increases_evidence_without_duplicate_transition():
    events = build_event_evolution(
        [_alert(0, "breakout"), _alert(30, "coin_persistent_gainer")],
        now_ms=NOW + 60_000,
    )

    assert len(events) == 1
    event = events[0]
    assert event["primary_state"] == "Breakout"
    assert [step["to"] for step in event["evolution"]] == ["Breakout"]
    assert event["alert_count"] == 2


def test_large_gap_starts_a_new_event_and_only_latest_is_active():
    events = build_event_evolution(
        [_alert(0, "breakout"), _alert(700, "coin_volatility_expansion")],
        now_ms=NOW + 720_000,
        gap_seconds=600,
    )

    assert len(events) == 1
    assert events[0]["primary_state"] == "Building"
    assert events[0]["alert_count"] == 1


def test_notification_slice_only_contains_eligible_events():
    events = build_event_evolution(
        [
            _alert(0, "coin_volatility_expansion", severity="low"),
            _alert(30, "breakout", severity="high"),
            _alert(60, "whale_move", severity="high"),
            _alert(90, "moonshot", severity="critical"),
        ],
        now_ms=NOW + 100_000,
    )

    candidates = notification_candidates(events)
    assert len(candidates) == 1
    assert candidates[0]["delivery_tier"] == "notify"


def test_the_read_favors_confirmed_continuation_without_calling_buy_or_sell():
    read = derive_event_read(
        state="Breakout",
        confidence=84,
        direction="up",
        families=["price", "flow"],
        modifiers=["Flow"],
        evidence={"pct_1m": 0.9},
    )

    assert read["label"] == "CONTINUATION FAVORED"
    assert read["tone"] == "favorable"
    assert read["is_directional_advice"] is False
    assert "buy" not in str(read).lower()
    assert "sell" not in str(read).lower()
    assert read["history"]["status"] == "collecting"


def test_the_read_uses_explicit_invalidation_and_measured_history_when_supplied():
    read = derive_event_read(
        state="Moonwalking",
        confidence=92,
        direction="up",
        families=["price", "flow", "social"],
        modifiers=["Flow", "Social"],
        evidence={
            "invalidation_price": 0.081,
            "historical_result": {
                "sample_size": 83,
                "follow_through_rate": 0.64,
            },
        },
    )

    assert read["condition"] == "while price holds above $0.081"
    assert read["history"]["label"] == "64% of 83 comparable events followed through"


def test_the_read_surfaces_conflicting_evidence_instead_of_overstating_confidence():
    read = derive_event_read(
        state="Breakout",
        confidence=90,
        direction="up",
        families=["price", "flow"],
        modifiers=["Flow"],
        conflicting_directions=True,
    )

    assert read["label"] == "MIXED — NO CLEAR EDGE"
    assert read["tone"] == "neutral"


def test_the_read_keeps_near_flat_flow_direction_neutral():
    read = derive_event_read(
        state="Building",
        confidence=62,
        direction="down",
        families=["flow"],
        modifiers=["Flow"],
        evidence={"pct_3m": 0.0},
    )

    assert read["label"] == "QUIET FLOW BUILDING"
    assert "downside" not in read["summary"].lower()


def test_the_read_prefers_meaningful_current_price_move_over_stale_direction():
    read = derive_event_read(
        state="Reversal Risk",
        confidence=96,
        direction="up",
        families=["price", "flow", "structure"],
        modifiers=["Flow"],
        evidence={"pct_3m": -2.02},
    )

    assert read["label"] == "BREAKDOWN CONFIRMED"


def test_event_payload_contains_the_read():
    events = build_event_evolution(
        [
            _alert(0, "breakout", severity="high"),
            _alert(30, "whale_move", severity="high"),
        ],
        now_ms=NOW + 40_000,
    )

    assert events[0]["the_read"]["label"] == "CONTINUATION FAVORED"
    assert events[0]["the_read"]["history"]["status"] == "collecting"


def test_market_carried_context_prevents_overstated_continuation_read():
    event = build_event_evolution(
        [
            _alert(0, "breakout", severity="high"),
            _alert(30, "whale_move", severity="high"),
        ],
        now_ms=NOW + 40_000,
    )[0]

    enriched = enrich_event(
        event,
        context={
            "market_relation": "market_carried",
            "badges": [{"label": "MARKET CARRIED", "tone": "context"}],
        },
    )

    assert enriched["the_read"]["label"] == "MARKET-LED MOVE"
    assert enriched["context_badges"][0]["label"] == "MARKET CARRIED"


def test_spot_tape_can_supply_independent_confirmation():
    read = derive_event_read(
        state="Breakout",
        confidence=80,
        direction="up",
        families=["price"],
        modifiers=[],
        evidence={"pct_1m": 0.8},
        context={"spot_pressure": "buying"},
    )

    assert read["label"] == "CONTINUATION FAVORED"
    assert "Coinbase spot buying" in read["confirmations"]


def test_thin_liquidity_is_a_risk_note_not_a_new_directional_alert():
    read = derive_event_read(
        state="Building",
        confidence=55,
        direction="up",
        families=["flow"],
        modifiers=["Flow"],
        evidence={"pct_1m": 0.1},
        context={"liquidity": "thin"},
    )

    assert "Thin liquidity" in read["risk_note"]
