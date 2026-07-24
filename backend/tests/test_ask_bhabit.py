from __future__ import annotations

import json

from flask import Flask

from backend import ask_bhabit


def market_provider(asset):
    if asset["symbol"] == "UNSUPPORTED":
        return None
    return {
        "current_price": {
            "status": "available",
            "value": 10.0,
            "source": "fixture_price",
            "retrieved_at": "2026-07-24T00:00:00Z",
        },
        "short_window_movement": {
            "status": "available",
            "value": 2.5,
            "source": "fixture_1h",
            "retrieved_at": "2026-07-24T00:00:00Z",
        },
        "longer_window_movement": {
            "status": "stale",
            "value": 4.0,
            "source": "fixture_24h",
            "retrieved_at": "2026-07-23T00:00:00Z",
            "freshness": "stale",
        },
        "volume": {
            "status": "available",
            "value": 1000.0,
            "source": "fixture_volume",
            "retrieved_at": "2026-07-24T00:00:00Z",
        },
        "liquidity": {
            "status": "conflicting",
            "value": None,
            "source": "fixture_liquidity",
            "retrieved_at": "2026-07-24T00:00:00Z",
            "conflicts": ["dex_a and dex_b disagree"],
        },
    }


def derivatives_provider(asset, price_change_pct):
    if asset["symbol"] == "SOL":
        return {
            "funding": {
                "status": "available",
                "value": 0.0001,
                "source": "hyperliquid",
                "retrieved_at": "2026-07-24T00:00:00Z",
            },
            "open_interest": {
                "status": "available",
                "value": 5000000.0,
                "source": "hyperliquid",
                "retrieved_at": "2026-07-24T00:00:00Z",
            },
            "liquidations": {
                "status": "unavailable",
                "value": None,
                "source": "hyperliquid",
                "retrieved_at": "2026-07-24T00:00:00Z",
                "reason": "liquidation feed absent",
            },
            "trader_positioning": {
                "status": "provider_error",
                "value": None,
                "source": "coinalyze",
                "retrieved_at": "2026-07-24T00:00:00Z",
                "error": "timeout",
            },
        }
    return {}


def sentiment_provider(asset):
    return {
        "status": "not_configured",
        "value": None,
        "source": "social_provider",
        "retrieved_at": "2026-07-24T00:00:00Z",
        "reason": "No paid social provider configured",
    }


def providers():
    return ask_bhabit.AskBhabitProviders(
        market=market_provider,
        sentiment=sentiment_provider,
        derivatives=derivatives_provider,
    )


def position(symbol="SOL"):
    return ask_bhabit.normalize_position(
        {
            "asset_id": symbol,
            "quantity": 2,
            "entry_price": 6,
            "note": "manual beta position",
        }
    )


def test_shdw_resolves_to_solana_shadow_token_not_shadow_exchange():
    asset = ask_bhabit.resolve_asset("SHDW")
    assert asset["symbol"] == "SHDW"
    assert asset["chain"] == "solana"
    assert asset["name"] == "Shadow Token"
    assert asset["name"] != "Shadow Exchange"
    assert asset["contract_address"]


def test_missing_derivatives_and_missing_social_provider_are_explicit():
    packet = ask_bhabit.build_evidence_packet(position("BTC"), providers=providers())
    derivatives = packet["public_market_evidence"]["derivatives"]
    assert derivatives["funding"]["status"] == "unavailable"
    assert derivatives["open_interest"]["status"] == "unavailable"
    assert packet["public_market_evidence"]["sentiment"]["status"] == "not_configured"
    assert packet["public_market_evidence"]["sentiment"]["value"] is None


def test_unsupported_asset_marks_sections_unsupported():
    packet = ask_bhabit.build_evidence_packet(
        position("UNSUPPORTED"), providers=providers()
    )
    assert packet["public_market_evidence"]["asset_identity"]["status"] == "unsupported"
    assert packet["public_market_evidence"]["price"]["status"] == "unsupported"
    assert packet["confidence"]["level"] == "insufficient_evidence"


def test_stale_provider_error_conflicting_data_and_sources_preserved():
    packet = ask_bhabit.build_evidence_packet(position("SOL"), providers=providers())
    evidence = packet["public_market_evidence"]
    assert evidence["movement"]["longer_window"]["status"] == "stale"
    assert evidence["volume_liquidity"]["liquidity"]["status"] == "conflicting"
    assert evidence["derivatives"]["trader_positioning"]["status"] == "provider_error"
    assert evidence["price"]["source"] == "fixture_price"
    assert evidence["price"]["retrieved_at"] == "2026-07-24T00:00:00Z"


def test_no_missing_value_converted_to_zero():
    packet = ask_bhabit.build_evidence_packet(position("SOL"), providers=providers())
    evidence = packet["public_market_evidence"]
    assert evidence["derivatives"]["liquidations"]["value"] is None
    assert evidence["sentiment"]["value"] is None


