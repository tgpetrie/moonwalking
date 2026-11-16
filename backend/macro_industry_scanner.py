"""Industry liquidity gate and multi-coin cycle scanner.

Pure and deterministic; this module does no network or disk I/O. Callers pass
in multi-year daily candles keyed by Coinbase product id.

- ``build_alt_index`` chains an equal-weight basket of liquid altcoins into
  one daily series, ``ALT_INDEX_3Y``. It stands in for TOTAL3 (the altcoin
  market excluding BTC and ETH). It is a proxy: the basket is equal-weight,
  not market-cap weighted, and holds only the members supplied.
- ``macro_industry_regime`` reads BTC, ETH and that index with
  ``chart_structure.multi_year_context`` and names one of four liquidity
  rotation stages plus a three-state gate.
- ``scan_universe_cycles`` reads every coin supplied, measures breadth across
  them and sorts them into four cycle buckets.

The stages, gate and buckets are descriptive and have not been outcome tested.
"""

from __future__ import annotations

import logging
import math
from typing import Any

__all__ = [
    "ALT_INDEX_NAME",
    "ALT_INDEX_MEMBERS",
    "MAJORS",
    "STAGES",
    "BUCKETS",
    "build_alt_index",
    "macro_industry_regime",
    "cycle_row",
    "universe_breadth",
    "scan_universe_cycles",
]

DAY = 86400
ALT_INDEX_NAME = "ALT_INDEX_3Y"
ALT_INDEX_WINDOW_DAYS = 1096
ALT_INDEX_MIN_MEMBERS = 3
MAJORS = ("BTC-USD", "ETH-USD")
# Liquid altcoins with long Coinbase histories. Members with no history
# supplied are skipped; the read names the members it actually used.
ALT_INDEX_MEMBERS = (
    "SOL-USD",
    "XRP-USD",
    "ADA-USD",
    "DOGE-USD",
    "AVAX-USD",
    "LINK-USD",
    "DOT-USD",
    "LTC-USD",
    "UNI-USD",
    "ATOM-USD",
    "NEAR-USD",
    "AAVE-USD",
)

STAGES = {
    "stage_1_macro_compression": (1, "Stage 1 · Macro compression"),
    "stage_2_btc_majors_lead": (2, "Stage 2 · BTC and majors lead"),
    "stage_3_alt_index_breakout": (3, "Stage 3 · Alt index breakout"),
    "stage_4_alt_season_expansion": (4, "Stage 4 · Alt-season expansion"),
}
GATES = {
    "risk_on_aligned": "Risk-on aligned",
    "neutral_chop": "Neutral chop",
    "risk_off_headwind": "Risk-off headwind",
}
BUCKETS = {
    "deep_accumulation_exhaustion": "Deep accumulation · exhaustion",
    "low_confirmation_breakout": "Low-confirmation breakout",
    "growth_expansion_ride": "Growth expansion",
    "rollover_profit_zone": "Rollover zone",
}
# Stage 3-4 with fewer than this share of coins above their 50-week average
# is not broad enough to call aligned.
BREADTH_ALIGNED_MIN_PCT = 35.0
DEEP_ACCUMULATION_MIN_STREAK = 12
BREAKOUT_MAX_RECOVERED_PCT = 50.0


def _structure():
    try:
        import chart_structure
    except ImportError:
        from backend import chart_structure
    return chart_structure


def _clean(candles: list[list[Any]] | None) -> dict[int, tuple[float, ...]]:
    """Valid daily bars by timestamp."""
    out: dict[int, tuple[float, ...]] = {}
    for bar in candles or []:
        if not isinstance(bar, (list, tuple)) or len(bar) < 6:
            continue
        try:
            ts, low, high, open_, close, volume = (float(bar[i]) for i in range(6))
        except (TypeError, ValueError):
            continue
        if not all(math.isfinite(v) for v in (ts, low, high, open_, close, volume)):
            continue
        if not 0 <= ts < 253402214400 or ts % DAY or low <= 0 or volume < 0 or not low <= min(open_, close) <= max(open_, close) <= high:
            continue
        out[int(ts)] = (ts, low, high, open_, close, volume)
    return out


