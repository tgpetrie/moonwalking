"""Explicit quote-currency costs for paper cycle decisions."""

import math
import os


def cost_model(fee_bps=0.0, slippage_bps=0.0, *, source="explicit_paper_assumption"):
    rates = []
    for value in (fee_bps, slippage_bps):
        if isinstance(value, bool):
            raise ValueError("Cost rates must be finite basis points from 0 to under 10000")
        rate = float(value)
        if not math.isfinite(rate) or not 0 <= rate < 10000:
            raise ValueError("Cost rates must be finite basis points from 0 to under 10000")
        rates.append(rate)
    return {"fee_bps": rates[0], "slippage_bps": rates[1], "source": source}


def configured_cost_model():
    return cost_model(
        os.environ.get("MW_CYCLE_FEE_BPS", "60"),
        os.environ.get("MW_CYCLE_SLIPPAGE_BPS", "10"),
    )


def _shared_sale(price, quantity, model):
    """The shared Decimal estimate for one covering level, or None if the
    inputs are not a positive, finite price and size."""
    try:
        from paper_fills import rate_from_bps, sell_at_price
    except ImportError:  # imported as backend.agents from the repository root
        from backend.paper_fills import rate_from_bps, sell_at_price
    from decimal import ROUND_DOWN, Decimal

    try:
        sale = sell_at_price(
            price,
            quantity,
            fee_rate=rate_from_bps(model["fee_bps"]),
            slippage_rate=rate_from_bps(model["slippage_bps"]),
        )
    except ValueError:
        return None
    net = sale["estimated_net_proceeds_usd"]
    cents = net.quantize(Decimal("0.01"), rounding=ROUND_DOWN) if net > 0 else Decimal(0)
    return {
        "fill_price": float(sale["estimated_sell_price_usd"]),
        "gross_proceeds_usd": float(sale["estimated_sell_price_usd"] * sale["requested_quantity"]),
        "fee_usd": float(sale["fee_usd"]),
        "slippage_usd": float(sale["slippage_cost_usd"]),
        "proceeds_usd": float(cents),
    }


def paper_sale(price, quantity, model):
    """Fees are charged on the slipped fill and proceeds are spendable cents.

    Priced by the shared Decimal estimate in ``paper_fills`` so the strategist
    and the paper pilot agree to the cent. Inputs that are not a positive,
    finite price and size keep the original float arithmetic.
    """
    shared = _shared_sale(price, quantity, model)
    if shared is not None:
        return shared
    fee = model["fee_bps"] / 10000
    slip = model["slippage_bps"] / 10000
    fill = price * (1 - slip)
    gross = fill * quantity
    fees = gross * fee
    # Import here to share the ledger's exact cent rounding.
    from .store import usdc_cents

    return {
        "fill_price": fill,
        "gross_proceeds_usd": gross,
        "fee_usd": fees,
        "slippage_usd": (price - fill) * quantity,
        "proceeds_usd": usdc_cents(gross - fees, round_down=True) / 100,
    }


def paper_buy(price, budget, model):
    """The budget includes the buy fee. Slippage changes the received quantity."""
    fill = price * (1 + model["slippage_bps"] / 10000)
    notional = budget / (1 + model["fee_bps"] / 10000)
    quantity = notional / fill
    return {
        "quantity": quantity,
        "fill_price": fill,
        "fee_usd": budget - notional,
        "slippage_usd": (fill - price) * quantity,
    }
