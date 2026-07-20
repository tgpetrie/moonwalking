try:
    from board_outcomes import BoardOutcomeStore
except Exception:  # pragma: no cover
    from backend.board_outcomes import BoardOutcomeStore


def row(symbol="SOL", price=100.0, change=1.2):
    return {
        "symbol": symbol,
        "product_id": f"{symbol}-USD",
        "current_price": price,
        "change_1m": change,
        "change_3m": change,
    }


def test_records_one_entry_and_blocks_duplicate_reentry_during_episode_lockout(
    tmp_path,
):
    db_path = tmp_path / "board.sqlite"
    store = BoardOutcomeStore(db_path)
    boards = {
        "ignition_1m": [row()],
        "confirmation_3m_up": [],
        "confirmation_3m_down": [],
    }

    store.observe(boards, {"SOL-USD": 100.0}, now_ts=1_000)
    store.observe(boards, {"SOL-USD": 101.0}, now_ts=1_020)
    assert store.status()["total_entries"] == 1

    store.observe({**boards, "ignition_1m": []}, {"SOL-USD": 101.0}, now_ts=1_040)
    store.observe(boards, {"SOL-USD": 102.0}, now_ts=1_060)
    assert BoardOutcomeStore(db_path).status()["total_entries"] == 1

    store.observe({**boards, "ignition_1m": []}, {"SOL-USD": 102.0}, now_ts=1_080)
    store.observe(boards, {"SOL-USD": 103.0}, now_ts=4_681)
    assert BoardOutcomeStore(db_path).status()["total_entries"] == 2


def test_measures_cost_adjusted_directional_checkpoints_for_losers(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("MW_BOARD_ROUND_TRIP_COST_PCT", "0")
    store = BoardOutcomeStore(tmp_path / "board.sqlite")
    boards = {
        "ignition_1m": [],
        "confirmation_3m_up": [],
        "confirmation_3m_down": [row(price=100.0, change=-1.5)],
    }
    store.observe(boards, {"SOL-USD": 100.0}, now_ts=10_000)
    store.observe(boards, {"SOL-USD": 99.0}, now_ts=10_300)
    store.observe(boards, {"SOL-USD": 98.0}, now_ts=10_900)
    store.observe(boards, {"SOL-USD": 97.0}, now_ts=11_800)
    store.observe(boards, {"SOL-USD": 96.0}, now_ts=13_600)

    summary = store.status()["boards"]["confirmation_3m_down"]
    assert summary["sample_size"] == 1
    assert summary["counts"]["continuation"] == 1
    assert summary["median_directional_return"] == {
        "5m": 1.0,
        "15m": 2.0,
        "30m": 3.0,
        "60m": 4.0,
    }


def test_classifies_reversal_and_whipsaw_without_overclaiming(tmp_path, monkeypatch):
    monkeypatch.setenv("MW_BOARD_ROUND_TRIP_COST_PCT", "0")
    store = BoardOutcomeStore(tmp_path / "board.sqlite")
    up = {
        "ignition_1m": [row("SOL")],
        "confirmation_3m_up": [],
        "confirmation_3m_down": [],
    }
    store.observe(up, {"SOL-USD": 100.0}, now_ts=20_000)
    store.observe(up, {"SOL-USD": 100.7}, now_ts=20_300)
    store.observe(up, {"SOL-USD": 99.2}, now_ts=20_900)

    summary = store.status()["boards"]["ignition_1m"]
    assert summary["sample_size"] == 1
    assert summary["counts"]["volatile"] == 1
    assert summary["status"] == "learning"
    assert summary["continuation_ci95"] is not None


def test_tracks_only_the_published_top_eight_by_default(tmp_path):
    store = BoardOutcomeStore(tmp_path / "board.sqlite")
    rows = [row(f"C{index}", 100 + index, 1 + index / 10) for index in range(10)]
    store.observe(
        {
            "ignition_1m": rows,
            "confirmation_3m_up": [],
            "confirmation_3m_down": [],
        },
        {f"C{index}-USD": 100 + index for index in range(10)},
        now_ts=30_000,
    )
    assert store.status()["total_entries"] == 8


def test_matches_a_non_board_control_and_reports_cost_adjusted_excess(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("MW_BOARD_ROUND_TRIP_COST_PCT", "0.20")
    store = BoardOutcomeStore(tmp_path / "board.sqlite")
    boards = {
        "ignition_1m": [row("SOL", 100.0, 1.2)],
        "confirmation_3m_up": [],
        "confirmation_3m_down": [],
    }
    prices = {
        "SOL": {"price": 100.0, "pct_1m": 1.2},
        "BTC": {"price": 100.0, "pct_1m": 0.8},
        "ETH": {"price": 100.0, "pct_1m": 0.3},
    }
    store.observe(boards, prices, now_ts=50_000)
    prices["SOL"]["price"] = 101.0
    prices["BTC"]["price"] = 100.6
    store.observe(boards, prices, now_ts=50_900)

    summary = store.status()["boards"]["ignition_1m"]
    assert summary["sample_size"] == 1
    assert summary["matched_sample_size"] == 1
    assert summary["median_directional_return"]["15m"] == 0.8
    assert summary["control"]["continuation_rate"] == 0.0
    assert summary["median_excess_return_vs_control"]["15m"] == 0.4
    assert summary["status"] == "learning"


def test_v2_status_preserves_but_excludes_legacy_samples(tmp_path):
    import sqlite3

    db_path = tmp_path / "board.sqlite"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE board_outcomes (id INTEGER PRIMARY KEY)")
    conn.execute("INSERT INTO board_outcomes DEFAULT VALUES")
    conn.commit()
    conn.close()

    store = BoardOutcomeStore(db_path)
    result = store.status()
    assert result["model_version"] == "board-outcomes-v2"
    assert result["total_entries"] == 0
    assert result["legacy_entries_preserved"] == 1
