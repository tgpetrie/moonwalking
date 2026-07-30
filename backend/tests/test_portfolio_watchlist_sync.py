import os
import sys
import sqlite3

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

os.environ.setdefault("WATCHLIST_DB_PATH", ":memory:")

import watchlist


_SHARED_DB_PATH = None


def _fresh_db():
    """Reset watchlist module to use a shared file-based temp DB."""
    import tempfile
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    db_path = tmp.name

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            display_name TEXT NOT NULL DEFAULT '',
            email TEXT UNIQUE,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS watchlists (
            id TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            notes TEXT NOT NULL DEFAULT '',
            position INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS watchlist_items (
            id TEXT PRIMARY KEY,
            watchlist_id TEXT NOT NULL,
            item_key TEXT NOT NULL,
            item_type TEXT NOT NULL DEFAULT 'Asset',
            title TEXT NOT NULL DEFAULT '',
            notes TEXT NOT NULL DEFAULT '',
            added_price REAL,
            position INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(watchlist_id, item_key)
        );
        """
    )
    now = watchlist._utc_now_iso()
    conn.execute(
        "INSERT INTO users (id, username, display_name, email, password_hash, created_at, updated_at) VALUES (1, 'tom', 'Tom', 'tom@test.com', 'x', ?, ?)",
        (now, now),
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


def test_sync_adds_new_symbols():
    db_path, restore = _fresh_db()
    try:
        result = watchlist.sync_portfolio_to_watchlist(1, {"BTC", "ETH", "SOL"})
        assert sorted(result["added"]) == ["BTC", "ETH", "SOL"]
        assert result["already_present"] == []

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        items = conn.execute("SELECT item_key FROM watchlist_items ORDER BY item_key").fetchall()
        conn.close()
        assert [r["item_key"] for r in items] == ["BTC", "ETH", "SOL"]
    finally:
        watchlist._db_connect = restore
        os.unlink(db_path)


def test_sync_skips_existing():
    db_path, restore = _fresh_db()
    try:
        watchlist.sync_portfolio_to_watchlist(1, {"BTC", "ETH"})
        result = watchlist.sync_portfolio_to_watchlist(1, {"BTC", "ETH", "SOL"})
        assert result["added"] == ["SOL"]
        assert sorted(result["already_present"]) == ["BTC", "ETH"]
    finally:
        watchlist._db_connect = restore
        os.unlink(db_path)


def test_sync_empty_set():
    db_path, restore = _fresh_db()
    try:
        result = watchlist.sync_portfolio_to_watchlist(1, set())
        assert result["added"] == []
        assert result["already_present"] == []
    finally:
        watchlist._db_connect = restore
        os.unlink(db_path)
