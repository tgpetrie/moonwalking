from agents.data_quality import (
    analyze_board_snapshot,
    analyze_coin_pressure_payload,
    analyze_track_record,
)
from agents.tape_scout import TapeScoutAgent


def test_data_quality_flags_duplicate_and_missing_price():
    observations = analyze_board_snapshot(
        {
            "timestamp": 1_000,
            "gainers_1m": [
                {"product_id": "BTC-USD", "symbol": "BTC", "price_now": 100},
                {"product_id": "BTC-USD", "symbol": "BTC", "price_now": None},
            ],
        },
        now=1_050,
    )

    kinds = {item.kind for item in observations}
    assert "duplicate_product_ids" in kinds
    assert "missing_or_invalid_price" in kinds


def test_data_quality_flags_stale_snapshot():
    observations = analyze_board_snapshot({"timestamp": 1_000, "gainers_1m": []}, now=1_500)

    stale = [item for item in observations if item.kind == "stale_board_snapshot"]
    assert stale
    assert stale[0].evidence["age_seconds"] == 500


def test_coin_pressure_missing_price_is_observed():
    observations = analyze_coin_pressure_payload(
        {"symbol": "BTC", "message": "Not enough live tape yet."}
    )

    kinds = {item.kind for item in observations}
    assert "coin_pressure_missing_price" in kinds
    assert "coin_pressure_no_live_tape" in kinds


def test_track_record_zero_rows_stays_unmeasured():
    observations = analyze_track_record(
        [
            {"label": "coin-selection", "observed_periods": 0, "market_periods": 100},
            {"label": "timing", "observed_periods": 0, "market_periods": 100},
        ]
    )

    assert observations[0].kind == "track_record_unmeasured"
    assert observations[0].severity == "info"


def test_tape_scout_spots_fast_move_without_forecast_claim():
    agent = TapeScoutAgent(one_min_threshold=1.0, three_min_threshold=3.0)

    observations = agent.run(
        {
            "board_snapshot": {
                "gainers_1m": [
                    {"product_id": "ETH-USD", "symbol": "ETH", "pct_1m": 1.2, "pct_3m": 1.8}
                ]
            }
        }
    )

    assert len(observations) == 1
    assert observations[0].kind == "fast_price_move"
    assert "not a forecast" in observations[0].summary
