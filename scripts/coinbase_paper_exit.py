"""Compare independent Coinbase spot exit rules on an ordered quote tape."""

import argparse
from decimal import Decimal, DecimalException
import json
from pathlib import Path
import re


BPS = Decimal(10_000)
PERCENT = Decimal(100)
RULES = ("rebound_usd", "rebound_pct", "net_profit_pct")


def _number(record, field, *, allow_zero=False):
    value = record.get(field)
    if isinstance(value, bool) or not isinstance(value, (str, int, Decimal)):
        raise ValueError(f"{field} must be a decimal number")
    try:
        number = Decimal(value)
    except DecimalException as error:
        raise ValueError(f"{field} must be a decimal number") from error
    if not number.is_finite() or number < 0 or (not allow_zero and number == 0):
        minimum = "nonnegative" if allow_zero else "positive"
        raise ValueError(f"{field} must be finite and {minimum}")
    return number


def _mark(observed_at_ms, bid, low, low_observed_at_ms, quantity, cost, fee, slip):
    estimated_price = bid * (1 - slip)
    net = estimated_price * quantity * (1 - fee)
    rebound = (bid - low) * quantity
    return {
        "observed_at_ms": observed_at_ms,
        "bid_usd": bid,
        "observed_low_bid_usd": low,
        "low_observed_at_ms": low_observed_at_ms,
        "rebound_usd": rebound,
        "rebound_pct": PERCENT * (bid - low) / low,
        "estimated_sell_price_usd": estimated_price,
        "estimated_net_proceeds_usd": net,
        "estimated_pnl_usd": net - cost,
        "net_profit_pct": PERCENT * (net - cost) / cost,
    }


def simulate_exit(spec):
    """Return the first hypothetical exit per rule and the last hold mark."""
    if not isinstance(spec, dict):
        raise ValueError("scenario must be an object")
    product = spec.get("product_id")
    if not isinstance(product, str) or not re.fullmatch(r"[A-Z0-9]+-USD", product):
        raise ValueError("product_id must identify a USD spot pair")
    quantity = _number(spec, "quantity")
    cost = _number(spec, "entry_cost_usd")
    fee_bps = _number(spec, "exit_fee_bps", allow_zero=True)
    slip_bps = _number(spec, "slippage_bps", allow_zero=True)
    if max(fee_bps, slip_bps) >= BPS:
        raise ValueError("fee and slippage must be below 10000 basis points")
    fee, slip = fee_bps / BPS, slip_bps / BPS
    thresholds = spec.get("thresholds")
    if not isinstance(thresholds, dict) or set(thresholds) != set(RULES):
        raise ValueError(f"thresholds must contain exactly {', '.join(RULES)}")
    thresholds = {rule: _number(thresholds, rule) for rule in RULES}

    quotes = spec.get("quotes")
    if not isinstance(quotes, list) or not quotes:
        raise ValueError("quotes must contain at least one bid observation")
    exits = dict.fromkeys(RULES)
    previous_ms = -1
    low = None
    for quote in quotes:
        if not isinstance(quote, dict):
            raise ValueError("each quote must be an object")
        observed_at_ms = quote.get("observed_at_ms")
        if type(observed_at_ms) is not int or observed_at_ms <= previous_ms:
            raise ValueError("quote times must be nonnegative and strictly increasing")
        previous_ms = observed_at_ms
        bid = _number(quote, "bid_usd")
        if low is None or bid < low:
            low, low_observed_at_ms = bid, observed_at_ms
        mark = _mark(
            observed_at_ms, bid, low, low_observed_at_ms, quantity, cost, fee, slip
        )
        for rule in RULES:
            if exits[rule] is None and mark[rule] >= thresholds[rule]:
                exits[rule] = mark

    return {
        "mode": "paper",
        "product_id": product,
        "quantity": quantity,
        "entry_cost_usd": cost,
        "exit_fee_bps": fee_bps,
        "slippage_bps": slip_bps,
        "thresholds": thresholds,
        "first_hypothetical_exits": exits,
        "hold_last_quote": mark,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "scenario", type=Path, help="JSON file with the position and bids"
    )
    args = parser.parse_args()
    try:
        with args.scenario.open(encoding="utf-8-sig") as source:
            spec = json.load(source, parse_float=Decimal)
        result = simulate_exit(spec)
    except (OSError, ValueError, DecimalException) as error:
        parser.exit(2, f"{parser.prog}: {error}\n")
    print(json.dumps(result, default=str, indent=2))


if __name__ == "__main__":
    main()
