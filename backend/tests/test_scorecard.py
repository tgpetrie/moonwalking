import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from signal_outcomes import SignalOutcomeStore


def _make_store():
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    return SignalOutcomeStore(db_path=tmp.name), tmp.name


def _insert_outcomes(store, state, direction, label, wins, losses):
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
                    f"{state}-{direction}-{label}-{i}",
                    f"evt-{i}",
                    "BTC-USD",
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
