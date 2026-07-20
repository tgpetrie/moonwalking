"""Coinbase OAuth 2.0 integration for user-managed portfolio authentication."""

import os
import secrets
import json
import time
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any
from urllib.parse import urlencode

import requests


COINBASE_OAUTH_AUTHORIZE_URL = "https://www.coinbase.com/oauth/authorize"
COINBASE_OAUTH_TOKEN_URL = "https://api.coinbase.com/oauth/token"
COINBASE_API_BASE = "https://api.coinbase.com"


class CoinbaseOAuthConfig:
    """Coinbase OAuth app credentials from environment."""

    def __init__(self):
        self.client_id = os.environ.get("COINBASE_OAUTH_CLIENT_ID", "").strip()
        self.client_secret = os.environ.get("COINBASE_OAUTH_CLIENT_SECRET", "").strip()
        self.redirect_uri = os.environ.get(
            "COINBASE_OAUTH_REDIRECT_URI",
            "http://127.0.0.1:5003/api/oauth/coinbase/callback",
        ).strip()

    def is_configured(self) -> bool:
        return bool(self.client_id and self.client_secret)


class OAuthTokenError(RuntimeError):
    """Raised when OAuth token operations fail."""

    pass


def generate_authorization_url(
    config: CoinbaseOAuthConfig, user_id: int
) -> tuple[str, str]:
    """Generate the Coinbase OAuth authorization URL.

    Returns:
        (authorization_url, state_token) — caller must store state in session for CSRF validation.
    """
    if not config.is_configured():
        raise OAuthTokenError("Coinbase OAuth is not configured on this server.")

    state = f"{user_id}-{secrets.token_hex(16)}"

    params = {
        "client_id": config.client_id,
        "redirect_uri": config.redirect_uri,
        "response_type": "code",
        "state": state,
        "scope": "wallet:accounts:read wallet:transactions:read",
    }
    return f"{COINBASE_OAUTH_AUTHORIZE_URL}?{urlencode(params)}", state


def exchange_authorization_code(
    config: CoinbaseOAuthConfig, code: str
) -> Dict[str, Any]:
    """Exchange authorization code for access token.

    Args:
        config: OAuth configuration
        code: Authorization code from Coinbase callback

    Returns:
        Token response with access_token, refresh_token, expires_in, etc.

    Raises:
        OAuthTokenError: If exchange fails
    """
    if not config.is_configured():
        raise OAuthTokenError("Coinbase OAuth is not configured on this server.")

    try:
        response = requests.post(
            COINBASE_OAUTH_TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "client_id": config.client_id,
                "client_secret": config.client_secret,
                "redirect_uri": config.redirect_uri,
            },
            timeout=10,
        )
    except requests.RequestException as exc:
        raise OAuthTokenError(f"Failed to exchange authorization code: {exc}") from exc

    if response.status_code >= 400:
        try:
            error_data = response.json()
            error_msg = error_data.get("error_description") or error_data.get("error")
        except Exception:
            error_msg = f"HTTP {response.status_code}"
        raise OAuthTokenError(f"Coinbase OAuth token exchange failed: {error_msg}")

    try:
        token_data = response.json()
    except Exception as exc:
        raise OAuthTokenError(f"Invalid token response from Coinbase: {exc}") from exc

    return token_data


def refresh_access_token(
    config: CoinbaseOAuthConfig, refresh_token: str
) -> Dict[str, Any]:
    """Refresh an expired access token using the refresh token.

    Args:
        config: OAuth configuration
        refresh_token: The refresh token

    Returns:
        New token response with access_token, expires_in, etc.

    Raises:
        OAuthTokenError: If refresh fails
    """
    if not config.is_configured():
        raise OAuthTokenError("Coinbase OAuth is not configured on this server.")

    try:
        response = requests.post(
            COINBASE_OAUTH_TOKEN_URL,
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": config.client_id,
                "client_secret": config.client_secret,
            },
            timeout=10,
        )
    except requests.RequestException as exc:
        raise OAuthTokenError(f"Failed to refresh access token: {exc}") from exc

    if response.status_code >= 400:
        try:
            error_data = response.json()
            error_msg = error_data.get("error_description") or error_data.get("error")
        except Exception:
            error_msg = f"HTTP {response.status_code}"
        raise OAuthTokenError(f"Coinbase token refresh failed: {error_msg}")

    try:
        token_data = response.json()
    except Exception as exc:
        raise OAuthTokenError(f"Invalid refresh response from Coinbase: {exc}") from exc

    return token_data


def get_valid_access_token(
    config: CoinbaseOAuthConfig,
    access_token: Optional[str],
    refresh_token: Optional[str],
    expires_at: Optional[str],
) -> Optional[str]:
    """Get a valid access token, refreshing if necessary.

    Args:
        config: OAuth configuration
        access_token: Current access token
        refresh_token: Refresh token
        expires_at: ISO timestamp of when access token expires

    Returns:
        Valid access token, or None if no refresh token available

    Raises:
        OAuthTokenError: If refresh fails
    """
    if not access_token:
        return None

    # Check if token is expired or expiring soon (within 5 minutes)
    if expires_at:
        try:
            expires_dt = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
            now = datetime.now(timezone.utc)
            if now < expires_dt - timedelta(minutes=5):
                return access_token
        except Exception:
            pass

    # Try to refresh
    if refresh_token:
        token_data = refresh_access_token(config, refresh_token)
        return token_data.get("access_token")

    return access_token


def compute_expiry_timestamp(expires_in_seconds: int) -> str:
    """Compute ISO 8601 expiry timestamp from expires_in value.

    Args:
        expires_in_seconds: Seconds until token expires

    Returns:
        ISO 8601 timestamp (with Z suffix)
    """
    expiry = datetime.now(timezone.utc) + timedelta(seconds=expires_in_seconds)
    return expiry.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def get_user_info(config: CoinbaseOAuthConfig, access_token: str) -> Dict[str, Any]:
    """Fetch the authenticated user's info from Coinbase.

    Args:
        config: OAuth configuration
        access_token: Valid OAuth access token

    Returns:
        User info dict with id, name, email, etc.

    Raises:
        OAuthTokenError: If fetch fails
    """
    try:
        response = requests.get(
            f"{COINBASE_API_BASE}/api/v3/brokerage/user",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/json",
            },
            timeout=10,
        )
    except requests.RequestException as exc:
        raise OAuthTokenError(f"Failed to fetch user info: {exc}") from exc

    if response.status_code >= 400:
        raise OAuthTokenError(
            f"Coinbase rejected user info request: HTTP {response.status_code}"
        )

    try:
        user_data = response.json()
    except Exception as exc:
        raise OAuthTokenError(f"Invalid user info response: {exc}") from exc

    return user_data if isinstance(user_data, dict) else {}
