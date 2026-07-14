import asyncio

from backend import sentiment_api


def test_sentiment_payload_stays_unavailable_without_real_sources(monkeypatch):
    async def no_source():
        return None

    monkeypatch.setattr(sentiment_api, "USE_REAL_SENTIMENT", False)
    monkeypatch.setattr(sentiment_api, "_get_fear_greed_payload", no_source)
    monkeypatch.setattr(sentiment_api, "_get_market_pulse_payload", no_source)

    payload = asyncio.run(sentiment_api._build_sentiment_payload())
    data = payload.model_dump(mode="json")

    assert data["data_status"] == "offline"
    assert data["scope"] == "market_wide"
    assert data["overall_sentiment"] is None
    assert data["fear_greed_index"] is None
    assert data["social_metrics"] == {}
    assert all(value is None for value in data["social_breakdown"].values())
    assert data["sentiment_history"] == []
    assert data["social_history"] == []
    assert data["trending_topics"] == []
    assert data["divergence_alerts"] == []
    assert data["sources"] == []


def test_sentiment_payload_reports_real_source_provenance(monkeypatch):
    async def fear_greed():
        return {
            "value": 28,
            "label": "Fear",
            "source": "alternative_me",
            "source_url": sentiment_api.FNG_URL,
            "updated_at": "2026-07-13T00:00:00Z",
            "stale": False,
            "stale_age_seconds": 10,
        }

    async def market_pulse():
        return {
            "total_market_cap_usd": 1_000_000.0,
            "total_volume_usd": 10_000.0,
            "btc_dominance": 50.0,
            "mcap_change_24h_pct": -1.0,
            "source": "coingecko_global",
            "source_url": sentiment_api.CG_GLOBAL_URL,
            "updated_at": "2026-07-13T00:00:00Z",
            "stale": False,
            "stale_age_seconds": 10,
        }

    monkeypatch.setattr(sentiment_api, "USE_REAL_SENTIMENT", False)
    monkeypatch.setattr(sentiment_api, "_get_fear_greed_payload", fear_greed)
    monkeypatch.setattr(sentiment_api, "_get_market_pulse_payload", market_pulse)

    payload = asyncio.run(sentiment_api._build_sentiment_payload())
    data = payload.model_dump(mode="json")

    assert data["data_status"] == "live"
    assert data["overall_sentiment"] == 0.28
    assert data["fear_greed_index"] == 28
    assert data["source_breakdown"] == {
        "tier1": 2,
        "tier2": 0,
        "tier3": 0,
        "fringe": 0,
    }
    assert [source["name"] for source in data["sources"]] == [
        "alternative_me",
        "coingecko_global",
    ]
    assert all(source["tier"] == "tier1" for source in data["sources"])


def test_source_catalog_exposes_only_contributing_real_providers(monkeypatch):
    payload = sentiment_api.SentimentResponse(
        data_status="live",
        sources=[
            {
                "name": "alternative_me",
                "status": "live",
                "tier": "tier1",
                "scope": "market_wide",
            }
        ],
    )

    async def cached_payload():
        return payload

    monkeypatch.setattr(sentiment_api, "_hydrate_sentiment_cache", cached_payload)

    sources = asyncio.run(sentiment_api.get_data_sources())
    stats = asyncio.run(sentiment_api.get_statistics())

    assert [source["name"] for source in sources] == ["alternative_me"]
    assert stats["total_sources"] == 1
    assert stats["sources_by_tier"] == {
        "tier1": 1,
        "tier2": 0,
        "tier3": 0,
        "fringe": 0,
    }
    assert stats["average_trust_weight"] is None
