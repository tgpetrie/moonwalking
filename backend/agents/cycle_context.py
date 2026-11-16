"""Builds the cycle inputs that ``CycleStrategistAgent`` and smart alerts read.

Both consume the same three things: a ``scan_universe_cycles`` payload, the
held positions and the watchlist. Keeping the shape in one place lets the
local runner script and any backend caller hand agents identical context.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping


def _symbol(value: Any) -> str | None:
    text = str(value or "").strip().upper()
    return text.split("-")[0].split("/")[0] or None


def _positive(value: Any) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if out == out and out > 0 and out != float("inf") else None


def normalize_positions(rows: Iterable[Mapping[str, Any]] | None) -> list[dict]:
    """Keep rows with a symbol and a positive quantity, one per symbol (summed)."""
    merged: dict[str, dict] = {}
    for row in rows or []:
        if not isinstance(row, Mapping):
            continue
        symbol = _symbol(row.get("symbol") or row.get("product_id"))
        quantity = _positive(row.get("quantity") if "quantity" in row else row.get("size"))
        if not symbol or quantity is None:
            continue
        if symbol in merged:
            merged[symbol]["quantity"] += quantity
            continue
        clean = {"symbol": symbol, "product_id": f"{symbol}-USD", "quantity": quantity}
        for key in ("stop_price", "higher_low_floor", "cost_basis", "entry_price", "source"):
            if row.get(key) is not None:
                clean[key] = row[key]
        merged[symbol] = clean
    return [merged[symbol] for symbol in sorted(merged)]


def normalize_watchlist(symbols: Iterable[Any] | None) -> list[str]:
    out: list[str] = []
    for raw in symbols or []:
        symbol = _symbol(raw.get("symbol") if isinstance(raw, Mapping) else raw)
        if symbol and symbol.isalnum() and symbol not in out:
            out.append(symbol)
    return out


def build_cycle_context(
    scan: Mapping[str, Any] | None,
    *,
    positions: Iterable[Mapping[str, Any]] | None = None,
    watchlist: Iterable[Any] | None = None,
    quotes: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Context keys read by ``CycleStrategistAgent`` and ``evaluate_smart_alerts``.

    A scan that is still warming (no coins) is passed as ``None`` so agents
    skip the pass instead of reading an empty universe.
    """
    usable = (
        isinstance(scan, Mapping)
        and isinstance(scan.get("coins"), list)
        and bool(scan.get("coins"))
    )
    context: dict[str, Any] = {
        "cycle_scan": dict(scan) if usable else None,
        "positions": normalize_positions(positions),
        "watchlist": normalize_watchlist(watchlist),
    }
    if isinstance(quotes, Mapping) and quotes:
        context["quotes"] = dict(quotes)
    return context


def evaluate_smart_alerts(context: Mapping[str, Any], engine: Any) -> dict[str, Any]:
    """Run the smart alert rules over the context's cycle scan."""
    scan = context.get("cycle_scan")
    if not isinstance(scan, Mapping):
        return {"status": "skipped", "reason": "no_cycle_scan", "fired": []}
    fired = engine.evaluate(
        scan,
        positions=context.get("positions") or [],
        watchlist=context.get("watchlist") or [],
        now=context.get("now_ts"),
    )
    return {"status": "ok", "fired": fired}