# ─── altcoin index ────────────────────────────────────────────────────────────


def build_alt_index(
    histories: dict[str, list[list[Any]]],
    members: tuple[str, ...] | list[str] | None = None,
    *,
    window_days: int = ALT_INDEX_WINDOW_DAYS,
) -> dict[str, Any]:
    """Equal-weight altcoin index as daily candles, oldest first, base 100.

    Each day's move is the average log move of the members that traded on
    both that day and the day before, so a coin listed part-way through joins
    without a jump. The index open, high and low are the same average applied
    to each member's open, high and low against its prior close.
    """
    wanted = [m for m in (ALT_INDEX_MEMBERS if members is None else members) if m not in MAJORS]
    series = {m: _clean(histories.get(m)) for m in wanted}
    series = {m: bars for m, bars in series.items() if len(bars) >= 2}
    if len(series) < ALT_INDEX_MIN_MEMBERS and members is None:
        # Too few of the usual members: use whatever altcoins were supplied.
        series = {
            m: bars
            for m in sorted(histories)
            if m not in MAJORS and len(bars := _clean(histories[m])) >= 2
        }
    if len(series) < ALT_INDEX_MIN_MEMBERS:
        return {
            "available": False,
            "name": ALT_INDEX_NAME,
            "reason": "too_few_members",
            "members": sorted(series),
        }
    last = max(max(bars) for bars in series.values())
    first = last - (window_days - 1) * DAY
    days = sorted({ts for bars in series.values() for ts in bars if ts >= first})
    level, candles, smallest = 100.0, [], None
    contributing = set()
    for ts in days:
        moves = {}
        for member, bars in series.items():
            bar, prior = bars.get(ts), bars.get(ts - DAY)
            if bar is None or prior is None:
                continue
            base = prior[4]
            log_base = math.log(base)
            moves[member] = (
                math.log(bar[1]) - log_base,
                math.log(bar[2]) - log_base,
                math.log(bar[3]) - log_base,
                math.log(bar[4]) - log_base,
                bar[4] * bar[5],
            )
        if len(moves) < ALT_INDEX_MIN_MEMBERS:
            continue
        count = len(moves)
        contributing.update(moves)
        smallest = count if smallest is None else min(smallest, count)
        low, high, open_, close = (
            level * math.exp(sum(m[k] for m in moves.values()) / count) for k in range(4)
        )
        candles.append([float(ts), low, high, open_, close, sum(m[4] for m in moves.values())])
        level = close
    if len(candles) < 2:
        return {
            "available": False,
            "name": ALT_INDEX_NAME,
            "reason": "no_overlapping_history",
            "members": sorted(series),
        }
    return {
        "available": True,
        "name": ALT_INDEX_NAME,
        "members": sorted(contributing),
        "member_count": len(contributing),
        "min_members_on_a_day": smallest,
        "candles": candles,
        "bars": len(candles),
        "first_timestamp": candles[0][0],
        "last_timestamp": candles[-1][0],
        "method": (
            "equal-weight average of member log moves, chained from 100; a "
            "proxy for TOTAL3, not market-cap weighted"
        ),
    }


# ─── stage and gate ───────────────────────────────────────────────────────────


