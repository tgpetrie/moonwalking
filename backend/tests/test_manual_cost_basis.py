import os
import sqlite3
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

os.environ.setdefault("WATCHLIST_DB_PATH", ":memory:")

from portfolio_mode import apply_manual_cost_basis

import watchlist


# --- Pure overlay logic (no DB) ---------------------------------------------


def _snapshot():
    """Three holdings: a partial-fill coin, a no-fill coin, and a complete one."""
    return {
        "summary": {
            "crypto_value_usd": 1700.0,
            "known_unrealized_pnl_usd": 50.0,
            "cost_basis_coverage_pct": 58.8,
        },
        "holdings": [
            {
                "symbol": "ADA",
                "is_cash": False,
                "quantity": 1000.0,
                "market_value_usd": 500.0,
                "unrealized_pnl_usd": None,
                "unrealized_pnl_pct": None,
                "cost_basis": {
                    "status": "partial",
                    "average_price": 0.30,
                    "known_quantity": 400.0,
                    "unknown_quantity": 600.0,
                    "known_cost_usd": 120.0,
                },
            },
            {
                "symbol": "DOGE",
                "is_cash": False,
                "quantity": 1000.0,
                "market_value_usd": 200.0,
                "unrealized_pnl_usd": None,
                "unrealized_pnl_pct": None,
                "cost_basis": {
                    "status": "unavailable",
                    "average_price": None,
                    "known_quantity": 0.0,
                    "unknown_quantity": 1000.0,
                    "known_cost_usd": None,
                },
            },
            {
                "symbol": "BTC",
                "is_cash": False,
                "quantity": 0.01,
                "market_value_usd": 1000.0,
                "unrealized_pnl_usd": 50.0,
                "unrealized_pnl_pct": 5.26,
                "cost_basis": {
                    "status": "complete",
                    "average_price": 95000.0,
                    "known_quantity": 0.01,
                    "unknown_quantity": 0.0,
                    "known_cost_usd": 950.0,
                },
            },
        ],
    }


def test_partial_holding_blends_known_and_manual():
    snap = _snapshot()
    apply_manual_cost_basis(snap, {"ADA": {"average_price": 0.40}})
    ada = snap["holdings"][0]
    # 120 known + (600 * 0.40) manual = 360 total over 1000 units.
    assert ada["cost_basis"]["status"] == "blended"
    assert ada["cost_basis"]["known_cost_usd"] == 360.0
    assert round(ada["cost_basis"]["average_price"], 4) == 0.36
    assert ada["cost_basis"]["unknown_quantity"] == 0.0
    assert ada["cost_basis"]["manual_average_price"] == 0.40
    # P&L unlocks: 500 market - 360 cost = 140.
    assert ada["unrealized_pnl_usd"] == 140.0
    assert round(ada["unrealized_pnl_pct"], 2) == 38.89


def test_unavailable_holding_uses_manual_wholesale():
    snap = _snapshot()
    apply_manual_cost_basis(snap, {"DOGE": {"average_price": 0.10}})
    doge = snap["holdings"][1]
    assert doge["cost_basis"]["status"] == "manual"
    assert doge["cost_basis"]["known_cost_usd"] == 100.0
    assert doge["unrealized_pnl_usd"] == 100.0
    assert doge["unrealized_pnl_pct"] == 100.0


def test_complete_holding_is_never_overwritten():
    snap = _snapshot()
    # A manual entry for a fully-verified coin must be ignored.
    apply_manual_cost_basis(snap, {"BTC": {"average_price": 1.0}})
    btc = snap["holdings"][2]
    assert btc["cost_basis"]["status"] == "complete"
    assert btc["cost_basis"]["average_price"] == 95000.0
    assert btc["unrealized_pnl_usd"] == 50.0


def test_summary_recomputes_pnl_and_coverage():
    snap = _snapshot()
    apply_manual_cost_basis(
        snap,
        {"ADA": {"average_price": 0.40}, "DOGE": {"average_price": 0.10}},
    )
    summary = snap["summary"]
    # 140 (ADA) + 100 (DOGE) + 50 (BTC) = 290 known P&L.
    assert summary["known_unrealized_pnl_usd"] == 290.0
    # All 1700 of crypto value now has a cost basis -> 100% coverage.
    assert summary["cost_basis_coverage_pct"] == 100.0


def test_invalid_and_empty_inputs_are_noops():
    snap = _snapshot()
    before = snap["holdings"][0]["cost_basis"]["status"]
    apply_manual_cost_basis(snap, None)
    apply_manual_cost_basis(snap, {})
    apply_manual_cost_basis(snap, {"ADA": {"average_price": 0}})
    apply_manual_cost_basis(snap, {"ADA": {"average_price": -5}})
    assert snap["holdings"][0]["cost_basis"]["status"] == before


def test_symbol_matching_is_case_insensitive():
    snap = _snapshot()
    apply_manual_cost_basis(snap, {"ada": {"average_price": 0.40}})
    assert snap["holdings"][0]["cost_basis"]["status"] == "blended"


# --- Storage round-trip (temp DB) -------------------------------------------


def _fresh_db():
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    db_path = tmp.name
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE manual_cost_basis (
            user_id INTEGER NOT NULL,
            symbol TEXT NOT NULL,
            average_price REAL NOT NULL,
            note TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY(user_id, symbol)
        );
        """
    )
    conn.commit()
    conn.close()

    original = watchlist._db_connect

    def _make_conn():
        c = sqlite3.connect(db_path)
        c.row_factory = sqlite3.Row
        return c

    watchlist._db_connect = _make_conn
    return db_path, original


def test_set_get_delete_round_trip():
    db_path, restore = _fresh_db()
    try:
        rec = watchlist.set_manual_cost_basis(1, "ada", 0.42, "bought on kraken")
        assert rec["symbol"] == "ADA"
        assert rec["average_price"] == 0.42

        stored = watchlist.get_manual_cost_basis(1)
        assert stored["ADA"]["average_price"] == 0.42
        assert stored["ADA"]["note"] == "bought on kraken"

        # Upsert overwrites in place.
        watchlist.set_manual_cost_basis(1, "ADA", 0.50)
        assert watchlist.get_manual_cost_basis(1)["ADA"]["average_price"] == 0.50

        assert watchlist.delete_manual_cost_basis(1, "ADA") is True
        assert watchlist.get_manual_cost_basis(1) == {}
        assert watchlist.delete_manual_cost_basis(1, "ADA") is False
    finally:
        watchlist._db_connect = restore
        os.unlink(db_path)


def test_set_rejects_invalid_price():
    db_path, restore = _fresh_db()
    try:
        assert watchlist.set_manual_cost_basis(1, "ADA", 0) is None
        assert watchlist.set_manual_cost_basis(1, "ADA", -1) is None
        assert watchlist.set_manual_cost_basis(1, "", 0.5) is None
        assert watchlist.get_manual_cost_basis(1) == {}
    finally:
        watchlist._db_connect = restore
        os.unlink(db_path)
