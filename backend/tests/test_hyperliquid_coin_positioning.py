from unittest.mock import Mock

import pytest

from backend import sentiment_api


def test_extract_all_hyperliquid_coin_positioning():
    meta = {
        "universe": [
            None,
            {"name": " sol "},
            {"name": "DOGE"},
            {"name": "BAD_MARK"},
            {"name": "BAD_FUNDING"},
            {"name": "BAD_OI"},
            {"name": "OVERFLOW"},
            {"name": "DELISTED", "isDelisted": True},
            {"name": "NO_CONTEXT"},
        ]
    }
    ctx = {"funding": "-0.000125", "openInterest": "5", "markPx": "20", "oraclePx": "21"}
    asset_ctxs = [
        ctx,
        ctx,
        {**ctx, "openInterest": "0", "oraclePx": "NaN"},
        {**ctx, "markPx": "0"},
        {**ctx, "funding": "NaN"},
        {**ctx, "openInterest": "Infinity"},
        {**ctx, "openInterest": "1e308"},
        ctx,
    ]

    assert sentiment_api._extract_all_hyperliquid_coin_positioning(meta, asset_ctxs) == {
        "SOL": {
            "funding_rate": -0.000125,
            "funding_8h_equiv": -0.001,
            "open_interest": 5.0,
            "open_interest_usd": 100.0,
            "mark_price": 20.0,
            "oracle_price": 21.0,
        },
        "DOGE": {
            "funding_rate": -0.000125,
            "funding_8h_equiv": -0.001,
            "open_interest": 0.0,
            "open_interest_usd": 0.0,
            "mark_price": 20.0,
            "oracle_price": None,
        },
    }


@pytest.mark.asyncio
async def test_derivatives_cache_exposes_coins_and_summarizes_benchmarks(monkeypatch):
    monkeypatch.setattr(sentiment_api, "BINANCE_DERIVATIVES_SYMBOLS", {})
    monkeypatch.setattr(sentiment_api, "OKX_DERIVATIVES_SYMBOLS", {})
    monkeypatch.setattr(sentiment_api, "BYBIT_DERIVATIVES_SYMBOLS", {})
    monkeypatch.setattr(sentiment_api, "COINALYZE_API_KEY", "")
    monkeypatch.setattr(sentiment_api, "_BINANCE_DERIVATIVES_CACHE", None)
    monkeypatch.setattr(sentiment_api, "_BINANCE_DERIVATIVES_CACHE_TS", None)

    ctx = {"funding": "0.00001", "openInterest": "5", "markPx": "20", "oraclePx": "21"}
    response = Mock()
    response.json.return_value = [
        {"universe": [{"name": "BTC"}, {"name": "SOL"}, {"name": "ETH"}]},
        [ctx, {**ctx, "funding": "-0.001"}, {**ctx, "funding": "0"}],
    ]
    post = Mock(return_value=response)
    monkeypatch.setattr(sentiment_api.requests, "post", post)

    payload = await sentiment_api._get_derivatives_positioning_payload()
    cached = await sentiment_api._get_derivatives_positioning_payload()

    post.assert_called_once_with(
        f"{sentiment_api.HYPERLIQUID_BASE_URL}/info",
        json={"type": "metaAndAssetCtxs"},
        timeout=1.5,
    )
    assert payload is not None and cached is not None
    assert [row["symbol"] for row in payload["symbols"]] == ["BTC", "ETH"]
    assert payload["summary"]["average_funding_rate"] == pytest.approx(0.00004)
    assert set(payload["coin_positioning"]) == {"BTC", "ETH", "SOL"}
    assert payload["coin_positioning"]["SOL"]["funding_rate"] == -0.001
    assert cached["coin_positioning"] == payload["coin_positioning"]
