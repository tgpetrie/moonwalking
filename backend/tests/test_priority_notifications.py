import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from alert_events import notification_candidates
from portfolio_mode import PortfolioService, get_held_symbols


def _event(symbol, confidence, notify_eligible=False):
    return {
        "symbol": symbol,
        "confidence": confidence,
        "notify_eligible": notify_eligible,
        "delivery_tier": "notify" if notify_eligible else "signal",
    }


def test_standard_events_pass_through_unchanged():
    events = [_event("BTC-USD", 90, notify_eligible=True)]
    out = notification_candidates(events)
    assert len(out) == 1
    assert "priority" not in out[0]


def test_held_symbol_elevated_at_lower_confidence():
    events = [_event("SOL-USD", 70)]
    out = notification_candidates(events, priority_symbols={"SOL"})
    assert len(out) == 1
    assert out[0]["priority"] == "holding"
    assert out[0]["notify_eligible"] is True
    assert out[0]["delivery_tier"] == "notify"
    assert out[0]["notify_reason"] == "holding_priority"


def test_non_held_below_bar_still_excluded():
    events = [_event("DOGE-USD", 70)]
    assert notification_candidates(events, priority_symbols={"SOL"}) == []


def test_held_below_priority_bar_still_excluded():
    events = [_event("SOL-USD", 50)]
    assert notification_candidates(events, priority_symbols={"SOL"}) == []


def test_held_and_standard_keeps_standard_semantics():
    events = [_event("SOL-USD", 90, notify_eligible=True)]
    out = notification_candidates(events, priority_symbols={"SOL"})
    assert len(out) == 1
    assert out[0]["priority"] == "holding"
    assert "notify_reason" not in out[0]


def test_priority_symbols_accept_product_ids():
    events = [_event("SOL-USD", 70)]
    out = notification_candidates(events, priority_symbols={"sol-usd"})
    assert len(out) == 1


def test_get_held_symbols_empty_when_unconfigured(monkeypatch):
    for key in ("COINBASE_API_KEY_NAME", "COINBASE_API_KEY_SECRET"):
        monkeypatch.delenv(key, raising=False)
    assert get_held_symbols() == set()
    assert get_held_symbols(fetch=True) == set()


def test_service_held_symbols_reads_cache_without_network():
    class _NoNetworkClient:
        def __getattr__(self, name):
            raise AssertionError("network call attempted from cached read")

    service = PortfolioService(_NoNetworkClient())
    assert service.held_symbols() == set()

    service._cache = {
        "holdings": [
            {"currency": "BTC", "is_cash": False},
            {"currency": "SOL", "is_cash": False},
            {"currency": "USD", "is_cash": True},
        ]
    }
    assert service.held_symbols() == {"BTC", "SOL"}


def test_service_held_symbols_reads_the_symbol_field_real_snapshots_use():
    """Regression: snapshots build holdings with "symbol", not "currency".

    Reading only "currency" made this return an empty set against every real
    snapshot, silently dropping holdings-based alert priority.
    """
    service = PortfolioService(object())
    service._cache = {
        "holdings": [
            {"symbol": "ETH", "is_cash": False},
            {"symbol": "XRP", "is_cash": False},
            {"symbol": "USD", "is_cash": True},
        ]
    }
    assert service.held_symbols() == {"ETH", "XRP"}


def test_service_held_symbols_accepts_legacy_currency_rows_alongside_symbol():
    service = PortfolioService(object())
    service._cache = {
        "holdings": [
            {"symbol": "ETH", "is_cash": False},
            {"currency": "BTC", "is_cash": False},
            {"symbol": "USDC", "is_cash": True},
            {"currency": "USD", "is_cash": True},
            {"is_cash": False},
        ]
    }
    assert service.held_symbols() == {"ETH", "BTC"}
