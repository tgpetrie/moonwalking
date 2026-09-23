from backend import coin_intel_external as intel


def test_coinpaprika_events_filter_old_history(monkeypatch):
    monkeypatch.setattr(intel, "_now_s", lambda: 1_800_000_000)

    old_ts = 1_500_000_000
    future_ts = 1_900_000_000
    rows = [
        {
            "id": "old",
            "name": "Old conference",
            "date": old_ts,
            "link": "https://example.test/old",
        },
        {
            "id": "future",
            "name": "Future catalyst",
            "date": future_ts,
            "link": "https://example.test/future",
        },
    ]

    normalized = intel._normalize_events(rows)

    assert [row["id"] for row in normalized] == ["future"]
    assert normalized[0]["status"] == "upcoming"
    assert normalized[0]["source"] == "coinpaprika"


def test_provider_rows_distinguish_quiet_from_offline(monkeypatch):
    monkeypatch.delenv("LUNARCRUSH_API_KEY", raising=False)
    monkeypatch.delenv("LUNARCRUSH_KEY", raising=False)
    monkeypatch.delenv("COINGLASS_API_KEY", raising=False)
    monkeypatch.delenv("ARKHAM_API_KEY", raising=False)
    monkeypatch.delenv("COINMARKETCAL_API_KEY", raising=False)

    rows = intel._provider_rows(
        coin_id="btc-bitcoin",
        gecko_id="bitcoin",
        events={"status": "live", "items": []},
        social={"status": "live", "items": []},
        social_metrics={"status": "live"},
    )

    by_name = {row["name"]: row for row in rows}
    assert by_name["CoinPaprika events"]["status"] == "quiet"
    assert by_name["CoinPaprika official timeline"]["status"] == "quiet"
    assert by_name["CoinGecko community + trending"]["status"] == "live"
    assert by_name["LunarCrush"]["status"] == "not_configured"
    assert by_name["CoinGlass"]["status"] == "not_configured"
    assert by_name["Arkham"]["status"] == "not_configured"
    assert by_name["CoinMarketCal"]["status"] == "not_configured"


def test_licensed_provider_rows_show_credentials_without_claiming_live_data(
    monkeypatch,
):
    monkeypatch.setenv("COINGLASS_API_KEY", "configured")
    monkeypatch.setenv("ARKHAM_API_KEY", "configured")
    monkeypatch.setenv("COINMARKETCAL_API_KEY", "configured")

    rows = intel._provider_rows(coin_id=None, gecko_id=None)
    by_name = {row["name"]: row for row in rows}

    for name in ("CoinGlass", "Arkham", "CoinMarketCal"):
        assert by_name[name]["configured"] is True
        assert by_name[name]["status"] == "configured"
        assert by_name[name]["status"] != "live"


def test_fetch_coin_icon_url_resolves_and_caches(monkeypatch):
    intel._ENDPOINT_CACHE.clear()
    monkeypatch.setattr(intel, "coingecko_coin_id", lambda symbol: "bitcoin")
    calls = []

    def fake_http_get_json(url):
        calls.append(url)
        return 200, {"image": {"large": "https://example.test/btc.png"}}, None

    monkeypatch.setattr(intel, "_http_get_json", fake_http_get_json)

    first = intel.fetch_coin_icon_url("BTC")
    assert first == "https://example.test/btc.png"
    assert len(calls) == 1

    # Second call is served from cache; no further network call.
    second = intel.fetch_coin_icon_url("btc-usd")
    assert second == "https://example.test/btc.png"
    assert len(calls) == 1


def test_fetch_coin_icon_url_negative_caches_unresolvable_symbols(monkeypatch):
    intel._ENDPOINT_CACHE.clear()
    monkeypatch.setattr(intel, "coingecko_coin_id", lambda symbol: None)
    calls = []
    monkeypatch.setattr(
        intel, "_http_get_json", lambda url: calls.append(url) or (200, {}, None)
    )

    result = intel.fetch_coin_icon_url("ZZZNOTREAL")
    assert result is None
    assert calls == []  # coingecko_coin_id returned None, no detail call made

    cached, url = intel.peek_coin_icon_url("ZZZNOTREAL")
    assert cached is True
    assert url is None


def test_peek_coin_icon_url_reports_uncached_symbols_honestly():
    intel._ENDPOINT_CACHE.clear()
    cached, url = intel.peek_coin_icon_url("NEVERLOOKEDUP")
    assert cached is False
    assert url is None
