"""Password reset: token lifecycle, enumeration safety, and session invalidation."""

import os
import sys
from datetime import timedelta

import pytest
from flask import Flask

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import auth_rate_limit
import mailer
import password_reset
import watchlist


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(watchlist, "_WATCHLIST_DB_PATH", tmp_path / "wl.sqlite")
    watchlist._ensure_watchlist_schema()
    auth_rate_limit.limiter.reset()

    app = Flask(__name__)
    app.config["SECRET_KEY"] = "test-key"  # pragma: allowlist secret
    app.config["TESTING"] = True
    app.register_blueprint(watchlist.watchlist_bp)
    with app.test_client() as test_client:
        yield test_client


@pytest.fixture
def sent(monkeypatch):
    """Capture outgoing mail instead of touching SMTP."""
    outbox = []
    monkeypatch.setattr(
        mailer,
        "send_email",
        lambda **kwargs: outbox.append(kwargs),
    )
    return outbox


def _signup(client, email="a@example.com", password="original-pw"):
    response = client.post(
        "/api/auth/signup",
        json={"name": "Tester", "email": email, "password": password},
    )
    assert response.status_code == 201
    return response


def _token_from(outbox):
    """Pull the raw token out of the captured reset link."""
    assert outbox, "no reset email was sent"
    body = outbox[-1]["body"]
    marker = "token="
    start = body.index(marker) + len(marker)
    return body[start:].split()[0]


def _request_reset(client, email="a@example.com"):
    return client.post("/api/auth/forgot-password", json={"email": email})


# --- enumeration safety ----------------------------------------------------


def test_unknown_email_returns_same_response_as_known_email(client, sent):
    _signup(client)
    client.post("/api/auth/logout")

    known = _request_reset(client, "a@example.com")
    auth_rate_limit.limiter.reset()
    unknown = _request_reset(client, "nobody@example.com")

    assert known.status_code == unknown.status_code == 200
    assert known.get_json() == unknown.get_json()


def test_unknown_email_sends_no_mail(client, sent):
    _request_reset(client, "nobody@example.com")
    assert sent == []


# --- happy path ------------------------------------------------------------


def test_valid_token_sets_new_password(client, sent):
    _signup(client)
    client.post("/api/auth/logout")
    _request_reset(client)

    response = client.post(
        "/api/auth/reset-password",
        json={"token": _token_from(sent), "password": "brand-new-pw"},
    )
    assert response.status_code == 200

    assert (
        client.post(
            "/api/auth/login",
            json={"email": "a@example.com", "password": "brand-new-pw"},
        ).status_code
        == 200
    )
    assert (
        client.post(
            "/api/auth/login",
            json={"email": "a@example.com", "password": "original-pw"},
        ).status_code
        == 401
    )


def test_only_a_digest_of_the_token_is_stored(client, sent):
    _signup(client)
    _request_reset(client)
    raw = _token_from(sent)

    conn = watchlist._db_connect()
    try:
        rows = conn.execute("SELECT token_hash FROM password_reset_tokens").fetchall()
    finally:
        conn.close()

    assert len(rows) == 1
    assert rows[0]["token_hash"] != raw
    assert rows[0]["token_hash"] == password_reset.digest_token(raw)


# --- rejection cases -------------------------------------------------------


def test_invalid_token_is_rejected(client):
    _signup(client)
    response = client.post(
        "/api/auth/reset-password",
        json={"token": "not-a-real-token", "password": "brand-new-pw"},
    )
    assert response.status_code == 400


def test_expired_token_is_rejected(client, sent):
    _signup(client)
    _request_reset(client)
    raw = _token_from(sent)

    conn = watchlist._db_connect()
    try:
        past = password_reset._iso(
            password_reset._now() - timedelta(seconds=password_reset.TOKEN_TTL_SECONDS)
        )
        conn.execute("UPDATE password_reset_tokens SET expires_at = ?", (past,))
        conn.commit()
    finally:
        conn.close()

    response = client.post(
        "/api/auth/reset-password", json={"token": raw, "password": "brand-new-pw"}
    )
    assert response.status_code == 400
    assert (
        client.post(
            "/api/auth/login",
            json={"email": "a@example.com", "password": "original-pw"},
        ).status_code
        == 200
    ), "an expired token must leave the old password working"


