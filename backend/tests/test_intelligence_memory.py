from __future__ import annotations

try:
    from intelligence_memory import IntelligenceMemoryStore
except Exception:  # pragma: no cover
    from backend.intelligence_memory import IntelligenceMemoryStore


def _portfolio_snapshot(
    *,
    symbol: str = "SOL",
    quantity: float = 2.0,
    market_value: float = 20.0,
    cost_basis: float = 12.0,
    price: float = 10.0,
    cash_value: float = 5.0,
):
    return {
        "status": "live",
        "mode": "view_only",
        "updated_at": "2026-07-25T00:00:00Z",
        "summary": {
            "total_value_usd": market_value + cash_value,
            "cash_value_usd": cash_value,
            "crypto_value_usd": market_value,
            "holding_count": 1,
            "open_order_count": 0,
            "known_unrealized_pnl_usd": market_value - cost_basis,
            "cost_basis_coverage_pct": 100.0,
        },
        "holdings": [
            {
                "symbol": symbol,
                "quantity": quantity,
                "market_value_usd": market_value,
                "price_usd": price,
                "allocation_pct": 80.0,
                "is_cash": False,
                "cost_basis": {
                    "status": "complete",
                    "known_cost_usd": cost_basis,
                },
            },
            {
                "symbol": "USD",
                "quantity": cash_value,
                "market_value_usd": cash_value,
                "price_usd": 1.0,
                "allocation_pct": 20.0,
                "is_cash": True,
                "cost_basis": {
                    "status": "not_applicable",
                    "known_cost_usd": cash_value,
                },
            },
        ],
    }


def test_portfolio_snapshot_memory_tracks_previous_state(tmp_path, monkeypatch):
    monkeypatch.setenv("MW_INTELLIGENCE_MEMORY_DB", str(tmp_path / "memory.sqlite"))
    store = IntelligenceMemoryStore()

    first = store.record_portfolio_snapshot(7, _portfolio_snapshot())
    second = store.record_portfolio_snapshot(
        7,
        _portfolio_snapshot(
            quantity=3.0,
            market_value=30.0,
            cost_basis=15.0,
            price=10.0,
            cash_value=4.0,
        ),
    )

    latest = store.latest_portfolio_snapshot(7)

    assert first["previous_snapshot_id"] is None
    assert second["previous_snapshot_id"] == first["snapshot_id"]
    assert second["change"]["status"] == "compared"
    assert "summary_changed" in second["change"]["categories"]
    assert any(
        change["field"] == "quantity"
        for change in second["change"]["holdings_changed"][0]["changes"]
    )
    assert latest["snapshot_id"] == second["snapshot_id"]
    assert any(holding["asset_symbol"] == "SOL" for holding in latest["holdings"])


def test_evidence_packet_history_links_to_previous_packet(tmp_path, monkeypatch):
    monkeypatch.setenv("MW_INTELLIGENCE_MEMORY_DB", str(tmp_path / "memory.sqlite"))
    store = IntelligenceMemoryStore()

    first = store.record_evidence_packet(
        {
            "packet_id": "evidence-1",
            "schema_version": "ask_bhabit.evidence.v1",
            "retrieved_at": "2026-07-25T00:00:00Z",
            "asset_id": "solana:So11111111111111111111111111111111111111112",
            "asset_symbol": "SOL",
            "public_market_evidence": {},
            "private_context": {},
            "confidence": {"level": "low"},
        },
        series_key="ask_bhabit:solana:So11111111111111111111111111111111111111112",
        origin="unit-test",
    )
    second = store.record_evidence_packet(
        {
            "packet_id": "evidence-2",
            "schema_version": "ask_bhabit.evidence.v1",
            "retrieved_at": "2026-07-26T00:00:00Z",
            "asset_id": "solana:So11111111111111111111111111111111111111112",
            "asset_symbol": "SOL",
            "public_market_evidence": {},
            "private_context": {},
            "confidence": {"level": "medium"},
        },
        series_key="ask_bhabit:solana:So11111111111111111111111111111111111111112",
        origin="unit-test",
    )

    latest = store.latest_evidence_packet(
        series_key="ask_bhabit:solana:So11111111111111111111111111111111111111112"
    )

    assert first["previous_packet_id"] is None
    assert second["previous_packet_id"] == "evidence-1"
    assert latest["packet_id"] == "evidence-2"
    assert latest["analysis"] == {}
