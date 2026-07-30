"""Shared portfolio credential resolution.

One path to an authenticated Coinbase client, used by both the interactive
``/api/portfolio`` route and the background intelligence runner. Before this
module the interactive route refreshed OAuth tokens inline and the runner had
no refresh path at all — so a token that expired overnight meant the runner
silently reported "portfolio unavailable" forever.

CRITICAL — refresh token rotation:

Coinbase issues a *new* refresh token on every refresh and invalidates the old
one. Any code that refreshes without persisting the returned refresh token
destroys the user's connection permanently: the old token is now dead and the
replacement was never saved. ``coinbase_oauth.get_valid_access_token()`` returns
only the access token and is therefore unsafe for reuse — this module refreshes
and persists in one step instead, and is the only supported way to obtain a
client for a stored user.

Every outcome is explicit. Nothing here fails silently.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import logging
import os
from typing import Any

try:
    from portfolio_mode import CoinbaseAdvancedTradeClient, PortfolioService
except ImportError:  # package imports under pytest
    from backend.portfolio_mode import CoinbaseAdvancedTradeClient, PortfolioService


logger = logging.getLogger(__name__)

# Refresh this far ahead of expiry so a long snapshot never races the deadline.
REFRESH_LEEWAY_SECONDS = 300


class CredentialStatus:
    """Explicit outcomes. Callers branch on these rather than on None."""

    CONNECTED = "connected"  # stored token still valid
    REFRESHED = "refreshed"  # refreshed and persisted
    NOT_CONNECTED = "not_connected"  # user never connected Coinbase
    REFRESH_FAILED = "refresh_failed"  # refresh attempted and rejected
    OAUTH_NOT_CONFIGURED = "oauth_not_configured"  # server missing OAuth app
    ENV_OWNER = "env_owner"  # single-owner API-key fallback
    STORE_UNAVAILABLE = "store_unavailable"  # user DB unreadable


# Statuses that mean "we can capture a portfolio right now".
USABLE_STATUSES = frozenset(
    {CredentialStatus.CONNECTED, CredentialStatus.REFRESHED, CredentialStatus.ENV_OWNER}
)


@dataclass
class ResolvedCredentials:
    status: str
    user_id: int | None = None
    client: Any = None
    access_token: str | None = None
    detail: str | None = None

    @property
    def usable(self) -> bool:
        return self.status in USABLE_STATUSES and self.client is not None


def _watchlist_db():
    try:
        from watchlist import _DB_LOCK, _db_connect, _utc_now_iso
    except ImportError:
        from backend.watchlist import _DB_LOCK, _db_connect, _utc_now_iso
    return _db_connect, _DB_LOCK, _utc_now_iso


def _oauth_module():
    try:
        import coinbase_oauth
    except ImportError:
        from backend import coinbase_oauth
    return coinbase_oauth


def load_stored_tokens(user_id: int) -> dict[str, Any] | None:
    """Read a user's stored Coinbase OAuth tokens. None if unreadable."""
    try:
        _db_connect, _DB_LOCK, _ = _watchlist_db()
    except Exception:
        logger.debug("[PortfolioCredentials] user store unavailable", exc_info=True)
        return None
    try:
        conn = _db_connect()
        try:
            row = conn.execute(
                """
                SELECT coinbase_oauth_access_token,
                       coinbase_oauth_refresh_token,
                       coinbase_oauth_expires_at
                FROM users
                WHERE id = ?
                """,
                (int(user_id),),
            ).fetchone()
        finally:
            conn.close()
    except Exception:
        logger.debug("[PortfolioCredentials] token read failed", exc_info=True)
        return None
    if not row:
        return None
    return {
        "access_token": row["coinbase_oauth_access_token"],
        "refresh_token": row["coinbase_oauth_refresh_token"],
        "expires_at": row["coinbase_oauth_expires_at"],
    }