def test_token_cannot_be_reused(client, sent):
    _signup(client)
    client.post("/api/auth/logout")
    _request_reset(client)
    raw = _token_from(sent)

    first = client.post(
        "/api/auth/reset-password", json={"token": raw, "password": "first-new-pw"}
    )
    assert first.status_code == 200

    second = client.post(
        "/api/auth/reset-password", json={"token": raw, "password": "second-new-pw"}
    )
    assert second.status_code == 400
    assert (
        client.post(
            "/api/auth/login",
            json={"email": "a@example.com", "password": "second-new-pw"},
        ).status_code
        == 401
    )


def test_requesting_a_second_token_invalidates_the_first(client, sent):
    _signup(client)
    _request_reset(client)
    first_token = _token_from(sent)
    _request_reset(client)
    second_token = _token_from(sent)
    assert first_token != second_token

    assert (
        client.post(
            "/api/auth/reset-password",
            json={"token": first_token, "password": "brand-new-pw"},
        ).status_code
        == 400
    )


def test_short_password_is_rejected(client, sent):
    _signup(client)
    _request_reset(client)
    response = client.post(
        "/api/auth/reset-password", json={"token": _token_from(sent), "password": "abc"}
    )
    assert response.status_code == 400


# --- token validation endpoint --------------------------------------------


def test_validate_endpoint_reports_live_and_dead_tokens(client, sent):
    _signup(client)
    _request_reset(client)
    raw = _token_from(sent)

    assert client.get(f"/api/auth/reset-password/validate?token={raw}").get_json() == {
        "valid": True
    }
    client.post("/api/auth/reset-password", json={"token": raw, "password": "new-pw-123"})
    assert client.get(f"/api/auth/reset-password/validate?token={raw}").get_json() == {
        "valid": False
    }


# --- session invalidation --------------------------------------------------


def test_reset_invalidates_sessions_issued_before_it(client, sent):
    """The signup session must stop authenticating once the password changes."""
    _signup(client)
    assert client.get("/api/auth/session").get_json()["authenticated"] is True

    _request_reset(client)
    raw = _token_from(sent)

    # A separate client stands in for "another device" holding a live cookie.
    other_cookie_session = client.get("/api/auth/session").get_json()
    assert other_cookie_session["authenticated"] is True

    client.post("/api/auth/reset-password", json={"token": raw, "password": "new-pw-123"})

    assert client.get("/api/auth/session").get_json()["authenticated"] is False


def test_session_version_increments_once_per_reset(client, sent):
    _signup(client)
    conn = watchlist._db_connect()
    try:
        before = conn.execute("SELECT session_version FROM users").fetchone()[0]
    finally:
        conn.close()

    _request_reset(client)
    client.post(
        "/api/auth/reset-password",
        json={"token": _token_from(sent), "password": "new-pw-123"},
    )

    conn = watchlist._db_connect()
    try:
        after = conn.execute("SELECT session_version FROM users").fetchone()[0]
    finally:
        conn.close()
    assert after == before + 1


def test_login_after_reset_produces_a_working_session(client, sent):
    _signup(client)
    _request_reset(client)
    client.post(
        "/api/auth/reset-password",
        json={"token": _token_from(sent), "password": "new-pw-123"},
    )
    client.post(
        "/api/auth/login", json={"email": "a@example.com", "password": "new-pw-123"}
    )
    assert client.get("/api/auth/session").get_json()["authenticated"] is True


# --- rate limiting ---------------------------------------------------------


def test_repeated_requests_for_one_email_stop_sending_but_stay_neutral(client, sent):
    _signup(client)
    limit = auth_rate_limit.RESET_REQUEST_PER_EMAIL[0]

    for _ in range(limit):
        assert _request_reset(client).status_code == 200
    assert len(sent) == limit

    throttled = _request_reset(client)
    assert throttled.status_code == 200, "throttling must not leak via status code"
    assert len(sent) == limit, "no further mail should go out"


def test_ip_budget_returns_429(client, sent):
    limit = auth_rate_limit.RESET_REQUEST_PER_IP[0]
    for index in range(limit):
        _request_reset(client, f"user{index}@example.com")
    assert _request_reset(client, "another@example.com").status_code == 429


def test_confirm_attempts_are_throttled(client):
    limit = auth_rate_limit.RESET_CONFIRM_PER_IP[0]
    for _ in range(limit):
        client.post(
            "/api/auth/reset-password", json={"token": "guess", "password": "x" * 8}
        )
    response = client.post(
        "/api/auth/reset-password", json={"token": "guess", "password": "x" * 8}
    )
    assert response.status_code == 429