def _lead(context: dict[str, Any] | None) -> dict[str, Any]:
    """Where one series stands: compressed, breaking out or expanding."""
    if not context or not context.get("available"):
        return {"available": False}
    regimes = context.get("rsi_regimes") or {}
    weekly = (regimes.get("1w") or {}).get("value")
    monthly = (regimes.get("1m") or {}).get("value")
    ladder = context.get("weekly_sma_ladder") or {}
    price = context.get("current_price")

    def above(key: str) -> bool | None:
        level = ladder.get(key)
        return None if level is None or price is None else bool(price > level)

    above_50, above_100 = above("sma_50w"), above("sma_100w")
    macd_up = bool((context.get("macd_signals") or {}).get("weekly_macd_above_signal"))
    weekly_regime = (regimes.get("1w") or {}).get("regime")
    expanding = weekly_regime == "growth_expansion" and above_50 is not False
    return {
        "available": weekly is not None,
        "weekly_rsi": weekly,
        "weekly_rsi_regime": weekly_regime,
        "monthly_rsi": monthly,
        "above_50w_sma": above_50,
        "above_100w_sma": above_100,
        "weekly_macd_above_signal": macd_up,
        "compressed": weekly_regime == "oversold_compression",
        "expanding": bool(expanding),
        "breaking_out": bool(expanding or (above_50 and macd_up)),
        "strong_expansion": bool(
            expanding
            and monthly is not None and monthly > 50
            and above_50 is True and above_100 is True
        ),
        "pct_from_cycle_high": context.get("pct_from_cycle_high"),
    }


def _stage(btc: dict[str, Any], eth: dict[str, Any], alt: dict[str, Any]) -> tuple[str, list[str]]:
    if alt.get("strong_expansion") and not btc.get("compressed"):
        return "stage_4_alt_season_expansion", [
            "The altcoin index has weekly RSI above 60 and trades above its 50-week and 100-week averages.",
        ]
    if alt.get("breaking_out"):
        return "stage_3_alt_index_breakout", [
            "The altcoin index is back above its 50-week average with weekly MACD above its signal line, or has weekly RSI above 60.",
        ]
    if btc.get("expanding") or (btc.get("breaking_out") and eth.get("breaking_out")):
        return "stage_2_btc_majors_lead", [
            "BTC and the majors are leading while the altcoin index has not broken out.",
        ]
    return "stage_1_macro_compression", [
        "Neither the majors nor the altcoin index is in an expansion.",
    ]


def _gate(stage: str, btc: dict[str, Any], breadth: dict[str, Any] | None) -> tuple[str, str]:
    above = ((breadth or {}).get("pct_above_50w_sma") or {}).get("pct")
    if stage in {"stage_3_alt_index_breakout", "stage_4_alt_season_expansion"}:
        if above is None:
            return "neutral_chop", "The index has broken out, but breadth is unavailable."
        if above < BREADTH_ALIGNED_MIN_PCT:
            return "neutral_chop", (
                f"The index has broken out, but only {above:.0f}% of scanned coins "
                "are above their 50-week average."
            )
        return "risk_on_aligned", "The altcoin index has broken out and breadth agrees."
    if stage == "stage_2_btc_majors_lead":
        return "neutral_chop", "Majors lead; altcoin liquidity has not rotated yet."
    weak_btc = btc.get("compressed") or (
        btc.get("above_50w_sma") is False and not btc.get("weekly_macd_above_signal")
    )
    if weak_btc:
        return "risk_off_headwind", (
            "BTC weekly momentum is weak, which works against altcoin recoveries."
        )
    return "neutral_chop", "No expansion yet, and BTC is not breaking down."


