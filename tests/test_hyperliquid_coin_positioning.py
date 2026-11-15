"""Offline checks for the all-coin Hyperliquid positioning helper. No network."""

import asyncio

import pytest

from backend import sentiment_api

extract = sentiment_api._extract_all_hyperliquid_coin_positioning

META = {
    "universe": [
        {"name": "BTC"},
        {"name": "ETH"},
        {"name": "kPEPE"},
        {"name": "sol"},
        {"name": "DEAD", "isDelisted": True},
        {"name": "ZERO"},
        {"name": ""},
        "not-a-dict",
        {"name": "NOPX"},
        {"name": "BTC"},
    ]
}
CTXS = [
    {
        "markPx": "100000.0",
        "oraclePx": "99990.0",
        "funding": "0.0000125",
        "openInterest": "25000.5",
    },
    {"markPx": "4000", "oraclePx": "4001", "funding": "-0.00002", "openInterest": "10"},
    {
        "markPx": "0.012",
        "oraclePx": "0.0121",
        "funding": "0.0001",
        "openInterest": "5e9",
    },
    {"markPx": "150.5"},
    {"markPx": "1.0", "funding": "0.5", "openInterest": "1"},
    {"markPx": "0", "funding": "0.1", "openInterest": "1"},
    {"markPx": "3.0"},
    {"markPx": "3.0"},
    {"oraclePx": "2.0", "funding": "0.1", "openInterest": "1"},
    {"markPx": "1.0", "funding": "9", "openInterest": "9"},
]


def test_extracts_every_valid_asset_by_hand():
    out = extract(META, CTXS)
    assert list(out) == ["BTC", "ETH", "KPEPE", "SOL"]
    assert out["BTC"] == {
        "exchange": "hyperliquid",
        "symbol": "BTC",
        "underlying_symbol": "BTC",
        "price_multiplier": 1,
        "mark_price": 100000.0,
        "index_price": 99990.0,
        "funding_rate": 0.0000125,
        "funding_interval_hours": 1.0,
        "funding_rate_8h_equiv": pytest.approx(0.0001),
        "open_interest": 25000.5,
        "open_interest_usd": pytest.approx(2_500_050_000.0),
    }
    eth = out["ETH"]
    assert eth["funding_rate_8h_equiv"] == pytest.approx(-0.00016)
    assert eth["open_interest_usd"] == pytest.approx(40_000.0)


def test_thousand_contracts_keep_their_own_key_and_record_the_underlying():
    pepe = extract(META, CTXS)["KPEPE"]
    assert (pepe["symbol"], pepe["underlying_symbol"]) == ("kPEPE", "PEPE")
    assert pepe["price_multiplier"] == 1000
    assert pepe["open_interest_usd"] == pytest.approx(5e9 * 0.012)


def test_missing_values_stay_none_and_are_never_zero():
    sol = extract(META, CTXS)["SOL"]
    assert sol["symbol"] == "sol" and sol["mark_price"] == 150.5
    for key in (
        "index_price",
        "funding_rate",
        "funding_rate_8h_equiv",
        "open_interest",
        "open_interest_usd",
    ):
        assert sol[key] is None


def test_delisted_unpriced_unnamed_and_duplicate_assets_are_left_out():
    out = extract(META, CTXS)
    for name in ("DEAD", "ZERO", "", "NOPX"):
        assert name not in out
    assert out["BTC"]["funding_rate"] == 0.0000125  # the first BTC entry wins


@pytest.mark.parametrize(
    ("meta", "ctxs"),
    [
        (None, CTXS),
        ({}, CTXS),
        ({"universe": "BTC"}, CTXS),
        (META, None),
        (META, {"BTC": {}}),
    ],
)
def test_malformed_responses_yield_nothing(meta, ctxs):
    assert extract(meta, ctxs) == {}


def test_contexts_shorter_than_the_universe_are_not_misaligned():
    assert list(extract(META, CTXS[:2])) == ["BTC", "ETH"]
    bad = [{"markPx": "nan"}, {"markPx": "inf"}, {"markPx": "-5"}, {"markPx": "x"}]
    assert extract(META, bad) == {}


class Response:
    def raise_for_status(self):
        return None

    def json(self):
        # The existing BTC/ETH lookup expects dict entries, as the API returns.
        kept = [
            i for i, asset in enumerate(META["universe"]) if isinstance(asset, dict)
        ]
        universe = [META["universe"][i] for i in kept]
        return [{"universe": universe}, [CTXS[i] for i in kept]]


def offline_venues(monkeypatch, post):
    async def nothing(*args):
        return None, None

    async def no_rows():
        return []

    monkeypatch.setattr(sentiment_api.requests, "post", post)
    for name in ("binance", "okx", "bybit"):
        monkeypatch.setattr(sentiment_api, f"_get_{name}_symbol_positioning", nothing)
    monkeypatch.setattr(sentiment_api, "_get_coinalyze_positioning", no_rows)
    monkeypatch.setattr(sentiment_api, "_BINANCE_DERIVATIVES_CACHE", None)
    monkeypatch.setattr(sentiment_api, "_BINANCE_DERIVATIVES_CACHE_TS", None)
    monkeypatch.setattr(sentiment_api, "_HYPERLIQUID_COIN_POSITIONING", {})


def test_payload_exposes_all_coins_and_keeps_symbols_and_summary_to_btc_eth(
    monkeypatch,
):
    calls = []

    def post(url, json, timeout):
        calls.append((url, json))
        return Response()

    offline_venues(monkeypatch, post)
    payload = asyncio.run(sentiment_api._get_derivatives_positioning_payload())
    assert calls == [
        (f"{sentiment_api.HYPERLIQUID_BASE_URL}/info", {"type": "metaAndAssetCtxs"})
    ]
    assert list(payload["coin_positioning"]) == ["BTC", "ETH", "KPEPE", "SOL"]
    assert [row["base_asset"] for row in payload["symbols"]] == ["BTC", "ETH"]
    assert all(row["exchange"] == "hyperliquid" for row in payload["symbols"])
    expected = sentiment_api._summarize_derivatives_positioning(
        payload["symbols"], len(payload["configured_exchanges"])
    )
    assert payload["summary"] == expected

    cached = asyncio.run(sentiment_api._get_derivatives_positioning_payload())
    assert len(calls) == 1  # served from the payload cache, one keyless call
    assert cached["coin_positioning"] == payload["coin_positioning"]


def test_a_failed_fetch_clears_the_snapshot(monkeypatch):
    def post(url, json, timeout):
        raise RuntimeError("offline")

    offline_venues(monkeypatch, post)
    monkeypatch.setattr(
        sentiment_api, "_HYPERLIQUID_COIN_POSITIONING", extract(META, CTXS)
    )
    rows = asyncio.run(sentiment_api._get_hyperliquid_positioning())
    assert rows[0][0] is None and rows[0][1]["exchange"] == "hyperliquid"
    assert sentiment_api._HYPERLIQUID_COIN_POSITIONING == {}
