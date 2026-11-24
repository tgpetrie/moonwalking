"""Downside BTC beta and cluster concentration math for the strategist.

Pure and deterministic: no network, no disk, no clock.

- ``compute_downside_btc_beta`` measures how an asset moves against BTC, over
  the whole sample and on the days BTC fell.
- ``evaluate_cluster_and_beta_heat`` groups open positions and candidate
  entries by cluster and splits the candidates into accepted and suppressed.

The limits are rules of thumb and have not been tested against outcomes.
"""

from __future__ import annotations

import math
from typing import Any, Iterable, Mapping

__all__ = [
    "compute_downside_btc_beta",
    "evaluate_cluster_and_beta_heat",
    "beta_heat_multiplier",
    "SUPPRESSION_REASONS",
]

BETA_MIN, BETA_MAX = -2.0, 5.0
DRAWDOWN_MULTIPLIER_MAX = 10.0
# Betas at or below this add no extra heat; above it heat scales in proportion.
BETA_NEUTRAL = 1.25
SUPPRESSION_REASONS = (
    "risk_unavailable",
    "cluster_count_cap_exceeded",
    "cluster_heat_cap_exceeded",
    "beta_adjusted_heat_cap_exceeded",
)
_EPSILON = 1e-9


def _positive(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) and out > 0 else None


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _beta_and_correlation(pairs: list[tuple[float, float]]) -> tuple[float | None, float | None]:
    """(beta, correlation) of asset returns on BTC returns, or ``None`` with no BTC variance."""
    count = len(pairs)
    if count < 2:
        return None, None
    mean_a = sum(a for a, _ in pairs) / count
    mean_b = sum(b for _, b in pairs) / count
    cov = sum((a - mean_a) * (b - mean_b) for a, b in pairs)
    var_a = sum((a - mean_a) ** 2 for a, _ in pairs)
    var_b = sum((b - mean_b) ** 2 for _, b in pairs)
    if var_b <= 1e-18:
        return None, None
    beta = _clamp(cov / var_b, BETA_MIN, BETA_MAX)
    correlation = None if var_a <= 1e-18 else _clamp(cov / math.sqrt(var_a * var_b), -1.0, 1.0)
    return beta, correlation


def _max_drawdown(closes: list[float]) -> float:
    peak, worst = 0.0, 0.0
    for close in closes:
        peak = max(peak, close)
        worst = max(worst, (peak - close) / peak)
    return worst


def compute_downside_btc_beta(
    asset_closes: Iterable[Any],
    btc_closes: Iterable[Any],
    *,
    min_down_days: int = 10,
) -> dict[str, Any]:
    """Full-sample and downside beta of an asset against BTC from daily closes.

    The two series are oldest first and aligned at their ends: the last close
    of each is the same day, and the longer one is cut to the shorter. A day
    counts only if both closes on it and on the day before are positive
    numbers. Betas are clamped to -2..5 and the drawdown multiplier to 0..10.

    ``downside_beta`` is the beta over days when BTC's return was below zero
    and is ``None`` with fewer than ``min_down_days`` of them.
    ``effective_downside_beta`` is the downside beta when available, else the
    full-sample beta, else 1.0, so a caller always has a number to size with.
    """
    if isinstance(min_down_days, bool) or not isinstance(min_down_days, int) or min_down_days < 2:
        raise ValueError("min_down_days must be an integer of at least 2")
    asset, btc = list(asset_closes or []), list(btc_closes or [])
    size = min(len(asset), len(btc))
    asset, btc = asset[len(asset) - size:], btc[len(btc) - size:]
    pairs: list[tuple[float, float]] = []
    clean_asset: list[float] = []
    clean_btc: list[float] = []
    prior: tuple[float, float] | None = None
    for raw_a, raw_b in zip(asset, btc):
        a, b = _positive(raw_a), _positive(raw_b)
        if a is None or b is None:
            prior = None
            continue
        clean_asset.append(a)
        clean_btc.append(b)
        if prior is not None:
            pairs.append((a / prior[0] - 1.0, b / prior[1] - 1.0))
        prior = (a, b)

    down = [pair for pair in pairs if pair[1] < 0]
    result: dict[str, Any] = {
        "available": False,
        "observations": len(pairs),
        "down_days": len(down),
        "beta": None,
        "correlation": None,
        "downside_beta": None,
        "downside_correlation": None,
        "downside_available": False,
        "relative_drawdown_multiplier": None,
        "effective_downside_beta": 1.0,
    }
    beta, correlation = _beta_and_correlation(pairs)
    if beta is None:
        result["reason"] = "not_enough_history" if len(pairs) < 2 else "btc_did_not_move"
        return result
    result.update(available=True, beta=round(beta, 4), effective_downside_beta=round(beta, 4))
    if correlation is not None:
        result["correlation"] = round(correlation, 4)
    if len(down) >= min_down_days:
        down_beta, down_correlation = _beta_and_correlation(down)
        if down_beta is not None:
            result.update(
                downside_beta=round(down_beta, 4),
                downside_available=True,
                effective_downside_beta=round(down_beta, 4),
            )
            if down_correlation is not None:
                result["downside_correlation"] = round(down_correlation, 4)
    btc_drawdown = _max_drawdown(clean_btc)
    if btc_drawdown > 1e-12:
        result["relative_drawdown_multiplier"] = round(
            _clamp(_max_drawdown(clean_asset) / btc_drawdown, 0.0, DRAWDOWN_MULTIPLIER_MAX), 4
        )
    return result


