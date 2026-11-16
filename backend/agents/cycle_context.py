"""Builds the cycle inputs that ``CycleStrategistAgent`` and smart alerts read.

Both consume the same three things: a ``scan_universe_cycles`` payload, the
held positions and the watchlist. Keeping the shape in one place lets the
local runner script and any backend caller hand agents identical context.
"""

from __future__ import annotations

from datetime import datetime
import math
import re
import time
from typing import Any, Callable, Iterable, Mapping


MAX_SCAN_AGE_SECONDS = 1800
EXCHANGE_BOOK_URL = "https://api.exchange.coinbase.com/products/{product_id}/book"
QUOTE_TIMEOUT_SECONDS = 4.0
MAX_QUOTE_PRODUCTS = 30
RISK_KEYS = ("portfolio_equity_usd", "base_risk_pct", "max_open_risk_pct")
_SYMBOL = re.compile(r"[A-Z0-9]{1,15}")


def _symbol(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    base = value.strip().upper().split("-")[0].split("/")[0]
    return base if _SYMBOL.fullmatch(base) else None


def _finite(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return out if math.isfinite(out) else None


def _positive(value: Any) -> float | None:
    out = _finite(value)
    return out if out is not None and out > 0 else None


def usable_cycle_scan(scan: Any, *, now: float | None = None) -> bool:
    """Allow pure scanner output or fresh, ready data from the Flask route."""
    if not isinstance(scan, Mapping) or not isinstance(scan.get("coins"), list) or not scan["coins"]:
        return False
    if not {"status", "computed_at", "ttl_seconds"}.intersection(scan):
        return True  # Pure in-process scanner result.
    computed = _finite(scan.get("computed_at"))
    ttl = _positive(scan.get("ttl_seconds"))
    if scan.get("status") != "ready" or computed is None or ttl is None:
        return False
    age = (time.time() if now is None else now) - computed
    return 0 <= age < min(ttl, MAX_SCAN_AGE_SECONDS)


def normalize_positions(rows: Iterable[Mapping[str, Any]] | None) -> list[dict]:
    """Keep rows with a symbol and a positive quantity, one per symbol (summed)."""
    merged: dict[str, dict] = {}
    seen_tickets: set[tuple[str, str]] = set()
    for row in rows or []:
        if not isinstance(row, Mapping):
            continue
        symbol = _symbol(row.get("symbol") or row.get("product_id"))
        quantity = _positive(row.get("quantity") if "quantity" in row else row.get("size"))
        if not symbol or quantity is None:
            continue
        ticket = row.get("ticket_id")
        if isinstance(ticket, str) and ticket:
            key = (symbol, ticket)
            if key in seen_tickets:
                continue
            seen_tickets.add(key)
        if symbol not in merged:
            merged[symbol] = {"symbol": symbol, "product_id": f"{symbol}-USD", "quantity": 0.0}
        clean = merged[symbol]
        clean["quantity"] += quantity
        for key in ("stop_price", "higher_low_floor"):
            level = _positive(row.get(key))
            if level is not None:
                clean[key] = max(level, clean.get(key, 0.0))
        for key in ("cost_basis", "entry_price", "source"):
            if row.get(key) is not None:
                clean.setdefault(key, row[key])
    return [merged[symbol] for symbol in sorted(merged) if math.isfinite(merged[symbol]["quantity"])]


def normalize_watchlist(symbols: Iterable[Any] | None) -> list[str]:
    out: list[str] = []
    for raw in symbols or []:
        symbol = _symbol((raw.get("symbol") or raw.get("product_id")) if isinstance(raw, Mapping) else raw)
        if symbol and symbol not in out:
            out.append(symbol)
    return out


def _unavailable(product_id: str, reason: str) -> dict[str, Any]:
    return {"product_id": product_id, "quote_status": "UNAVAILABLE", "reason": reason}


def fetch_top_of_book(
    product_id: str,
    *,
    http_get: Callable[..., Any] | None = None,
    timeout: float = QUOTE_TIMEOUT_SECONDS,
    now_ms: Callable[[], int] | None = None,
) -> dict[str, Any]:
    """One public, read-only level-1 book from Coinbase Exchange.

    Returns the quote shape ``GuardedDryRunExitExecutor`` checks: both sides,
    the bid size, the local receipt time and Coinbase's own book time. Any
    failure returns ``quote_status: "UNAVAILABLE"`` with a reason and never
    raises, so one bad product cannot stop an agent pass.
    """
    symbol = _symbol(product_id)
    if not symbol or product_id != f"{symbol}-USD":
        return _unavailable(str(product_id), "invalid_product")
    if http_get is None:
        import requests

        http_get = requests.get
    try:
        response = http_get(
            EXCHANGE_BOOK_URL.format(product_id=product_id),
            params={"level": 1},
            timeout=timeout,
            headers={"User-Agent": "moonwalking-local-agents", "Accept": "application/json"},
        )
        observed = int(now_ms()) if now_ms else time.time_ns() // 1_000_000
        response.raise_for_status()
        book = response.json()
    except Exception as exc:  # network, HTTP status or body decoding
        return _unavailable(product_id, f"request_failed:{type(exc).__name__}")
    if not isinstance(book, Mapping):
        return _unavailable(product_id, "malformed_book")
    if book.get("auction_mode"):
        return _unavailable(product_id, "auction_mode")

    def top(side: str) -> tuple[float | None, float | None]:
        levels = book.get(side)
        if not isinstance(levels, list) or not levels:
            return None, None
        level = levels[0]
        if not isinstance(level, (list, tuple)) or len(level) < 2:
            return None, None
        return _positive(level[0]), _positive(level[1])

    (bid, bid_size), (ask, ask_size) = top("bids"), top("asks")
    exchange_ms = None
    stamp = book.get("time")
    if isinstance(stamp, str):
        try:
            parsed = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
            if parsed.tzinfo is not None:
                exchange_ms = int(parsed.timestamp() * 1000)
        except ValueError:
            pass
    return {
        "product_id": product_id,
        "quote_status": "AVAILABLE" if bid is not None and ask is not None else "UNAVAILABLE",
        "source": "coinbase_exchange_book_level_1",
        "observed_at_ms": observed,
        "exchange_time_ms": exchange_ms,
        "bid_usd": bid,
        "bid_size": bid_size,
        "ask_usd": ask,
        "ask_size": ask_size,
    }


def fetch_live_quotes(
    products: Iterable[Any],
    *,
    http_get: Callable[..., Any] | None = None,
    timeout: float = QUOTE_TIMEOUT_SECONDS,
    now_ms: Callable[[], int] | None = None,
) -> dict[str, dict[str, Any]]:
    """Level-1 quotes keyed by ``BASE-USD`` for up to ``MAX_QUOTE_PRODUCTS`` coins."""
    quotes: dict[str, dict[str, Any]] = {}
    for symbol in normalize_watchlist(products)[:MAX_QUOTE_PRODUCTS]:
        product_id = f"{symbol}-USD"
        quotes[product_id] = fetch_top_of_book(
            product_id, http_get=http_get, timeout=timeout, now_ms=now_ms
        )
    return quotes


def build_cycle_context(
    scan: Mapping[str, Any] | None,
    *,
    positions: Iterable[Mapping[str, Any]] | None = None,
    watchlist: Iterable[Any] | None = None,
    quotes: Mapping[str, Any] | None = None,
    quote_fetcher: Callable[[list[str]], Mapping[str, Any]] | None = None,
    risk: Mapping[str, Any] | None = None,
    now: float | None = None,
) -> dict[str, Any]:
    """Context keys read by ``CycleStrategistAgent`` and ``evaluate_smart_alerts``.

    A warming, refreshing or stale HTTP scan is passed as ``None`` so agents
    skip the pass, and structured per-coin evidence is preserved.

    ``quote_fetcher`` (for example ``fetch_live_quotes``) is called by the
    strategist for the exits it is about to simulate, so those quotes are
    fresh at the guard. ``risk`` may carry ``portfolio_equity_usd``,
    ``base_risk_pct`` and ``max_open_risk_pct``.
    """
    context: dict[str, Any] = {
        "cycle_scan": dict(scan) if usable_cycle_scan(scan, now=now) else None,
        "positions": normalize_positions(positions),
        "watchlist": normalize_watchlist(watchlist),
    }
    if isinstance(quotes, Mapping) and quotes:
        context["quotes"] = dict(quotes)
    if callable(quote_fetcher):
        context["quote_fetcher"] = quote_fetcher
    for key in RISK_KEYS:
        value = _positive((risk or {}).get(key))
        if value is not None:
            context[key] = value
    return context


def evaluate_smart_alerts(context: Mapping[str, Any], engine: Any) -> dict[str, Any]:
    """Run the smart alert rules over the context's cycle scan."""
    scan = context.get("cycle_scan")
    now = _finite(context.get("now_ts"))
    if not usable_cycle_scan(scan, now=now):
        return {"status": "skipped", "reason": "no_cycle_scan", "fired": []}
    fired = engine.evaluate(
        scan,
        positions=context.get("positions") or [],
        watchlist=context.get("watchlist") or [],
        now=now,
    )
    return {"status": "ok", "fired": fired}
