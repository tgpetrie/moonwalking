"""Tests for the shared portfolio credential service.

The critical invariant: refreshing must persist the ROTATED refresh token.
Coinbase invalidates the old one, so losing the replacement permanently breaks
the user's connection.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

from backend import portfolio_credentials as pc
from backend.portfolio_credentials import (
    CredentialStatus,
    list_snapshot_eligible_users,
    resolve_portfolio_service,
    resolve_user_credentials,
)


def _iso(dt):
    return dt.replace(microsecond=0).isoformat().replace("+00:00", "Z")


@pytest.fixture
def user_db(tmp_path, monkeypatch):
    """A stand-in users table wired into the credential service."""
    db_path = tmp_path / "users.sqlite"
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE users (
            id INTEGER PRIMARY KEY,
            email TEXT,
            coinbase_oauth_access_token TEXT,
            coinbase_oauth_refresh_token TEXT,
            coinbase_oauth_expires_at TEXT,
            updated_at TEXT
        )
        """
    )
    conn.commit()
    conn.close()

    import threading

    lock = threading.Lock()

    def _db_connect():
        c = sqlite3.connect(db_path, check_same_thread=False)
        c.row_factory = sqlite3.Row
        return c

    monkeypatch.setattr(
        pc, "_watchlist_db", lambda: (_db_connect, lock, lambda: "2026-07-26T00:00:00Z")
    )

    def add_user(user_id, *, email="a@b.c", access=None, refresh=None, expires=None):
        c = _db_connect()
        c.execute(
            "INSERT INTO users (id, email, coinbase_oauth_access_token, "
            "coinbase_oauth_refresh_token, coinbase_oauth_expires_at) VALUES (?,?,?,?,?)",
            (user_id, email, access, refresh, expires),
        )
        c.commit()
        c.close()

    def read_user(user_id):
        c = _db_connect()
        row = c.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        c.close()
        return dict(row) if row else None

    return {"add_user": add_user, "read_user": read_user, "connect": _db_connect}


class FakeOAuth:
    """Stands in for the coinbase_oauth module."""

    def __init__(self, *, configured=True, response=None, raises=None):
        self._configured = configured
        self._response = response or {}
        self._raises = raises
        self.refresh_calls = []

    class CoinbaseOAuthConfig:
        pass

    def _make_config(self):
        outer = self

        class Config:
            def is_configured(self):
                return outer._configured

        return Config()

    def __call__(self):
        return self

    def refresh_access_token(self, config, refresh_token):
        self.refresh_calls.append(refresh_token)
        if self._raises:
            raise self._raises
        return self._response

    def compute_expiry_timestamp(self, seconds):
        return _iso(datetime.now(timezone.utc) + timedelta(seconds=seconds))


def _install_oauth(monkeypatch, fake):
    fake.CoinbaseOAuthConfig = fake._make_config
    monkeypatch.setattr(pc, "_oauth_module", lambda: fake)
    return fake


# --- 1. Valid connected user -------------------------------------------------


def test_valid_token_is_used_without_refresh(user_db, monkeypatch):
    future = _iso(datetime.now(timezone.utc) + timedelta(hours=2))
    user_db["add_user"](1, access="live-token", refresh="r1", expires=future)
    fake = _install_oauth(monkeypatch, FakeOAuth())

    resolved = resolve_user_credentials(1)

    assert resolved.status == CredentialStatus.CONNECTED
    assert resolved.usable is True
    assert resolved.access_token == "live-token"
    assert fake.refresh_calls == []  # no needless refresh


# --- 2. Expired credential refresh path --------------------------------------


def test_expired_token_refreshes_and_persists_rotated_refresh_token(
    user_db, monkeypatch
):
    past = _iso(datetime.now(timezone.utc) - timedelta(hours=1))
    user_db["add_user"](2, access="old-access", refresh="old-refresh", expires=past)
    fake = _install_oauth(
        monkeypatch,
        FakeOAuth(
            response={
                "access_token": "new-access",
                "refresh_token": "ROTATED-refresh",
                "expires_in": 3600,
            }
        ),
    )

    resolved = resolve_user_credentials(2)

    assert resolved.status == CredentialStatus.REFRESHED
    assert resolved.usable is True
    assert fake.refresh_calls == ["old-refresh"]

    # The rotated refresh token MUST be persisted; the old one is now dead.
    stored = user_db["read_user"](2)
    assert stored["coinbase_oauth_access_token"] == "new-access"
    assert stored["coinbase_oauth_refresh_token"] == "ROTATED-refresh"
    assert stored["coinbase_oauth_expires_at"]


def test_missing_expiry_triggers_refresh_rather_than_gambling(user_db, monkeypatch):
    user_db["add_user"](3, access="a", refresh="r", expires=None)
    fake = _install_oauth(
        monkeypatch,
        FakeOAuth(
            response={"access_token": "new", "refresh_token": "r2", "expires_in": 60}
        ),
    )
    resolved = resolve_user_credentials(3)
    assert resolved.status == CredentialStatus.REFRESHED
    assert fake.refresh_calls == ["r"]