def beta_heat_multiplier(downside_beta: Any) -> float:
    """``max(1, beta / 1.25)``; an unreadable beta counts as 1."""
    try:
        beta = float(downside_beta)
    except (TypeError, ValueError):
        return 1.0
    if isinstance(downside_beta, bool) or not math.isfinite(beta):
        return 1.0
    return max(1.0, _clamp(beta, BETA_MIN, BETA_MAX) / BETA_NEUTRAL)


def _symbol(item: Mapping[str, Any]) -> str:
    raw = item.get("symbol") or item.get("product_id") or ""
    return str(raw).strip().upper().split("-")[0]


def _cluster(item: Mapping[str, Any], symbol: str) -> str:
    for key in ("category_id", "cluster", "narrative_cluster", "sector"):
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip().lower()
    # A coin with no known cluster stands alone rather than joining one bucket.
    return f"uncategorized:{symbol or 'unknown'}"


def _risk_usd(item: Mapping[str, Any], equity_usd: float) -> float | None:
    """Risk in USD from the first of: risk_usd, risk_pct, quantity or notional to the stop."""
    sizing = item.get("sizing") if isinstance(item.get("sizing"), Mapping) else {}
    for source in (item, sizing):
        risk = _positive(source.get("risk_usd"))
        if risk is not None:
            return risk
    for source in (item, sizing):
        pct = _positive(source.get("risk_pct"))
        if pct is not None:
            return pct / 100.0 * equity_usd
    price = _positive(item.get("entry_price")) or _positive(item.get("reference_price")) or _positive(item.get("price"))
    stop = _positive(item.get("stop_price"))
    if price is None or stop is None or stop >= price:
        return None
    quantity = _positive(item.get("quantity"))
    if quantity is not None:
        return quantity * (price - stop)
    notional = (
        _positive(item.get("notional_usd"))
        or _positive(sizing.get("suggested_notional_usd"))
        or _positive(sizing.get("notional_usd"))
    )
    return None if notional is None else notional * (price - stop) / price


def _measure(item: Any, equity_usd: float) -> dict[str, Any] | None:
    if not isinstance(item, Mapping):
        return None
    symbol = _symbol(item)
    risk = _risk_usd(item, equity_usd)
    if risk is None:
        return {"symbol": symbol, "cluster": _cluster(item, symbol), "risk_usd": None}
    multiplier = beta_heat_multiplier(item.get("downside_beta", 1.0))
    risk_pct = risk / equity_usd * 100.0
    return {
        "symbol": symbol,
        "cluster": _cluster(item, symbol),
        "risk_usd": risk,
        "risk_pct": risk_pct,
        "beta_multiplier": multiplier,
        "beta_adjusted_risk_pct": risk_pct * multiplier,
    }


