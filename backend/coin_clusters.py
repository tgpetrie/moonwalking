"""Narrative clusters for liquid Coinbase USD coins.

A hand-kept map used by the strategist's cluster heat guard: coins in one
cluster tend to fall together, so the guard limits how many of them, and how
much risk in them, are held at once. Edit freely: a coin missing from the map
is treated as its own cluster.

The groupings are rules of thumb, not a classification standard, and a coin
belongs to one cluster only even where it fits several.
"""

from __future__ import annotations

from typing import Any

__all__ = ["COIN_CLUSTERS", "cluster_for"]

_GROUPS = {
    "majors": ("BTC", "ETH"),
    "layer-1": (
        "SOL", "ADA", "AVAX", "DOT", "NEAR", "ATOM", "SUI", "APT", "SEI", "ALGO",
        "HBAR", "XTZ", "EGLD", "ICP", "KAS", "INJ", "TIA", "FLOW", "MINA", "EOS",
        "ETC", "KAVA", "CELO", "ROSE", "ZETA",
    ),
    "layer-2": ("ARB", "OP", "POL", "MATIC", "IMX", "STRK", "MNT", "ZK", "METIS", "LRC", "SKL", "BLAST"),
    "defi": (
        "UNI", "AAVE", "COMP", "MKR", "CRV", "SNX", "LDO", "SUSHI", "1INCH", "BAL",
        "YFI", "PENDLE", "JUP", "ENA", "MORPHO", "CVX", "DYDX", "RPL", "AERO", "ONDO",
    ),
    "oracle-data": ("LINK", "PYTH", "GRT", "API3", "BAND", "TRB"),
    "ai-compute": ("FET", "RENDER", "RNDR", "TAO", "AKT", "OCEAN", "AGIX", "AIOZ", "IO", "VIRTUAL", "ARKM", "GLM"),
    "meme": ("DOGE", "SHIB", "PEPE", "BONK", "WIF", "FLOKI", "MOG", "POPCAT", "TRUMP", "PENGU", "BRETT", "FARTCOIN"),
    "gaming-metaverse": ("SAND", "MANA", "AXS", "APE", "GALA", "ENJ", "ILV", "YGG", "PRIME", "SUPER", "BLUR"),
    "payments": ("XRP", "XLM", "LTC", "BCH", "XCN", "AMP"),
    "storage-infra": ("FIL", "AR", "STORJ", "ANKR", "HNT", "THETA", "LPT", "IOTX", "QNT"),
    "privacy": ("ZEC", "DASH", "XMR"),
}

COIN_CLUSTERS: dict[str, str] = {
    symbol: cluster for cluster, symbols in _GROUPS.items() for symbol in symbols
}


def cluster_for(symbol: Any) -> str | None:
    """The cluster of ``SYMBOL`` or ``SYMBOL-USD``, or ``None`` when unmapped."""
    if not isinstance(symbol, str):
        return None
    return COIN_CLUSTERS.get(symbol.strip().upper().removesuffix("-USD"))
