"""One Decimal estimate of what a paper market sell would realise.

Shared by the Coinbase paper pilot replay (``scripts/coinbase_paper_exit.py``),
the depth replay (``scripts/coinbase_paper_depth.py``) and the cycle
strategist's ``GuardedDryRunExitExecutor``, so the three cannot price the same
sale differently.

The convention is the pilot's: walk the bids best first, apply slippage to the
volume-weighted price of that walk, then charge the fee on the slipped
proceeds. A single level that covers the size reduces to the pilot's
``bid * (1 - slip) * quantity * (1 - fee)``.

Nothing here touches a network or an account. It prices a hypothetical sale
from a book snapshot it is handed and never places, previews or routes an
order.
"""

from decimal import Decimal, DecimalException

FILLED = "filled"
INSUFFICIENT_BOOK_DEPTH = "insufficient_book_depth"
BPS = Decimal(10_000)


def to_decimal(value, label):
    """A finite Decimal from a string, int, Decimal or JSON float.

    Floats go through ``str`` so 174.8 stays 174.8 instead of its binary
    expansion. Booleans are refused: ``True`` is not a price.
    """
    if isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)):
        raise ValueError(f"{label} must be a number")
    try:
        number = Decimal(str(value)) if isinstance(value, float) else Decimal(value)
    except (DecimalException, ValueError) as error:
        raise ValueError(f"{label} must be a number") from error
    if not number.is_finite():
        raise ValueError(f"{label} must be finite")
    return number


def rate_from_bps(value):
    """A fee or slippage fraction from basis points in [0, 10000)."""
    try:
        bps = to_decimal(value, "rate")
    except ValueError as error:
        raise ValueError("rate must be finite basis points from 0 to under 10000") from error
    if not 0 <= bps < BPS:
        raise ValueError("rate must be finite basis points from 0 to under 10000")
    return bps / BPS


def book_levels(bids, *, best_ask=None):
    """Validate a bid ladder and return ``[(price, size), ...]`` as Decimals.

    Accepts Advanced Trade levels (``{"price": ..., "size": ...}``) and
    Exchange levels (``[price, size, ...]``). Prices must strictly descend and
    every price and size must be positive. With ``best_ask`` the book must not
    be crossed: the top bid has to sit below the best ask.
    """
    if not isinstance(bids, (list, tuple)) or not bids:
        raise ValueError("a book needs at least one bid level")
    levels = []
    for level in bids:
        if isinstance(level, dict):
            price, size = level.get("price"), level.get("size")
        elif isinstance(level, (list, tuple)) and len(level) >= 2:
            price, size = level[0], level[1]
        else:
            raise ValueError("each bid level needs a price and a size")
        try:
            price = to_decimal(price, "price")
        except ValueError as error:
            raise ValueError("bid level price must be positive and finite") from error
        if price <= 0:
            raise ValueError("bid level price must be positive and finite")
        try:
            size = to_decimal(size, "size")
        except ValueError as error:
            raise ValueError("bid level size must be positive and finite") from error
        if size <= 0:
            raise ValueError("bid level size must be positive and finite")
        if levels and price >= levels[-1][0]:
            raise ValueError("bid levels must descend in price")
        levels.append((price, size))
    if best_ask is not None:
        ask = to_decimal(best_ask, "best ask")
        if ask <= levels[0][0]:
            raise ValueError("book is crossed: the best ask is at or below the top bid")
    return levels


def estimate_sell_proceeds(levels, quantity, *, fee_rate, slippage_rate):
    """Price a market sell of ``quantity`` against validated bid ``levels``.

    ``fee_rate`` and ``slippage_rate`` are fractions (see ``rate_from_bps``).
    Returns a ``FILLED`` estimate, or an explicit ``INSUFFICIENT_BOOK_DEPTH``
    result with the shortfall and no proceeds: a partial fill is not what the
    position would realise, so it is never reported as such.
    """
    quantity = to_decimal(quantity, "quantity") if not isinstance(quantity, Decimal) else quantity
    if not quantity.is_finite() or quantity <= 0:
        raise ValueError("quantity must be positive and finite")
    fee, slip = Decimal(fee_rate), Decimal(slippage_rate)
    remaining = quantity
    gross = Decimal(0)
    consumed = 0
    for price, size in levels:
        if remaining <= 0:
            break
        taken = size if size < remaining else remaining
        gross += price * taken
        remaining -= taken
        consumed += 1
    top = levels[0][0]
    shared = {
        "requested_quantity": quantity,
        "levels_offered": len(levels),
        "levels_consumed": consumed,
        "book_quantity_offered": sum(size for _, size in levels),
        "top_bid_usd": top,
    }
    if remaining > 0:
        return {
            **shared,
            "status": INSUFFICIENT_BOOK_DEPTH,
            "fillable_quantity": quantity - remaining,
            "depth_shortfall_quantity": remaining,
            "fillable_gross_proceeds_usd": gross,
            "estimated_vwap_usd": None,
            "estimated_net_proceeds_usd": None,
        }
    vwap = gross / quantity
    sell_price = vwap * (1 - slip)
    slipped = sell_price * quantity
    return {
        **shared,
        "status": FILLED,
        "fillable_quantity": quantity,
        "depth_shortfall_quantity": Decimal(0),
        "gross_proceeds_usd": gross,
        "estimated_vwap_usd": vwap,
        "estimated_sell_price_usd": sell_price,
        "slippage_cost_usd": gross * slip,
        "fee_usd": slipped * fee,
        "estimated_net_proceeds_usd": slipped * (1 - fee),
        # How much worse the walk is than pricing everything at the top bid.
        "top_bid_only_gross_usd": top * quantity,
        "depth_cost_vs_top_bid_usd": top * quantity - gross,
    }


def sell_at_price(price, quantity, *, fee_rate, slippage_rate):
    """The same estimate for a single level that covers the whole size."""
    quantity = to_decimal(quantity, "quantity") if not isinstance(quantity, Decimal) else quantity
    return estimate_sell_proceeds(
        book_levels([(price, quantity)]), quantity, fee_rate=fee_rate, slippage_rate=slippage_rate
    )