def evaluate_cluster_and_beta_heat(
    existing_positions: Iterable[Any] | None,
    candidate_proposals: Iterable[Any] | None,
    *,
    equity_usd: float,
    max_total_heat_pct: float = 5.0,
    max_cluster_heat_pct: float = 2.0,
    max_positions_per_cluster: int = 2,
) -> dict[str, Any]:
    """Split candidate entries into accepted and suppressed by cluster and beta heat.

    Each item is a mapping with ``symbol`` (or ``product_id``), a cluster in
    ``category_id`` (or ``cluster`` / ``narrative_cluster`` / ``sector``), an
    optional ``downside_beta`` and a risk given as ``risk_usd``, ``risk_pct``
    or a size with ``stop_price``. Open positions whose risk cannot be read
    still count toward their cluster's coin count but add no heat.

    Candidates are taken in the order given, so pass the best first. Each is
    checked against, in order: the number of distinct coins in its cluster,
    the cluster's raw risk, and the portfolio's beta-adjusted risk
    (``risk_pct * max(1, downside_beta / 1.25)``). An accepted candidate counts
    against the ones after it. Returned proposals are copies with a
    ``cluster_guard`` block; suppressed ones also carry ``suppression_reason``.
    """
    equity = _positive(equity_usd)
    limits = [_positive(max_total_heat_pct), _positive(max_cluster_heat_pct)]
    if equity is None or None in limits:
        raise ValueError("equity_usd and the heat caps must be positive numbers")
    if isinstance(max_positions_per_cluster, bool) or not isinstance(max_positions_per_cluster, int) or max_positions_per_cluster < 1:
        raise ValueError("max_positions_per_cluster must be a positive integer")
    total_cap, cluster_cap = limits

    clusters: dict[str, dict[str, Any]] = {}

    def bucket(name: str) -> dict[str, Any]:
        return clusters.setdefault(
            name, {"symbols": [], "risk_usd": 0.0, "risk_pct": 0.0, "beta_adjusted_risk_pct": 0.0}
        )

    def add(measure: Mapping[str, Any]) -> None:
        entry = bucket(measure["cluster"])
        if measure["symbol"] and measure["symbol"] not in entry["symbols"]:
            entry["symbols"].append(measure["symbol"])
        if measure["risk_usd"] is not None:
            entry["risk_usd"] += measure["risk_usd"]
            entry["risk_pct"] += measure["risk_pct"]
            entry["beta_adjusted_risk_pct"] += measure["beta_adjusted_risk_pct"]

    unreadable_positions = []
    for position in existing_positions or []:
        measure = _measure(position, equity)
        if measure is None:
            continue
        if measure["risk_usd"] is None:
            unreadable_positions.append(measure["symbol"])
        add(measure)

    def totals() -> tuple[float, float]:
        return (
            sum(entry["risk_pct"] for entry in clusters.values()),
            sum(entry["beta_adjusted_risk_pct"] for entry in clusters.values()),
        )

    existing_raw, existing_adjusted = totals()
    accepted: list[dict[str, Any]] = []
    suppressed: list[dict[str, Any]] = []
    for proposal in candidate_proposals or []:
        measure = _measure(proposal, equity)
        if measure is None:
            continue
        reason = None
        if measure["risk_usd"] is None:
            reason = "risk_unavailable"
        else:
            entry = clusters.get(measure["cluster"]) or {"symbols": [], "risk_pct": 0.0}
            _, adjusted_total = totals()
            if measure["symbol"] not in entry["symbols"] and len(entry["symbols"]) >= max_positions_per_cluster:
                reason = "cluster_count_cap_exceeded"
            elif entry["risk_pct"] + measure["risk_pct"] > cluster_cap + _EPSILON:
                reason = "cluster_heat_cap_exceeded"
            elif adjusted_total + measure["beta_adjusted_risk_pct"] > total_cap + _EPSILON:
                reason = "beta_adjusted_heat_cap_exceeded"
        evidence = {
            key: round(value, 2 if key == "risk_usd" else 4) if isinstance(value, float) else value
            for key, value in measure.items()
        }
        copy = {**proposal, "cluster_guard": evidence}
        if reason is None:
            add(measure)
            accepted.append(copy)
        else:
            copy["suppression_reason"] = reason
            copy["cluster_guard"]["suppression_reason"] = reason
            suppressed.append(copy)

    raw_total, adjusted_total = totals()
    return {
        "accepted_proposals": accepted,
        "suppressed_proposals": suppressed,
        "clusters": {
            name: {
                "symbols": list(entry["symbols"]),
                "position_count": len(entry["symbols"]),
                "risk_usd": round(entry["risk_usd"], 2),
                "risk_pct": round(entry["risk_pct"], 4),
                "beta_adjusted_risk_pct": round(entry["beta_adjusted_risk_pct"], 4),
            }
            for name, entry in sorted(clusters.items())
        },
        "existing_risk_pct": round(existing_raw, 4),
        "existing_beta_adjusted_risk_pct": round(existing_adjusted, 4),
        "total_risk_pct": round(raw_total, 4),
        "total_beta_adjusted_risk_pct": round(adjusted_total, 4),
        "positions_without_risk": unreadable_positions,
        "limits": {
            "equity_usd": equity,
            "max_total_heat_pct": total_cap,
            "max_cluster_heat_pct": cluster_cap,
            "max_positions_per_cluster": max_positions_per_cluster,
            "beta_neutral": BETA_NEUTRAL,
        },
        "outcome_validated": False,
    }
