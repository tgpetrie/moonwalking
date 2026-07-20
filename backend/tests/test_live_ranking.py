from backend.live_ranking import LIVE_RANKING_MODEL_VERSION, build_live_rankings


def test_live_ranking_orders_confirmed_strength_and_excludes_stables():
    rows = build_live_rankings(
        price_snapshot={
            "AAA": {
                "price": 2,
                "pct_1m": 0.8,
                "pct_3m": 1.6,
                "pct_1h": 3.0,
                "trend_streak": 3,
            },
            "BBB": {"price": 3, "pct_1m": -0.4, "pct_3m": -1.1, "pct_1h": -2.0},
            "USDC": {"price": 1, "pct_1m": 0.01, "pct_3m": 0.02, "pct_1h": 0.0},
        },
        volume_snapshot={
            "AAA": {"volume_change_1h_pct": 120},
            "BBB": {"volume_change_1h_pct": -20},
        },
        alerts=[{"symbol": "AAA-USD", "type": "breakout"}],
    )

    assert [row["symbol"] for row in rows] == ["AAA", "BBB"]
    assert rows[0]["live_rank"] == 1
    assert rows[0]["live_score"] > rows[1]["live_score"]
    assert rows[0]["model_version"] == LIVE_RANKING_MODEL_VERSION
    assert rows[0]["universe_size"] == 2


def test_missing_inputs_remain_neutral_and_reduce_quality():
    complete, sparse = build_live_rankings(
        price_snapshot={
            "FULL": {
                "price": 2,
                "pct_1m": 0.2,
                "pct_3m": 0.4,
                "pct_1h": 0.8,
                "trend_streak": 2,
            },
            "SPARSE": {"price": 3, "pct_1m": 0.2, "pct_3m": None, "pct_1h": None},
        },
        volume_snapshot={"FULL": {"volume_change_1h_pct": 20}},
    )

    assert complete["symbol"] == "FULL"
    assert sparse["symbol"] == "SPARSE"
    assert complete["data_quality"] > sparse["data_quality"]
    assert complete["observed_inputs"] > sparse["observed_inputs"]
    assert complete["expected_inputs"] == sparse["expected_inputs"] == 6
    assert 1 <= sparse["live_score"] <= 99
