import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from signal_outcomes import SignalOutcomeStore


def _make_store():
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    return SignalOutcomeStore(db_path=tmp.name), tmp.name


def _insert_outcomes(
    store, state, direction, label, wins, losses, product_id="BTC-USD"
):
    conn = store._connect()
    try:
        for i in range(wins + losses):
            outcome = "followed_through" if i < wins else "did_not_follow_through"
            conn.execute(
                """
                INSERT INTO signal_outcomes (
                    signal_id, event_id, product_id, primary_state, read_label,
                    direction, confidence, started_ts, start_price, last_ts, last_price,
                    return_5m, return_15m, return_30m, return_60m,
                    max_favorable_pct, max_adverse_pct, outcome, complete
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
                """,
                (
                    f"{product_id}-{state}-{direction}-{label}-{i}",
                    f"evt-{i}",
                    product_id,
                    state,
                    label,
                    direction,
                    80,
                    1700000000 + i * 60,
                    50000.0,
                    1700000000 + i * 60 + 3600,
                    50500.0 if outcome == "followed_through" else 49500.0,
                    0.5 if outcome == "followed_through" else -0.3,
                    0.8 if outcome == "followed_through" else -0.5,
                    1.0 if outcome == "followed_through" else -0.8,
                    1.5 if outcome == "followed_through" else -1.0,
                    2.5 if outcome == "followed_through" else 0.3,
                    -0.5 if outcome == "followed_through" else -2.0,
                    outcome,
                ),
            )
        conn.commit()
    finally:
        conn.close()


def test_scorecard_basic():
    store, path = _make_store()
    try:
        _insert_outcomes(store, "Confirmed", "up", "STRONG_BUY", 30, 20)
        _insert_outcomes(store, "Confirmed", "down", "STRONG_SELL", 10, 10)

        result = store.scorecard()

        assert result["total_graded"] == 70
        assert result["overall_win_rate"] is not None
        assert len(result["signal_types"]) == 2

        buy_card = next(c for c in result["signal_types"] if c["label"] == "STRONG_BUY")
        assert buy_card["sample_size"] == 50
        assert buy_card["win_rate"] == 0.6
        assert buy_card["direction"] == "up"
        assert buy_card["median_return"]["5m"] is not None
    finally:
        os.unlink(path)


def test_scorecard_min_samples_filter():
    store, path = _make_store()
    try:
        _insert_outcomes(store, "Building", "up", "WATCH", 2, 1)

        result = store.scorecard(min_samples=5)
        assert result["total_graded"] == 3
        assert len(result["signal_types"]) == 0
    finally:
        os.unlink(path)


def test_scorecard_empty():
    store, path = _make_store()
    try:
        result = store.scorecard()
        assert result["total_graded"] == 0
        assert result["overall_win_rate"] is None
        assert result["signal_types"] == []
    finally:
        os.unlink(path)


# ---------------------------------------------------------------------------
# coin_scorecard — per-product filtering and shared aggregation path
# ---------------------------------------------------------------------------


def test_coin_scorecard_filters_by_product():
    store, path = _make_store()
    try:
        _insert_outcomes(store, "Confirmed", "up", "STRONG_BUY", 15, 10, "BTC-USD")
        _insert_outcomes(store, "Confirmed", "up", "STRONG_BUY", 5, 5, "ETH-USD")

        btc = store.coin_scorecard("BTC-USD")
        eth = store.coin_scorecard("ETH-USD")

        assert btc["product_id"] == "BTC-USD"
        assert btc["total_outcomes"] == 25
        assert len(btc["signal_types"]) == 1
        assert btc["signal_types"][0]["sample_size"] == 25

        assert eth["product_id"] == "ETH-USD"
        assert eth["total_outcomes"] == 10
        assert len(eth["signal_types"]) == 1
        assert eth["signal_types"][0]["sample_size"] == 10
    finally:
        os.unlink(path)


def test_coin_scorecard_uses_same_aggregation_as_global():
    store, path = _make_store()
    try:
        _insert_outcomes(store, "Confirmed", "up", "STRONG_BUY", 30, 20, "BTC-USD")

        global_card = store.scorecard()["signal_types"][0]
        coin_card = store.coin_scorecard("BTC-USD")["signal_types"][0]

        # Same math, same card shape
        assert global_card["win_rate"] == coin_card["win_rate"]
        assert global_card["sample_size"] == coin_card["sample_size"]
        assert global_card["median_favorable_pct"] == coin_card["median_favorable_pct"]
        assert global_card["median_return"] == coin_card["median_return"]
    finally:
        os.unlink(path)


def test_coin_scorecard_no_history():
    store, path = _make_store()
    try:
        result = store.coin_scorecard("UNKNOWN-USD")
        assert result["product_id"] == "UNKNOWN-USD"
        assert result["total_outcomes"] == 0
        assert result["signal_types"] == []
    finally:
        os.unlink(path)


def test_coin_scorecard_small_sample_excluded_by_min_samples():
    store, path = _make_store()
    try:
        # 4 outcomes < min_samples=5 default
        _insert_outcomes(store, "Building", "up", "WATCH", 2, 2, "BTC-USD")

        result = store.coin_scorecard("BTC-USD")
        assert result["total_outcomes"] == 4
        assert result["signal_types"] == []
    finally:
        os.unlink(path)


def test_coin_scorecard_excludes_other_coin_from_global_unaffected():
    store, path = _make_store()
    try:
        _insert_outcomes(store, "Confirmed", "up", "STRONG_BUY", 30, 20, "BTC-USD")
        _insert_outcomes(store, "Confirmed", "down", "STRONG_SELL", 10, 10, "ETH-USD")

        global_result = store.scorecard()
        assert global_result["total_graded"] == 70
        assert len(global_result["signal_types"]) == 2

        btc_result = store.coin_scorecard("BTC-USD")
        assert btc_result["total_outcomes"] == 50
        assert len(btc_result["signal_types"]) == 1
    finally:
        os.unlink(path)
