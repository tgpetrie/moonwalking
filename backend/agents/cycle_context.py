"""Builds the cycle inputs that ``CycleStrategistAgent`` and smart alerts read.

Both consume the same three things: a ``scan_universe_cycles`` payload, the
held positions and the watchlist. Keeping the shape in one place lets the
local runner script and any backend caller hand agents identical context.
"""

from __future__ import annotations

from datetime import datetime
from copy import deepcopy
from itertools import islice
import math
import re
import time
from typing import Any, Callable, Iterable, Mapping


MAX_SCAN_AGE_SECONDS = 1800
EXCHANGE_BOOK_URL = "https://api.exchange.coinbase.com/products/{product_id}/book"
QUOTE_TIMEOUT_SECONDS = 4.0
MAX_QUOTE_PRODUCTS = 30
# Bid levels the executor may walk when a caller asks for depth.
MAX_QUOTE_DEPTH_LEVELS = 50
QUOTE_BATCH_SECONDS = 12.0
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
    snapshot = scan.get("market_snapshot")
    if snapshot is not None:
        if not isinstance(snapshot, Mapping) or not snapshot.get("snapshot_id") or snapshot.get("timeframe") != "1d":
            return False
        cutoff = _positive(snapshot.get("as_of_ts"))
        if cutoff is None or cutoff % 86400:
            return False
        if any(
            row.get("available") and row.get("market_as_of_ts") != cutoff
            for row in scan["coins"] if isinstance(row, Mapping)
        ):
            return False
    if not {"status", "computed_at", "ttl_seconds"}.intersection(scan):
        return True  # Pure in-process scanner result.
    now = time.time() if now is None else now
    if snapshot is not None and snapshot["as_of_ts"] != int(now // 86400) * 86400:
        return False
    computed = _finite(scan.get("computed_at"))
    ttl = _positive(scan.get("ttl_seconds"))
    if scan.get("status") != "ready" or computed is None or ttl is None:
        return False
    age = now - computed
    return 0 <= age < min(ttl, MAX_SCAN_AGE_SECONDS)


def cycle_evidence(scan, symbol=None):
    """Preserve the scan revision and the coin's source candle boundary."""
    evidence = dict(scan.get("market_snapshot") or {})
    if evidence:
        evidence.update({key: scan[key] for key in ("computed_at", "ttl_seconds") if key in scan})
    if evidence and symbol:
        row = next((row for row in scan["coins"] if isinstance(row, Mapping) and row.get("symbol") == symbol), {})
        evidence.update(market_as_of_ts=row.get("market_as_of_ts"), history_id=row.get("history_id"))
    return evidence or None


def core_and_priority_ready(scan: Any, products: Iterable[Any] = ()) -> bool:
    """True when the industry regime is read and every given product is settled.

    A product is settled when it has a row in ``scan["coins"]`` or is listed as
    unavailable. Lets a pass run while the outer atlas slices are still filling.
    """
    if not isinstance(scan, Mapping) or not isinstance(scan.get("coins"), list):
        return False
    industry = scan.get("industry")
    if not isinstance(industry, Mapping) or not industry.get("available"):
        return False
    settled = {row.get("product_id") for row in scan["coins"] if isinstance(row, Mapping)}
    unavailable = scan.get("unavailable")
    if isinstance(unavailable, (list, tuple)):
        settled.update(item for item in unavailable if isinstance(item, str))
    return all(product in settled for product in products)


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
        for key in ("cost_basis", "entry_price", "source", "observed_at_ts", "opened_ts"):
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
    depth_levels: int = 1,
) -> dict[str, Any]:
    """One public, read-only book from Coinbase Exchange.

    Returns the quote shape ``GuardedDryRunExitExecutor`` checks: both sides,
    the bid size, the local receipt time and Coinbase's own book time. Any
    failure returns ``quote_status: "UNAVAILABLE"`` with a reason and never
    raises, so one bad product cannot stop an agent pass.

    ``depth_levels`` above 1 (up to ``MAX_QUOTE_DEPTH_LEVELS``) reads the
    aggregated level-2 book and adds a ``bids`` ladder of that many levels,
    which the executor walks to price the exit. The default stays level 1.
    """
    symbol = _symbol(product_id)
    if not symbol or product_id != f"{symbol}-USD":
        return _unavailable(str(product_id), "invalid_product")
    if type(depth_levels) is not int or not 1 <= depth_levels <= MAX_QUOTE_DEPTH_LEVELS:
        return _unavailable(product_id, "invalid_depth_levels")
    timeout = _positive(timeout)
    if timeout is None:
        return _unavailable(product_id, "invalid_timeout")
    if http_get is None:
        import requests

        http_get = requests.get
    try:
        response = http_get(
            EXCHANGE_BOOK_URL.format(product_id=product_id),
            params={"level": 1 if depth_levels == 1 else 2},
            timeout=min(timeout, QUOTE_TIMEOUT_SECONDS),
            allow_redirects=False,
            headers={"User-Agent": "moonwalking-local-agents", "Accept": "application/json"},
        )
        observed = int(now_ms()) if now_ms else time.time_ns() // 1_000_000
        response.raise_for_status()
        if response.status_code != 200:
            return _unavailable(product_id, "unexpected_http_status")
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
                exchange_ms = parsed.timestamp() * 1000
        except (ValueError, OverflowError, OSError):
            pass
    if exchange_ms is None or exchange_ms <= 0 or observed <= 0:
        return _unavailable(product_id, "invalid_book_time")
    if bid is None or bid_size is None or ask is None or ask_size is None or ask < bid:
        return _unavailable(product_id, "invalid_book_levels")
    quote = {
        "product_id": product_id,
        "quote_status": "AVAILABLE",
        "source": "coinbase_exchange_book_level_1",
        "observed_at_ms": observed,
        "exchange_time_ms": exchange_ms,
        "bid_usd": bid,
        "bid_size": bid_size,
        "ask_usd": ask,
        "ask_size": ask_size,
    }
    if depth_levels > 1:
        ladder = []
        for level in book.get("bids")[:depth_levels]:
            if not isinstance(level, (list, tuple)) or len(level) < 2:
                return _unavailable(product_id, "invalid_book_levels")
            price, size = _positive(level[0]), _positive(level[1])
            if price is None or size is None:
                return _unavailable(product_id, "invalid_book_levels")
            ladder.append([price, size])
        quote.update(
            source="coinbase_exchange_book_level_2",
            bids=ladder,
            book_levels_requested=depth_levels,
        )
    return quote