def test_no_thesis_and_thesis_present():
    no_thesis = ask_bhabit.build_evidence_packet(position("SOL"), providers=providers())
    assert no_thesis["private_context"]["thesis"]["status"] == "unavailable"
    thesis = ask_bhabit.normalize_thesis(
        {"why_entered": "staking growth", "tags": ["infra"]}
    )
    with_thesis = ask_bhabit.build_evidence_packet(
        position("SOL"), thesis, providers=providers()
    )
    assert with_thesis["private_context"]["thesis"]["status"] == "available"
    assert (
        with_thesis["private_context"]["thesis"]["value"]["why_entered"]
        == "staking growth"
    )


def test_snapshot_persistence(tmp_path):
    store = ask_bhabit.SnapshotStore(tmp_path / "snapshots.json")
    saved_position = store.upsert_position(
        {"asset_id": "SOL", "quantity": 2, "entry_price": 6}
    )
    store.upsert_thesis({"why_entered": "network growth"})
    packet = ask_bhabit.build_evidence_packet(
        saved_position, store.load()["thesis"], providers=providers()
    )
    store.append_snapshot({"snapshot_id": "s1", "evidence_packet": packet})
    loaded = store.load()
    assert loaded["position"]["asset_symbol"] == "SOL"
    assert loaded["thesis"]["why_entered"] == "network growth"
    assert loaded["snapshots"][0]["evidence_packet"]["asset_symbol"] == "SOL"


def test_no_previous_snapshot_comparison():
    packet = ask_bhabit.build_evidence_packet(position("SOL"), providers=providers())
    comparison = ask_bhabit.compare_packets(None, packet)
    assert comparison["status"] == "no_previous_snapshot"
    assert "insufficient_evidence" in comparison["categories"]


def test_deterministic_comparison_detects_numeric_and_status_changes():
    first = ask_bhabit.build_evidence_packet(position("SOL"), providers=providers())
    second = json.loads(json.dumps(first))
    second["public_market_evidence"]["price"]["value"] = 12.0
    second["public_market_evidence"]["derivatives"]["funding"]["value"] = 0.0003
    second["public_market_evidence"]["sentiment"]["status"] = "available"
    second["public_market_evidence"]["sentiment"]["value"] = {"label": "bullish"}
    comparison = ask_bhabit.compare_packets(first, second)
    fields = {change["field"] for change in comparison["changes"]}
    assert {"price", "funding", "sentiment"} <= fields
    assert "market_structure_changed" in comparison["categories"]
    assert "evidence_quality_changed" in comparison["categories"]


def test_confidence_classification_levels():
    packet = ask_bhabit.build_evidence_packet(position("SOL"), providers=providers())
    assert packet["confidence"]["level"] == "low"
    assert packet["confidence"]["reasons"]


def test_llm_prompt_contains_only_supplied_evidence():
    packet = ask_bhabit.build_evidence_packet(position("SOL"), providers=providers())
    comparison = ask_bhabit.compare_packets(None, packet)
    prompt = ask_bhabit.build_analysis_prompt(packet, comparison)
    assert "evidence_packet" in prompt
    assert "prior_snapshot_comparison" in prompt
    assert "LunarCrush" not in prompt
    assert "web-search" not in prompt
    assert "coinbase secret" not in prompt.lower()


def test_api_position_thesis_analysis_latest_and_what_changed(tmp_path, monkeypatch):
    monkeypatch.setenv("ASK_BHABIT_STORE_PATH", str(tmp_path / "api_store.json"))
    monkeypatch.setattr(ask_bhabit, "PROVIDERS", providers())
    app = Flask(__name__)
    app.register_blueprint(ask_bhabit.ask_bhabit_bp)
    client = app.test_client()

    assert (
        client.post(
            "/api/ask-bhabit/position",
            json={"asset_id": "SOL", "quantity": 2, "entry_price": 6},
        ).status_code
        == 200
    )
    assert (
        client.put(
            "/api/ask-bhabit/thesis", json={"why_entered": "network growth"}
        ).status_code
        == 200
    )
    evidence = client.get("/api/ask-bhabit/evidence").get_json()["data"]
    assert evidence["asset_symbol"] == "SOL"

    created = client.post("/api/ask-bhabit/analyze", json={})
    assert created.status_code == 201
    latest = client.get("/api/ask-bhabit/analysis/latest").get_json()["data"]
    assert latest["analysis"]["status"] == "not_configured"
    snapshots = client.get("/api/ask-bhabit/snapshots").get_json()["data"]
    assert len(snapshots) == 1
    changed = client.get("/api/ask-bhabit/what-changed").get_json()["data"]
    assert changed["status"] == "no_previous_snapshot"