def macro_industry_regime(
    histories: dict[str, list[list[Any]]],
    breadth: dict[str, Any] | None = None,
    *,
    members: tuple[str, ...] | list[str] | None = None,
) -> dict[str, Any]:
    """Four-stage liquidity rotation read from BTC, ETH and the altcoin index."""
    structure = _structure()
    index = build_alt_index(histories, members)
    summary = {k: v for k, v in index.items() if k != "candles"}
    if not histories.get("BTC-USD"):
        return {"available": False, "reason": "btc_history_unavailable", "alt_index": summary}
    if not index["available"]:
        return {"available": False, "reason": "alt_index_unavailable", "alt_index": summary}
    btc = _lead(structure.multi_year_context(histories.get("BTC-USD")))
    eth = _lead(structure.multi_year_context(histories.get("ETH-USD")))
    alt = _lead(structure.multi_year_context(index["candles"]))
    if not btc.get("available") or not alt.get("available"):
        return {"available": False, "reason": "not_enough_weekly_history", "alt_index": summary}
    stage, reasons = _stage(btc, eth, alt)
    gate, gate_reason = _gate(stage, btc, breadth)
    number, label = STAGES[stage]
    return {
        "available": True,
        "liquidity_rotation_stage": stage,
        "stage_number": number,
        "stage_label": label,
        "macro_regime_gate": gate,
        "gate_label": GATES[gate],
        "active_target_tier": structure.TARGET_TIER_BY_STAGE[stage],
        "reasons": reasons + [gate_reason],
        "components": {"BTC-USD": btc, "ETH-USD": eth, ALT_INDEX_NAME: alt},
        "alt_index": summary,
        "breadth": breadth,
        "outcome_validated": False,
    }


# ─── per-coin rows, breadth and buckets ───────────────────────────────────────


def _bucket(context: dict[str, Any], top: dict[str, Any], lead: dict[str, Any]) -> tuple[str | None, float]:
    """One bucket per coin, checked from latest cycle stage to earliest."""
    signals = context.get("macd_signals") or {}
    exhaustion = context.get("monthly_cycle_exhaustion") or {}
    stoch = context.get("weekly_stoch_rsi") or {}
    drawdown = context.get("macro_drawdown") or {}
    box = context.get("rollover_target_box") or {}
    breakout = top.get("confirmation_breakout") or {}
    recovered = drawdown.get("recovered_pct")
    streak = exhaustion.get("monthly_bearish_streak") or 0

    if box.get("available") and box.get("price_position") in {"inside", "above"}:
        return "rollover_profit_zone", float(recovered or 0.0)
    if (
        breakout.get("broken")
        and breakout.get("recent")
        and breakout.get("holding_above")
        and drawdown.get("available")
        and (recovered is None or recovered < BREAKOUT_MAX_RECOVERED_PCT)
    ):
        score = 30.0 - float(breakout.get("bars_since_break") or 0)
        return "low_confirmation_breakout", score + 3.0 * bool(
            signals.get("weekly_macd_bullish_cross")
        )
    # A coin already in a weekly expansion is past accumulation, however long
    # its monthly streak still reads.
    if (
        top.get("in_accumulation_box")
        and not lead.get("expanding")
        and (
            exhaustion.get("multi_year_oversold_exhaustion")
            or lead.get("weekly_rsi_regime") == "oversold_compression"
            or streak >= DEEP_ACCUMULATION_MIN_STREAK
        )
    ):
        score = (
            float(streak)
            + 5.0 * bool(exhaustion.get("multi_year_oversold_exhaustion"))
            + 3.0 * bool(signals.get("macro_bullish_divergence"))
            + 2.0 * bool(signals.get("daily_macd_kiss"))
            + 2.0 * (stoch.get("direction") == "oversold_turn_up")
            + 1.0 * bool((top.get("cycle_pattern") or {}).get("double_bottom"))
        )
        return "deep_accumulation_exhaustion", score
    if lead.get("expanding"):
        return "growth_expansion_ride", float(lead.get("weekly_rsi") or 0.0)
    return None, 0.0


