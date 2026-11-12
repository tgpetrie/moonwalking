from datetime import datetime, timedelta, timezone
from decimal import Decimal
import json
import sys

import pytest

import backend.paper_exit_adapter as adapter
from backend.paper_exit_adapter import (
    UnverifiedCostBasisError,
    collect_quotes,
    fetch_fee_tier_bps,
    poll_top_of_book,
    verify_slice_cost_basis,
)
from backend.portfolio_mode import (
    CoinbaseAdvancedTradeClient,
    UnsafeCoinbasePermissions,
)
from scripts.coinbase_paper_exit import simulate_exit


def _fill(entry, *, size, price, commission="0", side="BUY", day=1):
    return {
        "entry_id": entry,
        "trade_time": f"2025-01-{day:02d}T00:00:00Z",
        "product_id": "BTC-USD",
        "size_in_quote": False,
        "size": size,
        "price": price,
        "commission": commission,
        "side": side,
    }


def coinbase_client(
    monkeypatch, *, can_trade=False, balance="0.010", broken_cursor=False
):
    client = CoinbaseAdvancedTradeClient()
    buy = _fill("buy", size="0.012", price="40000", commission="6")
    sell = _fill("sell", size="0.002", price="45000", side="SELL", day=2)
    calls = []

    def get(path, *, params=None):
        calls.append(path)
        if path.endswith("/key_permissions"):
            return {"can_view": True, "can_trade": can_trade, "can_transfer": False}
        if path.endswith("/accounts"):
            return {
                "accounts": [
                    {
                        "currency": "BTC",
                        "available_balance": {"value": balance},
                        "hold": {"value": "0"},
                    }
                ]
            }
        if path.endswith("/fills"):
            assert params["asset_filters"] == ["BTC"]
            if "cursor" not in params:
                return {"fills": [sell], "cursor": "next"}
            return {"fills": [buy, sell], "cursor": "next" if broken_cursor else ""}
        if path.endswith("/transaction_summary"):
            assert params == {"product_type": "SPOT"}
            return {"fee_tier": {"taker_fee_rate": "0.006"}}
        assert path.endswith("/product_book")
        assert params == {"product_id": "BTC-USD", "limit": 1}
        return {
            "pricebook": {
                "product_id": "BTC-USD",
                "time": "1970-01-01T00:00:01.011Z",
                "bids": [{"price": "45000", "size": "0.25"}],
            }
        }

    monkeypatch.setattr(client, "get", get)
    return client, calls


def test_pilot_follows_short_fill_pages_and_allocates_decimal_cost(monkeypatch):
    client, calls = coinbase_client(monkeypatch)
    basis = verify_slice_cost_basis(client, "BTC-USD", "0.005")
    assert basis["entry_cost_usd"] == Decimal("202.50")
    assert basis["source_fill_ids"] == ["buy", "sell"]
    assert basis["cost_basis_verified"] is True
    assert calls.count("/api/v3/brokerage/orders/historical/fills") == 2
    assert fetch_fee_tier_bps(client) == Decimal("60")
    assert poll_top_of_book(client, "BTC-USD", now_ms=lambda: 1120) == {
        "observed_at_ms": 1120,
        "exchange_time_ms": 1011,
        "bid_usd": Decimal("45000"),
        "bid_size": Decimal("0.25"),
    }


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"balance": "0.010001"}, "do not reconcile"),
        ({"broken_cursor": True}, "pagination is incomplete"),
        ({"balance": "0.004"}, "exceeds available balance"),
    ],
)
def test_pilot_rejects_unverified_inventory(monkeypatch, kwargs, message):
    client, _ = coinbase_client(monkeypatch, **kwargs)
    with pytest.raises(UnverifiedCostBasisError, match=message):
        verify_slice_cost_basis(client, "BTC-USD", "0.005")


def test_pilot_checks_permissions_before_reading_account(monkeypatch):
    client, calls = coinbase_client(monkeypatch, can_trade=True)
    with pytest.raises(UnsafeCoinbasePermissions, match="View-only"):
        verify_slice_cost_basis(client, "BTC-USD", "0.005")
    assert calls == ["/api/v3/brokerage/key_permissions"]


def test_unavailable_book_and_overrun_do_not_create_synthetic_receipts(monkeypatch):
    client, calls = coinbase_client(monkeypatch)
    now = 1000

    def book_request(path, *, params):
        nonlocal now
        calls.append(path)
        now += 2200
        return {"pricebook": {"product_id": "ETH-USD"}}

    def sleep(seconds):
        nonlocal now
        now += round(seconds * 1000)

    monkeypatch.setattr(client, "get", book_request)
    quotes = collect_quotes(
        client,
        {"window_start_ms": 1000, "window_end_ms": 5000, "product_id": "BTC-USD"},
        now_ms=lambda: now,
        sleep=sleep,
    )
    assert quotes == [
        {"observed_at_ms": 3200, "quote_status": "UNAVAILABLE"},
    ]
    assert len(calls) == 2


def test_collector_cli_writes_a_replayable_window(monkeypatch, tmp_path):
    client, _ = coinbase_client(monkeypatch)
    start = datetime.now(timezone.utc).replace(microsecond=0) + timedelta(seconds=10)
    now = int(start.timestamp()) * 1000 - 1000
    original_get = client.get
    original_collect = adapter.collect_quotes

    def sleep(seconds):
        nonlocal now
        now += round(seconds * 1000)

    def get(path, *, params=None):
        response = original_get(path, params=params)
        if path.endswith("/product_book"):
            response["pricebook"]["time"] = datetime.fromtimestamp(
                now / 1000, timezone.utc
            ).isoformat()
        return response

    monkeypatch.setattr(client, "get", get)
    monkeypatch.setattr(CoinbaseAdvancedTradeClient, "from_environment", lambda: client)
    monkeypatch.setattr(adapter, "_now_ms", lambda: now)
    monkeypatch.setattr(
        adapter,
        "collect_quotes",
        lambda client, spec: original_collect(
            client, spec, now_ms=lambda: now, sleep=sleep
        ),
    )
    output = tmp_path / "window.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "paper_exit_adapter",
            "--product",
            "BTC-USD",
            "--quantity",
            "0.005",
            "--start-utc",
            start.isoformat(),
            "--duration-seconds",
            "3",
            "--slippage-bps",
            "10",
            "--out",
            str(output),
        ],
    )
    adapter.main()
    result = simulate_exit(json.loads(output.read_text(encoding="utf-8")))
    assert result["data_quality"]["window_valid"]
    assert result["data_quality"]["valid_poll_slots"] == 3
    assert result["pilot_settings"]["matches_official"] is True
    assert result["pilot_settings"]["window_matches_official"] is False
    assert result["official_pilot_result"] is False
    assert result["hold_last_quote"]["bid_size"] == Decimal("0.25")
    assert result["entry_cost_usd"] == Decimal("202.50")
