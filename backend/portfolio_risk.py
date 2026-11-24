"""Combine existing sell plans with real holdings; never change the level math."""

import math
import re
from datetime import datetime

from entry_signal_intelligence import build_entry_read
from sell_side_intelligence import build_sell_plan


def number(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (ValueError, TypeError):
        return None


def timestamp(value):
    numeric = number(value)
    if numeric is not None:
        return numeric
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp()
    except (ValueError, TypeError):
        return 0


def normalize_holdings(holdings, *, positions):
    """Group multiple accounts for one asset without double-counting cards."""
    grouped = {}
    for holding in holdings:
        if holding.get("is_cash"):
            continue
        symbol = (
            str(holding.get("symbol") or holding.get("product_id") or "")
            .upper()
            .split("-")[0]
        )
        if not re.fullmatch(r"[A-Z0-9]{1,20}", symbol):
            continue
        qty = number(holding.get("quantity")) if positions else None
        if qty is not None and qty <= 0:
            continue
        price = number(holding.get("price_usd"))
        if symbol in grouped:
            prior = grouped[symbol]
            prior["quantity"] = (
                prior["quantity"] + qty
                if prior["quantity"] is not None and qty is not None
                else None
            )
        else:
            grouped[symbol] = {
                "product_id": f"{symbol}-USD",
                "symbol": symbol,
                "quantity": qty,
                "price_usd": price if price and price > 0 else None,
            }
    return list(grouped.values())


def build_risk_board(holdings, levels, contexts, *, source, quote_as_of, now):
    rows = []
    counts = {"high": 0, "watch": 0, "clear": 0, "unavailable": 0}
    entry_counts = {
        "breakout": 0,
        "entry_watch": 0,
        "pullback": 0,
        "extended": 0,
        "invalidated": 0,
        "clear": 0,
        "unavailable": 0,
    }
    amounts = []
    excluded = []
    breached = []
    fresh = 0 < quote_as_of <= now + 30 and now - quote_as_of <= 120
    for holding in holdings:
        symbol = holding["symbol"]
        price = holding["price_usd"]
        structure = levels.get(symbol)
        plan = build_sell_plan(
            product_id=holding["product_id"],
            current_price=price if fresh else None,
            levels=structure,
            signal_context=contexts.get(symbol),
        )
        if not fresh:
            plan["reason"] = (
                "A fresh quote is unavailable. Refresh when the price feed is current."
            )
        elif not plan["available"] and price:
            plan["reason"] = (
                "Not enough completed candle history yet, or history is still loading."
            )
        plan.update(generated_at=int(now), price_as_of=int(quote_as_of))
        if plan["available"] and structure and structure.get("chart"):
            plan["chart"] = {**structure["chart"], "product_id": holding["product_id"]}
        # The entry read uses the same quote, the same measured levels and the
        # same structural support the protection plan just published, so the two
        # reads on one card can never name different levels.
        entry = build_entry_read(
            product_id=holding["product_id"],
            current_price=price if fresh else None,
            levels=structure,
            signal_context=contexts.get(symbol),
            sell_plan=plan,
        )
        if not entry["available"] and not fresh:
            entry["reason"] = plan["reason"]
            entry["entry_signal"]["reasons"] = [plan["reason"]]
        entry.update(generated_at=int(now), price_as_of=int(quote_as_of))
        entry_status = entry["entry_signal"]["status"]
        entry_status = entry_status if entry_status in entry_counts else "unavailable"
        entry_counts[entry_status] += 1
        qty = holding["quantity"]
        amount = None
        distance = None
        resistance_distance = None
        is_breached = False
        if plan["available"]:
            stop = plan["stop"]["trigger_price"]
            distance = (price - stop) / price * 100
            resistance = plan["market_structure"].get("resistance")
            resistance_distance = (
                (resistance - price) / price * 100 if resistance else None
            )
            is_breached = price <= stop
            if source == "portfolio" and qty is not None and qty > 0:
                amount = qty * max(price - stop, 0)
                amounts.append(amount)
            if is_breached:
                breached.append(symbol)
        if amount is None and source == "portfolio":
            excluded.append(symbol)
        status = (
            plan.get("top_signal", {}).get("status")
            if plan["available"]
            else "unavailable"
        )
        status = status if status in counts else "unavailable"
        counts[status] += 1
        rows.append(
            {
                **holding,
                "plan": plan,
                "entry": entry,
                "status": status,
                "entry_status": entry_status,
                "market_value_usd": (
                    qty * price if qty is not None and price is not None else None
                ),
                "distance_to_stop_pct": distance,
                "distance_to_resistance_pct": resistance_distance,
                "capital_to_stop_usd": amount,
                "trigger_breached": is_breached,
            }
        )
    order = {"high": 0, "watch": 1, "clear": 2, "unavailable": 3}
    rows.sort(key=lambda row: (order[row["status"]], row["symbol"]))
    return {
        "status": "partial" if counts["unavailable"] else "live",
        "source": source,
        "updated_at": int(now),
        "quote_as_of": int(quote_as_of),
        "rows": rows,
        "summary": {
            "counts": counts,
            "entry_counts": entry_counts,
            "total": len(rows),
            "capital_to_stop_usd": sum(amounts) if amounts else None,
            "sized_plan_count": len(amounts),
            "excluded_symbols": excluded,
            "breached_symbols": breached,
        },
    }
