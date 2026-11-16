"""Builds the cycle inputs that ``CycleStrategistAgent`` and smart alerts read.

Both consume the same three things: a ``scan_universe_cycles`` payload, the
held positions and the watchlist. Keeping the shape in one place lets the
local runner script and any backend caller hand agents identical context.
"""

from __future__ import annotations

import math
import re
import time
from typing import Any, Iterable, Mapping


MAX_SCAN_AGE_SECONDS = 1800
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


def build_cycle_context(
    scan: Mapping[str, Any] | None,
    *,
    positions: Iterable[Mapping[str, Any]] | None = None,
    watchlist: Iterable[Any] | None = None,
    quotes: Mapping[str, Any] | None = None,
    now: float | None = None,
) -> dict[str, Any]:
    """Context keys read by ``CycleStrategistAgent`` and ``evaluate_smart_alerts``.

    A warming, refreshing or stale HTTP scan is passed as ``None`` so agents
    skip the pass, and structured per-coin evidence is preserved.
    """
    context: dict[str, Any] = {
        "cycle_scan": dict(scan) if usable_cycle_scan(scan, now=now) else None,
        "positions": normalize_positions(positions),
        "watchlist": normalize_watchlist(watchlist),
    }
    if isinstance(quotes, Mapping) and quotes:
        context["quotes"] = dict(quotes)
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
