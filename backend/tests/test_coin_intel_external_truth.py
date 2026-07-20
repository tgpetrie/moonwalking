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