def test_refresh_response_without_rotation_keeps_old_refresh_token(
    user_db, monkeypatch
):
    past = _iso(datetime.now(timezone.utc) - timedelta(hours=1))
    user_db["add_user"](4, access="a", refresh="keep-me", expires=past)
    _install_oauth(
        monkeypatch,
        FakeOAuth(response={"access_token": "new", "expires_in": 3600}),
    )
    resolve_user_credentials(4)
    assert user_db["read_user"](4)["coinbase_oauth_refresh_token"] == "keep-me"


def test_refresh_failure_is_explicit(user_db, monkeypatch):
    past = _iso(datetime.now(timezone.utc) - timedelta(hours=1))
    user_db["add_user"](5, access="a", refresh="bad", expires=past)
    _install_oauth(monkeypatch, FakeOAuth(raises=RuntimeError("invalid_grant")))

    resolved = resolve_user_credentials(5)

    assert resolved.status == CredentialStatus.REFRESH_FAILED
    assert resolved.usable is False
    assert "invalid_grant" in resolved.detail


def test_expired_without_refresh_token_demands_reconnect(user_db, monkeypatch):
    past = _iso(datetime.now(timezone.utc) - timedelta(hours=1))
    user_db["add_user"](6, access="a", refresh="", expires=past)
    _install_oauth(monkeypatch, FakeOAuth())

    resolved = resolve_user_credentials(6)
    assert resolved.status == CredentialStatus.REFRESH_FAILED
    assert "reconnect" in resolved.detail


def test_oauth_not_configured_is_explicit(user_db, monkeypatch):
    past = _iso(datetime.now(timezone.utc) - timedelta(hours=1))
    user_db["add_user"](7, access="a", refresh="r", expires=past)
    _install_oauth(monkeypatch, FakeOAuth(configured=False))

    resolved = resolve_user_credentials(7)
    assert resolved.status == CredentialStatus.OAUTH_NOT_CONFIGURED
    assert resolved.usable is False


# --- 3. Unavailable / not connected ------------------------------------------


def test_unconnected_user_is_explicit(user_db, monkeypatch):
    user_db["add_user"](8, access=None)
    _install_oauth(monkeypatch, FakeOAuth())
    resolved = resolve_user_credentials(8)
    assert resolved.status == CredentialStatus.NOT_CONNECTED
    assert resolved.usable is False


def test_unreadable_store_is_explicit(monkeypatch):
    def boom():
        raise RuntimeError("db gone")

    monkeypatch.setattr(pc, "_watchlist_db", boom)
    resolved = resolve_user_credentials(9)
    assert resolved.status == CredentialStatus.STORE_UNAVAILABLE
    assert resolved.usable is False


def test_resolve_portfolio_service_returns_reason_when_unusable(user_db, monkeypatch):
    past = _iso(datetime.now(timezone.utc) - timedelta(hours=1))
    user_db["add_user"](10, access="a", refresh="bad", expires=past)
    _install_oauth(monkeypatch, FakeOAuth(raises=RuntimeError("nope")))
    monkeypatch.delenv("COINBASE_API_KEY_NAME", raising=False)

    service, resolved = resolve_portfolio_service(10)
    assert service is None
    assert resolved.status == CredentialStatus.REFRESH_FAILED


# --- 4. Eligibility partitioning ---------------------------------------------


def test_eligibility_partitions_users_by_auth_state(user_db, monkeypatch):
    future = _iso(datetime.now(timezone.utc) + timedelta(hours=2))
    past = _iso(datetime.now(timezone.utc) - timedelta(hours=1))
    monkeypatch.delenv("COINBASE_PORTFOLIO_OWNER_EMAIL", raising=False)
    monkeypatch.delenv("COINBASE_API_KEY_NAME", raising=False)
    monkeypatch.delenv("COINBASE_API_KEY_SECRET", raising=False)

    user_db["add_user"](20, email="ok@x.com", access="a", refresh="r", expires=future)
    user_db["add_user"](21, email="stale@x.com", access="a", refresh="r", expires=past)
    user_db["add_user"](22, email="dead@x.com", access="a", refresh="", expires=past)
    user_db["add_user"](23, email="none@x.com", access=None)

    eligible, ineligible = list_snapshot_eligible_users()
    eligible_ids = {e["user_id"] for e in eligible}
    reasons = {i["user_id"]: i["reason"] for i in ineligible}

    # Valid and refreshable users are eligible; refresh happens at capture time.
    assert eligible_ids == {20, 21}
    assert reasons[22] == CredentialStatus.REFRESH_FAILED
    assert reasons[23] == CredentialStatus.NOT_CONNECTED


def test_env_owner_is_eligible_without_oauth(user_db, monkeypatch):
    monkeypatch.setenv("COINBASE_PORTFOLIO_OWNER_EMAIL", "owner@x.com")
    monkeypatch.setenv("COINBASE_API_KEY_NAME", "key")
    monkeypatch.setenv("COINBASE_API_KEY_SECRET", "secret")
    user_db["add_user"](30, email="owner@x.com", access=None)

    eligible, _ = list_snapshot_eligible_users()
    assert eligible == [{"user_id": 30, "auth": "env_owner"}]
