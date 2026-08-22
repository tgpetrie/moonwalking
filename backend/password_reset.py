"""Password-reset token lifecycle.

Only a SHA-256 digest of each token is persisted, so a database disclosure
never yields a usable reset link. The raw token exists in memory just long
enough to be placed in the outgoing email, and is never logged.

SHA-256 (rather than a password KDF) is the right primitive here: the token
is 256 bits of `secrets` entropy, not a human-chosen password, so there is
no dictionary to slow down.
"""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

TOKEN_TTL_SECONDS = 30 * 60
_TOKEN_BYTES = 32

SCHEMA = """
CREATE TABLE IF NOT EXISTS password_reset_tokens (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    token_hash TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    used_at TEXT,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_password_reset_tokens_user_id
    ON password_reset_tokens(user_id);
"""


def ensure_schema(conn) -> None:
    conn.executescript(SCHEMA)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    return value.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _parse(value: str):
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def digest_token(raw_token: str) -> str:
    """One-way digest of a reset token, safe to store."""
    return hashlib.sha256(str(raw_token or "").encode("utf-8")).hexdigest()


def create_token(conn, user_id: int, *, now: datetime | None = None) -> str:
    """Issue a fresh single-use token, invalidating the user's older ones.

    Returns the raw token. The caller must place it in an email and drop it;
    it cannot be recovered from the database afterwards.
    """
    moment = now or _now()
    # Superseding outstanding tokens means a second "forgot password" click
    # cannot leave two usable links alive at once.
    conn.execute(
        "DELETE FROM password_reset_tokens WHERE user_id = ? AND used_at IS NULL",
        (user_id,),
    )
    raw_token = secrets.token_urlsafe(_TOKEN_BYTES)
    conn.execute(
        """
        INSERT INTO password_reset_tokens (user_id, token_hash, created_at, expires_at)
        VALUES (?, ?, ?, ?)
        """,
        (
            user_id,
            digest_token(raw_token),
            _iso(moment),
            _iso(moment + timedelta(seconds=TOKEN_TTL_SECONDS)),
        ),
    )
    return raw_token


def _lookup(conn, raw_token: str):
    if not raw_token:
        return None
    return conn.execute(
        """
        SELECT id, user_id, expires_at, used_at
        FROM password_reset_tokens
        WHERE token_hash = ?
        """,
        (digest_token(raw_token),),
    ).fetchone()


def token_is_valid(conn, raw_token: str, *, now: datetime | None = None) -> bool:
    """Check a token without consuming it (used to gate the reset screen)."""
    row = _lookup(conn, raw_token)
    if not row or row["used_at"]:
        return False
    expires = _parse(row["expires_at"])
    return bool(expires and (now or _now()) < expires)


def consume_token(conn, raw_token: str, *, now: datetime | None = None):
    """Validate and burn a token.

    Returns the owning ``user_id``, or None when the token is unknown,
    expired, or already used. Marking it used in the same transaction as the
    password write is the caller's responsibility.
    """
    moment = now or _now()
    row = _lookup(conn, raw_token)
    if not row or row["used_at"]:
        return None
    expires = _parse(row["expires_at"])
    if not expires or moment >= expires:
        return None
    conn.execute(
        "UPDATE password_reset_tokens SET used_at = ? WHERE id = ?",
        (_iso(moment), row["id"]),
    )
    return row["user_id"]


def purge_expired(conn, *, now: datetime | None = None) -> int:
    """Drop spent and expired rows so the table cannot grow without bound."""
    cursor = conn.execute(
        "DELETE FROM password_reset_tokens WHERE expires_at < ? OR used_at IS NOT NULL",
        (_iso(now or _now()),),
    )
    return int(cursor.rowcount or 0)
