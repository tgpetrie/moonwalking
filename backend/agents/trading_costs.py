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


def paper_sale(price, quantity, model):
    """Fees are charged on the slipped fill and proceeds are spendable cents."""
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