def fetch_live_quotes(
    products: Iterable[Any],
    *,
    http_get: Callable[..., Any] | None = None,
    timeout: float = QUOTE_TIMEOUT_SECONDS,
    now_ms: Callable[[], int] | None = None,
    depth_levels: int = 1,
) -> dict[str, dict[str, Any]]:
    """Quotes keyed by ``BASE-USD`` for up to ``MAX_QUOTE_PRODUCTS`` coins.

    Level 1 by default; ``depth_levels`` is passed to ``fetch_top_of_book``.
    """
    quotes: dict[str, dict[str, Any]] = {}
    per_book = _positive(timeout)
    if per_book is None or isinstance(products, (str, bytes)):
        return quotes
    deadline = time.monotonic() + QUOTE_BATCH_SECONDS
    for product in islice(products, MAX_QUOTE_PRODUCTS):
        product = product.strip().upper() if isinstance(product, str) else None
        symbol = _symbol(product)
        if symbol is None or product not in (symbol, f"{symbol}-USD"):
            continue
        product_id = f"{symbol}-USD"
        if product_id in quotes:
            continue
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        quotes[product_id] = fetch_top_of_book(
            product_id, http_get=http_get, timeout=min(per_book, remaining), now_ms=now_ms,
            depth_levels=depth_levels,
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
        "cycle_scan": deepcopy(scan) if usable_cycle_scan(scan, now=now) else None,
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