def persist_tokens(
    user_id: int, *, access_token: str, refresh_token: str | None, expires_at: str
) -> bool:
    """Persist a refreshed token set, including the ROTATED refresh token.

    Losing the rotated refresh token permanently breaks the user's connection,
    so this always writes all three fields together.
    """
    try:
        _db_connect, _DB_LOCK, _utc_now_iso = _watchlist_db()
    except Exception:
        return False
    try:
        with _DB_LOCK:
            conn = _db_connect()
            try:
                conn.execute(
                    """
                    UPDATE users
                    SET coinbase_oauth_access_token = ?,
                        coinbase_oauth_refresh_token = ?,
                        coinbase_oauth_expires_at = ?,
                        updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        access_token,
                        refresh_token or "",
                        expires_at,
                        _utc_now_iso(),
                        int(user_id),
                    ),
                )
                conn.commit()
            finally:
                conn.close()
        return True
    except Exception:
        logger.warning(
            "[PortfolioCredentials] failed to persist refreshed tokens for user %s",
            user_id,
            exc_info=True,
        )
        return False


def _token_needs_refresh(expires_at: str | None) -> bool:
    if not expires_at:
        return True  # unknown expiry — refresh rather than gamble on a 401
    try:
        expiry = datetime.fromisoformat(str(expires_at).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return True
    if expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) >= expiry - timedelta(
        seconds=REFRESH_LEEWAY_SECONDS
    )


def resolve_user_credentials(user_id: int) -> ResolvedCredentials:
    """Resolve one user's OAuth credentials into a ready client.

    Refreshes when needed and persists the rotated token set before returning.
    This is the single supported entry point for both request and background
    paths.
    """
    tokens = load_stored_tokens(user_id)
    if tokens is None:
        return ResolvedCredentials(
            status=CredentialStatus.STORE_UNAVAILABLE,
            user_id=user_id,
            detail="User store could not be read.",
        )

    access_token = str(tokens.get("access_token") or "").strip()
    refresh_token = str(tokens.get("refresh_token") or "").strip()
    if not access_token:
        return ResolvedCredentials(
            status=CredentialStatus.NOT_CONNECTED,
            user_id=user_id,
            detail="User has not connected Coinbase.",
        )

    if not _token_needs_refresh(tokens.get("expires_at")):
        return ResolvedCredentials(
            status=CredentialStatus.CONNECTED,
            user_id=user_id,
            client=CoinbaseAdvancedTradeClient(oauth_access_token=access_token),
            access_token=access_token,
        )

    # --- refresh required ---------------------------------------------------
    oauth = _oauth_module()
    config = oauth.CoinbaseOAuthConfig()
    if not config.is_configured():
        return ResolvedCredentials(
            status=CredentialStatus.OAUTH_NOT_CONFIGURED,
            user_id=user_id,
            detail="Coinbase OAuth app credentials are not configured on this server.",
        )
    if not refresh_token:
        return ResolvedCredentials(
            status=CredentialStatus.REFRESH_FAILED,
            user_id=user_id,
            detail="Access token expired and no refresh token is stored; user must reconnect.",
        )

    try:
        token_data = oauth.refresh_access_token(config, refresh_token)
    except Exception as exc:
        return ResolvedCredentials(
            status=CredentialStatus.REFRESH_FAILED,
            user_id=user_id,
            detail=f"Coinbase refused the token refresh: {exc}",
        )

    new_access = str(token_data.get("access_token") or "").strip()
    if not new_access:
        return ResolvedCredentials(
            status=CredentialStatus.REFRESH_FAILED,
            user_id=user_id,
            detail="Coinbase refresh response contained no access token.",
        )
    # Coinbase rotates the refresh token; fall back to the old one only if the
    # response omitted it entirely.
    new_refresh = str(token_data.get("refresh_token") or "").strip() or refresh_token
    expires_at = oauth.compute_expiry_timestamp(
        int(token_data.get("expires_in") or 3600)
    )

    persisted = persist_tokens(
        user_id,
        access_token=new_access,
        refresh_token=new_refresh,
        expires_at=expires_at,
    )
    if not persisted:
        # The old refresh token is now dead. Surface this loudly: the next run
        # will fail auth and the user will need to reconnect.
        logger.error(
            "[PortfolioCredentials] refreshed user %s but could not persist the "
            "rotated refresh token; connection may need to be re-established",
            user_id,
        )

    return ResolvedCredentials(
        status=CredentialStatus.REFRESHED,
        user_id=user_id,
        client=CoinbaseAdvancedTradeClient(oauth_access_token=new_access),
        access_token=new_access,
        detail=None if persisted else "Refreshed but token persistence failed.",
    )


def resolve_env_owner_credentials() -> ResolvedCredentials:
    """Single-owner API-key fallback (COINBASE_API_KEY_NAME/SECRET)."""
    try:
        client = CoinbaseAdvancedTradeClient.from_environment()
    except Exception as exc:
        return ResolvedCredentials(
            status=CredentialStatus.NOT_CONNECTED,
            detail=f"Environment Coinbase key unavailable: {exc}",
        )
    return ResolvedCredentials(status=CredentialStatus.ENV_OWNER, client=client)


def resolve_portfolio_service(user_id: int) -> tuple[Any, ResolvedCredentials]:
    """Resolve a ``PortfolioService`` for a user, or (None, reason)."""
    resolved = resolve_user_credentials(user_id)
    if resolved.usable:
        return PortfolioService(resolved.client), resolved

    # Fall back to the env-owner key only when the user simply never connected.
    if resolved.status == CredentialStatus.NOT_CONNECTED:
        env = resolve_env_owner_credentials()
        if env.usable:
            env.user_id = user_id
            return PortfolioService(env.client), env
    return None, resolved


def list_snapshot_eligible_users() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Partition known users into (eligible, ineligible-with-reason).

    Eligibility is decided from *stored state* only — no network calls — so a
    scheduling cycle can report who it intends to check before it checks them.
    A user with an expired token but a usable refresh token is eligible: the
    refresh happens at capture time.
    """
    try:
        _db_connect, _DB_LOCK, _ = _watchlist_db()
    except Exception:
        logger.debug("[PortfolioCredentials] user store unavailable", exc_info=True)
        return [], []

    try:
        conn = _db_connect()
        try:
            rows = conn.execute(
                """
                SELECT id, email,
                       coinbase_oauth_access_token AS access_token,
                       coinbase_oauth_refresh_token AS refresh_token,
                       coinbase_oauth_expires_at AS expires_at
                FROM users
                """
            ).fetchall()
        finally:
            conn.close()
    except Exception:
        logger.debug("[PortfolioCredentials] user enumeration failed", exc_info=True)
        return [], []

    owner_email = str(os.getenv("COINBASE_PORTFOLIO_OWNER_EMAIL") or "").strip().lower()
    env_owner_configured = bool(
        str(os.getenv("COINBASE_API_KEY_NAME") or "").strip()
        and str(os.getenv("COINBASE_API_KEY_SECRET") or "").strip()
    )

    eligible: list[dict[str, Any]] = []
    ineligible: list[dict[str, Any]] = []
    for row in rows:
        user_id = int(row["id"])
        access_token = str(row["access_token"] or "").strip()
        refresh_token = str(row["refresh_token"] or "").strip()
        is_owner = (
            owner_email and str(row["email"] or "").strip().lower() == owner_email
        )

        if access_token:
            # Expired with no refresh token is a dead connection — say so.
            if _token_needs_refresh(row["expires_at"]) and not refresh_token:
                ineligible.append(
                    {
                        "user_id": user_id,
                        "reason": CredentialStatus.REFRESH_FAILED,
                        "detail": "Token expired and no refresh token stored; user must reconnect.",
                    }
                )
                continue
            eligible.append({"user_id": user_id, "auth": "oauth"})
        elif is_owner and env_owner_configured:
            eligible.append({"user_id": user_id, "auth": "env_owner"})
        else:
            ineligible.append(
                {
                    "user_id": user_id,
                    "reason": CredentialStatus.NOT_CONNECTED,
                    "detail": "No Coinbase connection.",
                }
            )
    return eligible, ineligible


__all__ = [
    "CredentialStatus",
    "ResolvedCredentials",
    "USABLE_STATUSES",
    "list_snapshot_eligible_users",
    "load_stored_tokens",
    "persist_tokens",
    "resolve_env_owner_credentials",
    "resolve_portfolio_service",
    "resolve_user_credentials",
]
