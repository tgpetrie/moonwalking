"""Per-user portfolio holdings: user A must never receive user B's holdings."""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import watchlist
import portfolio_mode


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setattr(watchlist, "_WATCHLIST_DB_PATH", tmp_path / "wl.sqlite")
    watchlist._ensure_watchlist_schema()
    monkeypatch.delenv("COINBASE_PORTFOLIO_OWNER_EMAIL", raising=False)
    yield tmp_path


def _mk_user(email, username, *, oauth_token=None):
    conn = watchlist._db_connect()
    try:
        now = watchlist._utc_now_iso()
        cur = conn.execute(
            """INSERT INTO users (email, password_hash, display_name, username,
               plan, created_at, updated_at, coinbase_oauth_access_token)
               VALUES (?,?,?,?,?,?,?,?)""",
            (email, "x", "N", username, "Free Account", now, now, oauth_token),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def _add_cost_basis(user_id, symbol):
    conn = watchlist._db_connect()
    try:
        now = watchlist._utc_now_iso()
        conn.execute(
            """INSERT INTO manual_cost_basis (user_id, symbol, average_price, note,
               created_at, updated_at) VALUES (?,?,?,?,?,?)""",
            (user_id, symbol, 1.0, "", now, now),
        )
        conn.commit()
    finally:
        conn.close()


class _FakeService:
    """Stands in for a Coinbase-backed PortfolioService."""

    def __init__(self, symbols):
        self._symbols = set(symbols)

    def held_symbols(self, *, fetch=False):
        return set(self._symbols)


# ── the core guarantee ───────────────────────────────────────────────────────


def test_user_a_never_receives_user_b_holdings(db, monkeypatch):
    a = _mk_user("a@example.com", "alice", oauth_token="token-a")
    b = _mk_user("b@example.com", "bob", oauth_token="token-b")

    # Each linked account resolves to its own holdings.
    holdings_by_token = {"token-a": {"AAA"}, "token-b": {"BBB"}}
    seen_tokens = []

    def fake_client(user_id):
        conn = watchlist._db_connect()
        try:
            row = conn.execute(
                "SELECT coinbase_oauth_access_token FROM users WHERE id = ?", (user_id,)
            ).fetchone()
        finally:
            conn.close()
        token = row[0]
        seen_tokens.append(token)
        return token

    monkeypatch.setattr(portfolio_mode, "_oauth_client_for_user", fake_client)
    monkeypatch.setattr(
        portfolio_mode,
        "PortfolioService",
        lambda token: _FakeService(holdings_by_token[token]),
    )

    assert portfolio_mode.held_symbols_for_user(a) == {"AAA"}
    assert portfolio_mode.held_symbols_for_user(b) == {"BBB"}
    # Neither call leaked into the other.
    assert "BBB" not in portfolio_mode.held_symbols_for_user(a)
    assert "AAA" not in portfolio_mode.held_symbols_for_user(b)


def test_unlinked_non_owner_never_reaches_the_global_owner_service(db, monkeypatch):
    """The process-global env-key service must not answer for a random user."""
    user = _mk_user("nobody@example.com", "nobody")  # no OAuth token, not owner

    called = {"global": False}

    def boom(*_a, **_kw):
        called["global"] = True
        return {"OWNER_COIN"}

    monkeypatch.setattr(portfolio_mode, "owner_held_symbols", boom)

    assert portfolio_mode.held_symbols_for_user(user) == set()
    assert called["global"] is False


def test_manual_cost_basis_is_scoped_to_its_owner(db):
    a = _mk_user("a@example.com", "alice")
    b = _mk_user("b@example.com", "bob")
    _add_cost_basis(a, "ADA")
    _add_cost_basis(b, "SOL")

    assert portfolio_mode.held_symbols_for_user(a) == {"ADA"}
    assert portfolio_mode.held_symbols_for_user(b) == {"SOL"}


def test_no_user_id_yields_nothing(db):
    assert portfolio_mode.held_symbols_for_user(None) == set()
    assert portfolio_mode.held_symbols_for_user(0) == set()


# ── owner behaviour preserved ────────────────────────────────────────────────


def test_configured_owner_still_gets_env_key_holdings(db, monkeypatch):
    owner = _mk_user("owner@example.com", "owner")
    monkeypatch.setenv("COINBASE_PORTFOLIO_OWNER_EMAIL", "Owner@Example.com")
    monkeypatch.setattr(portfolio_mode, "owner_held_symbols", lambda **_kw: {"OWNED"})
    assert portfolio_mode.held_symbols_for_user(owner) == {"OWNED"}


def test_owner_env_path_does_not_apply_to_other_users(db, monkeypatch):
    _mk_user("owner@example.com", "owner")
    other = _mk_user("other@example.com", "other")
    monkeypatch.setenv("COINBASE_PORTFOLIO_OWNER_EMAIL", "owner@example.com")
    monkeypatch.setattr(portfolio_mode, "owner_held_symbols", lambda **_kw: {"OWNED"})
    assert portfolio_mode.held_symbols_for_user(other) == set()


def test_is_portfolio_owner_requires_configuration(db, monkeypatch):
    user = _mk_user("a@example.com", "alice")
    monkeypatch.delenv("COINBASE_PORTFOLIO_OWNER_EMAIL", raising=False)
    assert portfolio_mode._is_portfolio_owner(user) is False
    monkeypatch.setenv("COINBASE_PORTFOLIO_OWNER_EMAIL", "a@example.com")
    assert portfolio_mode._is_portfolio_owner(user) is True


# ── resilience ───────────────────────────────────────────────────────────────


def test_never_raises_when_the_portfolio_backend_fails(db, monkeypatch):
    user = _mk_user("a@example.com", "alice", oauth_token="tok")
    _add_cost_basis(user, "ADA")

    monkeypatch.setattr(portfolio_mode, "_oauth_client_for_user", lambda _u: "tok")

    def exploding(_client):
        raise RuntimeError("coinbase down")

    monkeypatch.setattr(portfolio_mode, "PortfolioService", exploding)

    # Degrades to the signals that still work rather than raising.
    assert portfolio_mode.held_symbols_for_user(user) == {"ADA"}


def test_oauth_client_returns_none_without_a_linked_account(db):
    user = _mk_user("a@example.com", "alice")
    assert portfolio_mode._oauth_client_for_user(user) is None
    assert portfolio_mode._oauth_client_for_user(None) is None


# ── back-compat ──────────────────────────────────────────────────────────────


def test_legacy_alias_still_points_at_the_owner_helper():
    assert portfolio_mode.get_held_symbols is portfolio_mode.owner_held_symbols


def test_notification_priority_symbols_is_user_scoped(db, monkeypatch):
    """The one consumer must not mix users when a user context exists."""
    import app

    a = _mk_user("a@example.com", "alice")
    b = _mk_user("b@example.com", "bob")
    _add_cost_basis(a, "ADA")
    _add_cost_basis(b, "SOL")

    # The global owner set and global watchlist must not bleed in.
    monkeypatch.setattr(portfolio_mode, "owner_held_symbols", lambda **_kw: {"OWNER"})
    app.watchlist_db.add("GLOBALCOIN")
    try:
        got_a = app._notification_priority_symbols(user_id=a)
        got_b = app._notification_priority_symbols(user_id=b)
    finally:
        app.watchlist_db.discard("GLOBALCOIN")

    assert got_a == {"ADA"}
    assert got_b == {"SOL"}
    for result in (got_a, got_b):
        assert "OWNER" not in result
        assert "GLOBALCOIN" not in result


def test_notification_priority_without_user_preserves_global_behaviour(db, monkeypatch):
    """Background loop has no session; existing behaviour is unchanged."""
    import app

    monkeypatch.setattr(portfolio_mode, "owner_held_symbols", lambda **_kw: {"OWNER"})
    app.watchlist_db.add("GLOBALCOIN")
    try:
        result = app._notification_priority_symbols()
    finally:
        app.watchlist_db.discard("GLOBALCOIN")

    assert "OWNER" in result
    assert "GLOBALCOIN" in result