def cycle_row(product_id: str, candles: list[list[Any]] | None) -> dict[str, Any]:
    """One coin's scan summary and the structured evidence used downstream."""
    structure = _structure()
    symbol = str(product_id).upper().removesuffix("-USD")
    context = structure.multi_year_context(candles)
    if not context.get("available") or not context.get("is_multi_year"):
        return {
            "symbol": symbol,
            "product_id": product_id,
            "available": False,
            "reason": "not_enough_daily_history",
            "candle_count": context.get("candle_count", 0),
        }
    price = context["current_price"]
    top = structure.top_down_confluence(context, {}, price)
    lead = _lead(context)
    bucket, score = _bucket(context, top, lead)
    signals = context.get("macd_signals") or {}
    exhaustion = context.get("monthly_cycle_exhaustion") or {}
    stoch = context.get("weekly_stoch_rsi") or {}
    daily = context.get("daily_structure") or {}
    breakout = top.get("confirmation_breakout") or {}
    pivot = top.get("low_confirmation_pivot") or daily.get("low_confirmation_pivot")
    stop = top.get("accumulation_invalidation_stop")
    box = context.get("rollover_target_box") or {}
    extension = context.get("full_extension_targets") or {}
    extension_levels = [
        value for value in (extension.get("levels") or {}).values()
        if isinstance(value, (int, float)) and value > 0
    ] if extension.get("available") else []
    support = context.get("log_fib_retracements") or {}
    return {
        "symbol": symbol,
        "product_id": product_id,
        "available": True,
        "price": price,
        "bucket": bucket,
        "bucket_label": BUCKETS.get(bucket),
        "score": round(score, 2),
        "weekly_rsi": lead.get("weekly_rsi"),
        "multi_year_context": {
            key: context[key]
            for key in (
                "rsi_regimes",
                "weekly_stoch_rsi",
                "weekly_sma_ladder",
                "monthly_cycle_exhaustion",
                "macd_signals",
                "daily_structure",
            )
            if key in context
        },
        "weekly_rsi_regime": lead.get("weekly_rsi_regime"),
        "monthly_rsi": lead.get("monthly_rsi"),
        "weekly_stoch_direction": stoch.get("direction"),
        "monthly_bearish_streak": exhaustion.get("monthly_bearish_streak"),
        "multi_year_oversold_exhaustion": exhaustion.get("multi_year_oversold_exhaustion")
        if exhaustion.get("available") and exhaustion.get("histogram_shrinking") is not None else None,
        "above_50w_sma": lead.get("above_50w_sma"),
        "pct_from_cycle_high": context.get("pct_from_cycle_high"),
        "at_multi_year_support": bool(top.get("at_multi_year_support")),
        "cycle_pattern": (top.get("cycle_pattern") or {}).get("kind"),
        "low_confirmation_pivot": {
            "price": pivot["price"],
            "distance_pct": pivot.get("distance_pct"),
            "at_support": bool(top.get("low_confirmation_pivot")),
        }
        if pivot
        else None,
        "breaking_confirmation_pivot": bool(
            breakout.get("broken") and breakout.get("recent") and breakout.get("holding_above")
        ) if breakout.get("pivot_price") is not None else None,
        "accumulation_invalidation_stop": {
            "stop_price": stop["stop_price"],
            "stop_distance_pct": stop["stop_distance_pct"],
        }
        if stop
        else None,
        "daily_macd_kiss": signals.get("daily_macd_kiss") if (signals.get("1d") or {}).get("histogram") is not None else None,
        "daily_bullish_divergence": signals.get("daily_bullish_divergence"),
        "weekly_macd_bullish_cross": signals.get("weekly_macd_bullish_cross") if (signals.get("1w") or {}).get("previous_histogram") is not None else None,
        "macro_bullish_divergence": bool(signals.get("macro_bullish_divergence")),
        "rollover_target_box": {"low": box["low"], "high": box["high"]}
        if box.get("available")
        else None,
        "fib_confluence_clusters": len(context.get("fib_confluence_clusters") or []),
        # Levels the strategist sizes against: the log-Fib support box under
        # the cycle high, cluster midpoints, the cycle low and the far targets.
        "support_levels": {
            ratio: support[ratio] for ratio in ("0.618", "0.702", "0.786") if support.get(ratio)
        } or None,
        "fib_cluster_mids": [
            cluster["mid"] for cluster in context.get("fib_confluence_clusters") or []
        ],
        "cycle_low": (context.get("cycle_low") or {}).get("price"),
        "full_extension_targets": {"low": min(extension_levels), "high": max(extension_levels)}
        if extension_levels
        else None,
        "active_target_tier": top.get("active_target_tier"),
        "_tiers": {
            tier: bool((top.get(tier) or {}).get("available"))
            for tier in ("rollover_target_box", "full_extension_targets")
        },
    }


