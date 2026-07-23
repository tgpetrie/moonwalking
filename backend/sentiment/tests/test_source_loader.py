import json

import pytest

from backend.sentiment.source_loader import (
    SentimentSourceLoaderError,
    load_sources,
)


def _write_catalog(tmp_path, tier, sources, schema_version=1):
    payload = {"schema_version": schema_version, "tier": tier, "sources": sources}
    path = tmp_path / f"{tier}.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_loads_valid_catalog_and_summarizes(tmp_path):
    _write_catalog(
        tmp_path,
        "Tier1",
        [
            {
                "name": "Fear & Greed Index",
                "description": "Macro gauge",
                "tier": "Tier1",
                "weight": 0.9,
                "endpoint": "https://example.com/fng",
            }
        ],
    )
    _write_catalog(
        tmp_path,
        "fringe",
        [
            {
                "name": "4chan /biz/",
                "description": "Fringe chatter",
                "weight": 0.3,
                "endpoint": "https://boards.4channel.org/biz/catalog",
            }
        ],
    )

    catalog = load_sources(tmp_path, force_reload=True)
    summary = catalog.summary()
    assert summary["tiers"]["tier1"] == 1
    assert summary["tiers"]["fringe"] == 1
    assert summary["total"] == 2


def test_rejects_unknown_tier_keys(tmp_path):
    _write_catalog(
        tmp_path,
        "unknown",
        [
            {
                "name": "Bad Tier",
                "description": "Should fail",
                "weight": 0.5,
            }
        ],
    )

    with pytest.raises(SentimentSourceLoaderError):
        load_sources(tmp_path, force_reload=True)


def test_rejects_missing_required_fields(tmp_path):
    _write_catalog(
        tmp_path,
        "tier2",
        [
            {
                "name": "",
                "description": "Missing name",
                "weight": 0.5,
            }
        ],
    )

    with pytest.raises(SentimentSourceLoaderError):
        load_sources(tmp_path, force_reload=True)


def test_rejects_duplicate_titles_and_urls(tmp_path):
    sources = [
        {
            "name": "CoinDesk",
            "description": "News feed",
            "weight": 0.8,
            "endpoint": "https://coindesk.com/rss",
        },
        {
            "name": "CoinDesk",
            "description": "Duplicate title",
            "weight": 0.7,
            "endpoint": "https://coindesk.com/rss",
        },
    ]
    _write_catalog(tmp_path, "tier2", sources)

    with pytest.raises(SentimentSourceLoaderError):
        load_sources(tmp_path, force_reload=True)


def test_rejects_unknown_schema_version(tmp_path):
    _write_catalog(
        tmp_path,
        "tier1",
        [
            {
                "name": "Legacy",
                "description": "Should fail schema",
                "weight": 0.4,
            }
        ],
        schema_version=99,
    )

    with pytest.raises(SentimentSourceLoaderError):
        load_sources(tmp_path, force_reload=True)


def test_current_catalog_marks_live_planned_and_retired_sources():
    catalog = load_sources(force_reload=True)
    entries = catalog.serialized()

    by_name = {entry["name"]: entry for entry in entries}

    assert by_name["Fear & Greed Index"]["implemented"] is True
    assert by_name["CoinGecko Global Market Data"]["implemented"] is True
    assert by_name["Binance USD-M Futures Positioning"]["implemented"] is True
    assert by_name["OKX Swap Positioning"]["implemented"] is True
    assert by_name["Bybit V5 Derivatives Positioning"]["implemented"] is True
    assert by_name["CoinGlass Derivatives Aggregates"]["signal_role"] == "paid_upgrade"
    assert by_name["SentiCrypt Legacy API"]["scope"] == "retired_legacy"
