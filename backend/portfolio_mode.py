"""Authenticated, owner-only, view-only Coinbase Portfolio Mode.

This module deliberately exposes GET routes only. It validates Coinbase key
permissions before loading balances and refuses keys that can trade or transfer.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import os
import threading
import time
from typing import Any, Iterable

import requests
from flask import Blueprint, jsonify, request

try:
    from watchlist import get_authenticated_user
except ImportError:  # package-style imports used by pytest from the repo root
    from backend.watchlist import get_authenticated_user


portfolio_bp = Blueprint("portfolio_mode", __name__)

COINBASE_HOST = "api.coinbase.com"
COINBASE_BASE_URL = f"https://{COINBASE_HOST}"
OPEN_ORDER_STATUSES = {"PENDING", "OPEN", "QUEUED", "CANCEL_QUEUED", "EDIT_QUEUED"}
USD_EQUIVALENTS = {"USD", "USDC"}


def _decimal(value: Any) -> Decimal:
    try:
        parsed = Decimal(str(value or "0"))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal("0")
    return parsed if parsed.is_finite() else Decimal("0")


def _float(value: Decimal | Any) -> float | None:
    if value in (None, "") or isinstance(value, bool):
        return None
    raw = str(value).strip()
    if raw.endswith("%"):
        raw = raw[:-1]
    try:
        parsed = Decimal(raw)
    except (InvalidOperation, TypeError, ValueError):
        return None
    return float(parsed) if parsed.is_finite() else None


def _iso_now() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _normalize_secret(value: str) -> str:
    return str(value or "").strip().replace("\\n", "\n")


class PortfolioModeError(RuntimeError):
    code = "portfolio_error"
    http_status = 503

    def __init__(self, message: str, *, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.details = details or {}


class PortfolioNotConfigured(PortfolioModeError):
    code = "coinbase_not_configured"


class PortfolioDependencyMissing(PortfolioModeError):
    code = "coinbase_auth_dependency_missing"


class CoinbaseRequestError(PortfolioModeError):
    code = "coinbase_unavailable"


class UnsafeCoinbasePermissions(PortfolioModeError):
    code = "unsafe_coinbase_permissions"
    http_status = 409


@dataclass
class PageResult:
    items: list[dict[str, Any]]
    complete: bool = True


class CoinbaseAdvancedTradeClient:
    """Small read-only Advanced Trade client using Coinbase App JWT auth."""

    def __init__(
        self,
        api_key_name: str,
        api_key_secret: str,
        *,
        http_session: requests.Session | None = None,
        timeout: float = 10.0,
    ):
        self.api_key_name = str(api_key_name or "").strip()
        self.api_key_secret = _normalize_secret(api_key_secret)
        self.http = http_session or requests.Session()
        self.timeout = timeout

    @classmethod
    def from_environment(cls) -> "CoinbaseAdvancedTradeClient":
        key_name = os.environ.get("COINBASE_API_KEY_NAME", "").strip()
        key_secret = _normalize_secret(os.environ.get("COINBASE_API_KEY_SECRET", ""))
        if not key_name or not key_secret:
            raise PortfolioNotConfigured(
                "Coinbase Portfolio Mode is not configured on this server."
            )
        return cls(key_name, key_secret)

    def _jwt(self, method: str, path: str) -> str:
        try:
            from cdp.auth.utils.jwt import JwtOptions, generate_jwt
        except ImportError as exc:
            raise PortfolioDependencyMissing(
                "Coinbase authentication support is not installed on this server."
            ) from exc

        return generate_jwt(
            JwtOptions(
                api_key_id=self.api_key_name,
                api_key_secret=self.api_key_secret,
                request_method=method.upper(),
                request_host=COINBASE_HOST,
                request_path=path,
                expires_in=120,
            )
        )

    def get(self, path: str, *, params: dict[str, Any] | None = None) -> dict[str, Any]:
        try:
            response = self.http.get(
                f"{COINBASE_BASE_URL}{path}",
                params=params or None,
                headers={
                    "Authorization": f"Bearer {self._jwt('GET', path)}",
                    "Accept": "application/json",
                    "Cache-Control": "no-cache",
                },
                timeout=self.timeout,
            )
        except PortfolioModeError:
            raise
        except requests.RequestException as exc:
            raise CoinbaseRequestError("Coinbase did not respond in time.") from exc

        if response.status_code >= 400:
            if response.status_code in (401, 403):
                message = "Coinbase rejected the configured key or its permissions."
            elif response.status_code == 429:
                message = "Coinbase temporarily rate-limited Portfolio Mode."
            else:
                message = "Coinbase portfolio data is temporarily unavailable."
            raise CoinbaseRequestError(message)

        try:
            payload = response.json()
        except ValueError as exc:
            raise CoinbaseRequestError(
                "Coinbase returned an unreadable response."
            ) from exc
        return payload if isinstance(payload, dict) else {}

    def _pages(
        self,
        path: str,
        field: str,
        *,
        limit: int,
        max_pages: int = 5,
    ) -> PageResult:
        cursor = ""
        items: list[dict[str, Any]] = []
        complete = True
        for page_index in range(max_pages):
            params: dict[str, Any] = {"limit": limit}
            if cursor:
                params["cursor"] = cursor
            payload = self.get(path, params=params)
            page_items = payload.get(field)
            if isinstance(page_items, list):
                items.extend(item for item in page_items if isinstance(item, dict))
            if payload.get("proof_token_required") is True:
                return PageResult(items=items, complete=False)
            cursor = str(payload.get("cursor") or "")
            has_next_value = payload.get("has_next")
            has_next = (
                bool(has_next_value)
                if has_next_value is not None
                else bool(cursor)
                and isinstance(page_items, list)
                and len(page_items) >= limit
            )
            if not has_next or not cursor:
                return PageResult(items=items, complete=True)
            if page_index == max_pages - 1:
                complete = False
        return PageResult(items=items, complete=complete)

    def get_key_permissions(self) -> dict[str, Any]:
        return self.get("/api/v3/brokerage/key_permissions")

    def list_accounts(self) -> PageResult:
        return self._pages("/api/v3/brokerage/accounts", "accounts", limit=250)

    def list_fills(self) -> PageResult:
        return self._pages(
            "/api/v3/brokerage/orders/historical/fills",
            "fills",
            limit=1000,
        )

    def list_orders(self) -> PageResult:
        return self._pages(
            "/api/v3/brokerage/orders/historical/batch",
            "orders",
            limit=250,
        )

    def get_product(self, product_id: str) -> dict[str, Any]:
        return self.get(f"/api/v3/brokerage/products/{product_id}")


def _fill_base_quantity(fill: dict[str, Any]) -> Decimal:
    size = _decimal(fill.get("size"))
    price = _decimal(fill.get("price"))
    if fill.get("size_in_quote") is True:
        return (size / price) if price > 0 else Decimal("0")
    return size


def reconstruct_cost_basis(
    currency: str,
    current_quantity: Decimal,
    fills: Iterable[dict[str, Any]],
    *,
    history_complete: bool = True,
) -> dict[str, Any]:
    """Reconstruct weighted cost only for quantity covered by USD fills.

    Any current quantity above fill-covered inventory is explicitly unknown.
    """

    relevant: list[dict[str, Any]] = []
    for fill in fills:
        product_id = str(fill.get("product_id") or "").upper()
        parts = product_id.split("-")
        if len(parts) < 2 or parts[0] != currency or parts[1] not in USD_EQUIVALENTS:
            continue
        relevant.append(fill)
    relevant.sort(
        key=lambda item: str(
            item.get("trade_time") or item.get("sequence_timestamp") or ""
        )
    )

    covered_quantity = Decimal("0")
    covered_cost = Decimal("0")
    for fill in relevant:
        quantity = _fill_base_quantity(fill)
        price = _decimal(fill.get("price"))
        commission = _decimal(fill.get("commission"))
        if quantity <= 0 or price <= 0:
            continue
        side = str(fill.get("side") or "").upper()
        if side == "BUY":
            covered_quantity += quantity
            covered_cost += (quantity * price) + commission
        elif side == "SELL" and covered_quantity > 0:
            removed = min(quantity, covered_quantity)
            average = covered_cost / covered_quantity
            covered_quantity -= removed
            covered_cost = max(Decimal("0"), covered_cost - (average * removed))

    tolerance = max(Decimal("0.00000001"), current_quantity * Decimal("0.005"))
    unknown_quantity = max(Decimal("0"), current_quantity - covered_quantity)
    known_quantity = min(current_quantity, covered_quantity)
    average_price = (covered_cost / covered_quantity) if covered_quantity > 0 else None
    known_cost = (average_price * known_quantity) if average_price is not None else None

    if current_quantity <= 0:
        status = "not_applicable"
    elif known_quantity <= tolerance:
        status = "unavailable"
    elif unknown_quantity > tolerance or not history_complete:
        status = "partial"
    else:
        status = "complete"

    return {
        "status": status,
        "average_price": _float(average_price) if average_price is not None else None,
        "known_quantity": _float(known_quantity),
        "unknown_quantity": _float(unknown_quantity),
        "known_cost_usd": _float(known_cost) if known_cost is not None else None,
        "fill_count": len(relevant),
        "history_complete": bool(history_complete),
        "source": "coinbase_advanced_trade_fills",
    }


def _account_quantity(account: dict[str, Any]) -> tuple[Decimal, Decimal, Decimal]:
    available = _decimal((account.get("available_balance") or {}).get("value"))
    held = _decimal((account.get("hold") or {}).get("value"))
    return available + held, available, held


def _order_value(order: dict[str, Any], keys: tuple[str, ...]) -> Any:
    configuration = order.get("order_configuration")
    if not isinstance(configuration, dict):
        return None
    for child in configuration.values():
        if not isinstance(child, dict):
            continue
        for key in keys:
            if child.get(key) not in (None, ""):
                return child.get(key)
    return None


def _serialize_open_order(order: dict[str, Any]) -> dict[str, Any]:
    return {
        "order_id": order.get("order_id"),
        "product_id": order.get("product_id"),
        "symbol": str(order.get("product_id") or "").split("-")[0],
        "side": str(order.get("side") or "").upper(),
        "status": str(order.get("status") or "UNKNOWN").upper(),
        "created_at": order.get("created_time") or order.get("created_at"),
        "limit_price": _float(_order_value(order, ("limit_price", "stop_price"))),
        "base_size": _float(_order_value(order, ("base_size",))),
        "quote_size": _float(_order_value(order, ("quote_size",))),
        "filled_size": _float(order.get("filled_size")),
    }


class PortfolioService:
    def __init__(
        self,
        client: CoinbaseAdvancedTradeClient | Any,
        *,
        cache_ttl_seconds: int = 30,
        stale_ttl_seconds: int = 300,
    ):
        self.client = client
        self.cache_ttl_seconds = max(5, cache_ttl_seconds)
        self.stale_ttl_seconds = max(self.cache_ttl_seconds, stale_ttl_seconds)
        self._cache: dict[str, Any] | None = None
        self._cache_time = 0.0
        self._lock = threading.Lock()

    @staticmethod
    def _safe_permissions(raw: dict[str, Any]) -> dict[str, Any]:
        return {
            "can_view": bool(raw.get("can_view")),
            "can_trade": bool(raw.get("can_trade")),
            "can_transfer": bool(raw.get("can_transfer")),
            "can_receive": bool(raw.get("can_receive")),
            "portfolio_id": raw.get("portfolio_uuid"),
            "portfolio_type": raw.get("portfolio_type"),
        }

    def snapshot(self, *, force: bool = False) -> dict[str, Any]:
        now = time.monotonic()
        with self._lock:
            if (
                not force
                and self._cache
                and (now - self._cache_time) < self.cache_ttl_seconds
            ):
                cached = deepcopy(self._cache)
                cached["cache"] = "fresh"
                return cached

            try:
                snapshot = self._load()
            except CoinbaseRequestError:
                if self._cache and (now - self._cache_time) < self.stale_ttl_seconds:
                    cached = deepcopy(self._cache)
                    cached["status"] = "stale"
                    cached["cache"] = "last_good"
                    cached["stale_seconds"] = int(now - self._cache_time)
                    return cached
                raise

            self._cache = deepcopy(snapshot)
            self._cache_time = now
            return snapshot

    def held_symbols(self, *, fetch: bool = False) -> set[str]:
        """Non-cash currencies currently held, as base symbols (e.g. {"BTC"}).

        With fetch=False this only reads the in-memory cache and never touches
        the network, so it is safe on request paths. fetch=True may refresh
        via snapshot() and belongs in background threads only.
        """
        snapshot: dict[str, Any] | None
        if fetch:
            snapshot = self.snapshot()
        else:
            with self._lock:
                snapshot = deepcopy(self._cache) if self._cache else None
        if not snapshot:
            return set()
        return {
            str(row.get("currency") or "").upper()
            for row in snapshot.get("holdings") or []
            if row.get("currency") and not row.get("is_cash")
        }

    def _load(self) -> dict[str, Any]:
        permissions = self._safe_permissions(self.client.get_key_permissions())
        if not permissions["can_view"]:
            raise UnsafeCoinbasePermissions(
                "The configured Coinbase key does not have View permission.",
                details={"permissions": permissions},
            )
        if permissions["can_trade"] or permissions["can_transfer"]:
            raise UnsafeCoinbasePermissions(
                "Stage 1 requires a View-only Coinbase key with Trade and Transfer disabled.",
                details={"permissions": permissions},
            )

        accounts_page = self.client.list_accounts()
        fills_page = self.client.list_fills()
        orders_page = self.client.list_orders()
        active_orders = [
            order
            for order in orders_page.items
            if str(order.get("status") or "").upper() in OPEN_ORDER_STATUSES
        ]

        account_rows: list[tuple[dict[str, Any], Decimal, Decimal, Decimal]] = []
        for account in accounts_page.items:
            if account.get("active") is False or account.get("ready") is False:
                continue
            quantity, available, held = _account_quantity(account)
            if quantity <= 0:
                continue
            account_rows.append((account, quantity, available, held))

        prices: dict[str, tuple[Decimal, str | None, dict[str, Any]]] = {}
        for account, _quantity, _available, _held in account_rows:
            currency = str(account.get("currency") or "").upper()
            if currency in USD_EQUIVALENTS:
                prices[currency] = (Decimal("1"), None, {})
                continue
            product_payload: dict[str, Any] = {}
            product_id: str | None = None
            for quote in ("USD", "USDC"):
                candidate = f"{currency}-{quote}"
                try:
                    product_payload = self.client.get_product(candidate)
                    price = _decimal(product_payload.get("price"))
                except CoinbaseRequestError:
                    continue
                if price > 0:
                    product_id = candidate
                    prices[currency] = (price, product_id, product_payload)
                    break
            if currency not in prices:
                prices[currency] = (Decimal("0"), product_id, product_payload)

        holdings: list[dict[str, Any]] = []
        for account, quantity, available, held in account_rows:
            currency = str(account.get("currency") or "").upper()
            price, product_id, product = prices.get(currency, (Decimal("0"), None, {}))
            market_value = quantity * price if price > 0 else None
            is_cash = currency in USD_EQUIVALENTS
            if is_cash:
                cost_basis = {
                    "status": "not_applicable",
                    "average_price": 1.0,
                    "known_quantity": _float(quantity),
                    "unknown_quantity": 0.0,
                    "known_cost_usd": _float(quantity),
                    "fill_count": 0,
                    "history_complete": fills_page.complete,
                    "source": "cash_balance",
                }
            else:
                cost_basis = reconstruct_cost_basis(
                    currency,
                    quantity,
                    fills_page.items,
                    history_complete=fills_page.complete,
                )

            unrealized_pnl = None
            unrealized_pnl_pct = None
            known_cost = _decimal(cost_basis.get("known_cost_usd"))
            if (
                cost_basis["status"] == "complete"
                and market_value is not None
                and known_cost > 0
            ):
                unrealized_pnl = market_value - known_cost
                unrealized_pnl_pct = (unrealized_pnl / known_cost) * Decimal("100")

            holdings.append(
                {
                    "account_id": account.get("uuid"),
                    "product_id": product_id,
                    "symbol": currency,
                    "name": account.get("name") or currency,
                    "quantity": _float(quantity),
                    "available_quantity": _float(available),
                    "held_quantity": _float(held),
                    "price_usd": _float(price) if price > 0 else None,
                    "market_value_usd": (
                        _float(market_value) if market_value is not None else None
                    ),
                    "allocation_pct": None,
                    "price_change_24h_pct": _float(
                        product.get("price_percentage_change_24h")
                    ),
                    "is_cash": is_cash,
                    "cost_basis": cost_basis,
                    "unrealized_pnl_usd": (
                        _float(unrealized_pnl) if unrealized_pnl is not None else None
                    ),
                    "unrealized_pnl_pct": (
                        _float(unrealized_pnl_pct)
                        if unrealized_pnl_pct is not None
                        else None
                    ),
                }
            )

        valued = [row for row in holdings if row["market_value_usd"] is not None]
        total_value = sum(
            (_decimal(row["market_value_usd"]) for row in valued), Decimal("0")
        )
        cash_value = sum(
            (_decimal(row["market_value_usd"]) for row in valued if row["is_cash"]),
            Decimal("0"),
        )
        complete_value = sum(
            (
                _decimal(row["market_value_usd"])
                for row in valued
                if not row["is_cash"] and row["cost_basis"]["status"] == "complete"
            ),
            Decimal("0"),
        )
        crypto_value = max(Decimal("0"), total_value - cash_value)
        known_pnl = sum(
            (
                _decimal(row["unrealized_pnl_usd"])
                for row in holdings
                if row["unrealized_pnl_usd"] is not None
            ),
            Decimal("0"),
        )
        for row in holdings:
            if total_value > 0 and row["market_value_usd"] is not None:
                row["allocation_pct"] = _float(
                    (_decimal(row["market_value_usd"]) / total_value) * Decimal("100")
                )
        holdings.sort(key=lambda row: _decimal(row["market_value_usd"]), reverse=True)

        return {
            "status": "live",
            "mode": "view_only",
            "updated_at": _iso_now(),
            "cache": "refreshed",
            "permissions": permissions,
            "summary": {
                "total_value_usd": _float(total_value),
                "cash_value_usd": _float(cash_value),
                "crypto_value_usd": _float(crypto_value),
                "holding_count": sum(1 for row in holdings if not row["is_cash"]),
                "open_order_count": len(active_orders),
                "known_unrealized_pnl_usd": _float(known_pnl),
                "cost_basis_coverage_pct": _float(
                    (complete_value / crypto_value) * Decimal("100")
                    if crypto_value > 0
                    else Decimal("100")
                ),
            },
            "holdings": holdings,
            "open_orders": [
                _serialize_open_order(order) for order in active_orders[:100]
            ],
            "data_quality": {
                "accounts_complete": accounts_page.complete,
                "fills_complete": fills_page.complete,
                "orders_complete": orders_page.complete,
                "cost_basis_rule": "advanced_trade_fills_only",
            },
        }


_SERVICE: PortfolioService | None = None
_SERVICE_LOCK = threading.Lock()


def get_portfolio_service() -> PortfolioService:
    global _SERVICE
    with _SERVICE_LOCK:
        if _SERVICE is None:
            _SERVICE = PortfolioService(CoinbaseAdvancedTradeClient.from_environment())
        return _SERVICE


def get_held_symbols(*, fetch: bool = False) -> set[str]:
    """Best-effort held-symbol set; empty when Portfolio Mode is unconfigured.

    Never raises: notification prioritization must degrade to standard
    behavior rather than break alert delivery.
    """
    try:
        return get_portfolio_service().held_symbols(fetch=fetch)
    except Exception:
        return set()


def _error_payload(error: PortfolioModeError):
    payload = {
        "status": "unavailable",
        "code": error.code,
        "error": str(error),
        "mode": "view_only",
    }
    payload.update(error.details)
    return jsonify(payload), error.http_status


@portfolio_bp.route("/api/portfolio", methods=["GET"])
def portfolio_snapshot():
    user = get_authenticated_user()
    if not user:
        return (
            jsonify({"status": "unauthorized", "error": "Authentication required"}),
            401,
        )

    owner_email = (
        str(os.environ.get("COINBASE_PORTFOLIO_OWNER_EMAIL") or "").strip().lower()
    )
    if not owner_email:
        return (
            jsonify(
                {
                    "status": "setup_required",
                    "code": "portfolio_owner_not_configured",
                    "error": "Portfolio Mode owner access is not configured on this server.",
                    "mode": "view_only",
                    "required_secrets": [
                        "COINBASE_PORTFOLIO_OWNER_EMAIL",
                        "COINBASE_API_KEY_NAME",
                        "COINBASE_API_KEY_SECRET",
                    ],
                }
            ),
            503,
        )
    if str(user.get("email") or "").strip().lower() != owner_email:
        return (
            jsonify(
                {
                    "status": "forbidden",
                    "code": "portfolio_owner_only",
                    "error": "Portfolio Mode is private to the configured owner account.",
                }
            ),
            403,
        )

    force = str(request.args.get("refresh") or "").lower() in {"1", "true", "yes"}
    try:
        return jsonify(get_portfolio_service().snapshot(force=force))
    except PortfolioModeError as error:
        return _error_payload(error)


__all__ = [
    "CoinbaseAdvancedTradeClient",
    "PortfolioService",
    "PortfolioModeError",
    "UnsafeCoinbasePermissions",
    "portfolio_bp",
    "reconstruct_cost_basis",
]