def _share(rows: list[dict[str, Any]], known, hit) -> dict[str, Any]:
    pool = [row for row in rows if known(row)]
    count = sum(1 for row in pool if hit(row))
    return {
        "pct": round(count / len(pool) * 100.0, 1) if pool else None,
        "count": count,
        "of": len(pool),
    }


def universe_breadth(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Share of scanned coins in each state. ``of`` is the coins that could be read."""
    usable = [row for row in rows if row.get("available")]
    return {
        "pct_monthly_exhausted": _share(
            usable,
            lambda r: r.get("monthly_bearish_streak") is not None
            and r.get("multi_year_oversold_exhaustion") is not None,
            lambda r: r.get("multi_year_oversold_exhaustion"),
        ),
        "pct_weekly_rsi_above_60": _share(
            usable,
            lambda r: r.get("weekly_rsi") is not None,
            lambda r: (
                r["weekly_rsi_regime"] == "growth_expansion"
                if "weekly_rsi_regime" in r else r["weekly_rsi"] > 60
            ),
        ),
        "pct_above_50w_sma": _share(
            usable,
            lambda r: r.get("above_50w_sma") is not None,
            lambda r: r["above_50w_sma"],
        ),
        "pct_breaking_confirmation_pivot": _share(
            usable, lambda r: r.get("breaking_confirmation_pivot") is not None,
            lambda r: r["breaking_confirmation_pivot"],
        ),
        "coins": len(usable),
    }


def scan_universe_cycles(
    histories: dict[str, list[list[Any]]],
    *,
    members: tuple[str, ...] | list[str] | None = None,
    breadth_products: set[str] | frozenset[str] | None = None,
) -> dict[str, Any]:
    """Rank all rows; optionally constrain industry gate breadth to a fixed universe."""
    rows = []
    for product_id in sorted(histories):
        try:
            rows.append(cycle_row(product_id, histories[product_id]))
        except Exception:  # one bad series must not sink the scan
            logging.exception("[MacroScan] cycle read failed for %s", product_id)
            rows.append(
                {
                    "symbol": product_id.removesuffix("-USD"),
                    "product_id": product_id,
                    "available": False,
                    "reason": "read_failed",
                }
            )
    breadth = universe_breadth(rows)
    gate_breadth = breadth if breadth_products is None else universe_breadth(
        [row for row in rows if row["product_id"] in breadth_products]
    )
    try:
        regime = macro_industry_regime(histories, gate_breadth, members=members)
    except Exception:
        logging.exception("[MacroScan] industry regime failed")
        regime = {"available": False, "reason": "regime_failed"}
    stage_tier = regime.get("active_target_tier") if regime.get("available") else None
    for row in rows:
        tiers = row.pop("_tiers", None)
        if not row.get("available"):
            continue
        row["macro_regime_gate"] = regime.get("macro_regime_gate")
        if stage_tier and (tiers or {}).get(stage_tier):
            row["active_target_tier"] = stage_tier
    buckets = {
        name: sorted(
            (row for row in rows if row.get("bucket") == name),
            key=lambda row: (-row["score"], row["symbol"]),
        )
        for name in BUCKETS
    }
    return {
        "industry": regime,
        "breadth": breadth,
        "buckets": buckets,
        "bucket_labels": dict(BUCKETS),
        "coins": rows,
        "scanned": breadth["coins"],
        "skipped": [row["symbol"] for row in rows if not row.get("available")],
        "blocks_alerts": False,
        "outcome_validated": False,
    }
