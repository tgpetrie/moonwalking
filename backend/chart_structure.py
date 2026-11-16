"""Plain-English structure layer on top of the wave engine.

Pure and deterministic; this module does no network I/O. It turns an
``elliott_wave_engine`` read into things a reader with no charting vocabulary
can follow:

- ``swing_history`` labels each confirmed swing as a higher or lower high or
  low and finds the current run of higher lows (a rising floor) or lower highs
  (a falling ceiling).
- ``plain_story`` restates the active read as a short sequence: the prior
  move, the pullback zone, the recovery target and the price that breaks the
  setup, plus the supporting signs in everyday words.
- ``radar_structure`` reads 15m, 1h and 4h structure for one product and
  returns a single posture for a 3m gainer row. It is display context only:
  nothing here gates, ranks or suppresses an alert.

Wording is descriptive. Nothing in this module is outcome-validated.
"""

from __future__ import annotations

import logging
import math
from statistics import median
from typing import Any

__all__ = [
    "HORIZONS",
    "DEFAULT_HORIZON",
    "horizon_list",
    "multi_year_context",
    "top_down_confluence",
    "apply_macro_regime",
    "swing_history",
    "plain_story",
    "short_headline",
    "trend_state",
    "radar_structure",
    "radar_posture",
]

# The three views offered on the Chart Read panel. ``span`` is what the
# candle history actually covers, so the label never promises more than it has.
HORIZONS: dict[str, dict[str, Any]] = {
    "short": {
        "key": "short",
        "label": "Short-term",
        "timeframe": "15m",
        "higher_timeframe": "4h",
        "span": "~3 days",
        "detail": "15-minute candles · ~3 days",
    },
    "swing": {
        "key": "swing",
        "label": "Swing",
        "timeframe": "1h",
        "higher_timeframe": "4h",
        "span": "~12 days",
        "detail": "1-hour candles · ~12 days",
    },
    "macro": {
        "key": "macro",
        "label": "Macro",
        "timeframe": "4h",
        "higher_timeframe": "1d",
        "span": "~1 month",
        "detail": "4-hour candles · ~1 month",
    },
    "cycle": {
        "key": "cycle",
        "label": "Cycle",
        "timeframe": "1d",
        "higher_timeframe": "1w",
        "span": "1–3+ years",
        "detail": "Daily candles · multi-year history",
    },
}
DEFAULT_HORIZON = "swing"

# Two lows (or highs) closer than this share of a typical swing count as the
# same level: a hold, not a higher or lower one.
HOLD_TOLERANCE = 0.10

_SWING_LABEL = {
    ("low", "higher"): "Higher low",
    ("low", "lower"): "Lower low",
    ("low", "equal"): "Held the prior low",
    ("low", "first"): "Swing low",
    ("high", "higher"): "Higher high",
    ("high", "lower"): "Lower high",
    ("high", "equal"): "Stalled at the prior high",
    ("high", "first"): "Swing high",
}


def horizon_list() -> list[dict[str, Any]]:
    return [dict(HORIZONS[key]) for key in ("short", "swing", "macro", "cycle")]


def _cycle_analysis():
    try:
        import cycle_analysis
    except ImportError:
        from backend import cycle_analysis
    return cycle_analysis


def multi_year_context(candles: list[list[Any]] | None) -> dict[str, Any]:
    """Describe the multi-year daily range and the momentum behind it.

    The range, the Fibonacci grids, the historical shelves and the structure
    are read from the trailing ``cycle_analysis.CYCLE_WINDOW_DAYS`` bars. The
    daily, weekly and monthly indicators warm up on every bar supplied, so
    passing a longer history only steadies them.

    The cycle low and high skip single-bar flash wicks; the raw extremes are
    reported next to them.
    """
    analysis = _cycle_analysis()
    by_ts = {}
    for bar in candles or []:
        if not isinstance(bar, (list, tuple)) or len(bar) < 6:
            continue
        values = [_num(value) for value in bar[:6]]
        if any(value is None for value in values):
            continue
        ts, low, high, opening, close, volume = values
        if low <= 0 or volume < 0 or not low <= min(opening, close) <= max(opening, close) <= high:
            continue
        by_ts[ts] = tuple(values)
    if not by_ts:
        return {"available": False, "reason": "no_daily_history"}
    history = [by_ts[ts] for ts in sorted(by_ts)]
    rows = history[-analysis.CYCLE_WINDOW_DAYS:]
    grids = analysis.fib_structure(rows)
    index, filtered = grids.pop("_index"), grids.pop("_rows")
    low = (grids["cycle_low"]["timestamp"], grids["cycle_low"]["price"])
    high = (grids["cycle_high"]["timestamp"], None, grids["cycle_high"]["price"])
    price = rows[-1][4]
    span = high[2] - low[1]
    try:
        extras = {
            **analysis.momentum_stack(history),
            "daily_structure": analysis.daily_structure(filtered),
            "corrective_structure": analysis.corrective_structure(
                filtered, index["high"], history
            ),
        }
    except Exception:  # the range read must survive an indicator failure
        logging.exception("[ChartStructure] cycle momentum unavailable")
        extras = {"cycle_momentum_error": True}
    groups: dict[tuple[str, int], list] = {}
    for row in rows:
        for kind, value in (("support", row[1]), ("resistance", row[2])):
            bucket = math.floor(math.log(value) / math.log(1.02))
            groups.setdefault((kind, bucket), []).append((value, row[5]))
    zones = []
    for (kind, _), points in groups.items():
        if len(points) < 3:
            continue
        zones.append({
            "kind": kind,
            "low": min(point[0] for point in points),
            "high": max(point[0] for point in points),
            "touches": len(points),
            "volume": round(sum(point[1] for point in points), 8),
        })
    zones.sort(key=lambda zone: (-zone["touches"], -zone["volume"], zone["low"]))
    expected_days = int((rows[-1][0] - rows[0][0]) / 86400) + 1
    return {
        "available": True,
        **grids,
        "current_price": price,
        "pct_from_cycle_high": round((price / high[2] - 1) * 100, 2),
        "cycle_range_position_pct": round((price - low[1]) / span * 100, 2) if span else None,
        "macro_fib_levels": {str(ratio): high[2] - span * ratio for ratio in analysis.RETRACEMENT_RATIOS},
        "log_fib_retracements": {
            str(ratio): high[2] ** (1.0 - ratio) * low[1] ** ratio
            for ratio in analysis.RETRACEMENT_RATIOS
        } if span > 0 else {},
        "fib_ratio_sets": {
            "retracements": list(analysis.RETRACEMENT_RATIOS),
            "extensions": list(analysis.EXTENSION_RATIOS),
        },
        "major_historical_zones": zones[:6],
        "zone_method": "daily highs/lows grouped into 2% price bands; at least three daily touches; sorted by touches then base volume",
        "candle_count": len(rows),
        "history_candle_count": len(history),
        "coverage_days": expected_days,
        "missing_days": max(0, expected_days - len(rows)),
        "is_multi_year": len(rows) >= 365 and expected_days - len(rows) <= expected_days * 0.1,
        "first_timestamp": rows[0][0],
        "last_timestamp": rows[-1][0],
        **extras,
        "outcome_validated": False,
    }


_PATTERN_TEXT = {
    "wxy_terminal_sweep": (
        "Three-leg decline from the cycle high (5-3-5 / W-X-Y). The last leg "
        "has reached the base the prior advance started from."
    ),
    "abcde_channel_test": (
        "Five-leg channel from the cycle high (A-B-C-D-E). The latest low is "
        "testing the channel's lower trendline."
    ),
    "double_bottom_accumulation": (
        "The latest low is retesting the prior low (a double bottom)."
    ),
}


def _cycle_pattern(
    structure: dict[str, Any], daily: dict[str, Any], in_box: bool = False
) -> dict[str, Any]:
    """Name the multi-year pattern in the two shapes this read supports.

    A three-leg decline counts as a sweep of the base when price is at the
    base the advance started from or, when the window holds no earlier base,
    inside the multi-year support box.
    """
    corrective = str(structure.get("kind") or "none")
    channel = structure.get("channel") or {}
    double_bottom = bool(structure.get("double_bottom_retest") or daily.get("double_bottom"))
    terminal = (daily.get("final_leg_down_swings") or 0) >= 3
    kind = "none"
    if corrective == "abcde_channel" and channel.get("holds"):
        kind = "abcde_channel_test"
    elif corrective in {"wxy_zigzag", "flat_retest"} and (
        structure.get("at_historic_base") or in_box
    ):
        kind = "wxy_terminal_sweep"
    elif double_bottom:
        kind = "double_bottom_accumulation"
    text = _PATTERN_TEXT.get(kind, "")
    if kind == "abcde_channel_test" and channel.get("overthrow"):
        text += " It dipped through the line briefly and closed back near it."
    if kind == "wxy_terminal_sweep" and terminal:
        text += " That leg came down in a stair-step, which is how a finishing leg usually looks."
    return {
        "kind": kind,
        "corrective_kind": corrective,
        "legs": structure.get("legs") or 0,
        "terminal_wave_5": bool(terminal and corrective in {"wxy_zigzag", "flat_retest"}),
        "at_historic_base": bool(structure.get("at_historic_base")),
        "double_bottom": double_bottom,
        "channel_overthrow": bool(channel.get("overthrow")) if channel else False,
        "description": text,
    }


def _invalidation_stop(daily: dict[str, Any], price: float) -> dict[str, Any] | None:
    """A structural stop just under the prior double-bottom or last-leg low."""
    analysis = _cycle_analysis()
    reference = _num((daily.get("structural_low") or {}).get("price"))
    if reference is None or reference <= 0:
        return None
    basis = "wave_c_low"
    first = _num(((daily.get("double_bottom") or {}).get("first") or {}).get("price"))
    if first is not None and first > 0:
        reference, basis = min(reference, first), "double_bottom_low"
    stop = reference * (1.0 - analysis.STOP_BUFFER)
    if stop >= price:
        return None
    distance = round((price - stop) / price * 100.0, 2)
    return {
        "stop_price": stop,
        "stop_distance_pct": distance,
        "reference_low": reference,
        "basis": basis,
        "buffer_pct": analysis.STOP_BUFFER * 100.0,
        "tight": distance < 10.0,
        "message": f"Accumulation read is invalid below {_money(stop)} ({distance:.1f}% under price)",
    }


def top_down_confluence(cycle: dict[str, Any], reads: dict[str, dict[str, Any]], current_price: Any) -> dict[str, Any]:
    """Compare bullish short-term swings with observed cycle support."""
    price = _num(current_price)
    if not cycle.get("available") or not cycle.get("is_multi_year"):
        return {"available": False, "reason": "multi_year_history_unavailable"}
    low = _num((cycle.get("cycle_low") or {}).get("price"))
    high = _num((cycle.get("cycle_high") or {}).get("price"))
    fib = cycle.get("log_fib_retracements") or {}
    box_low, box_high = _num(fib.get("0.886")), _num(fib.get("0.618"))
    if price is None or low is None or high is None or high <= low or box_low is None or box_high is None:
        return {"available": False, "reason": "cycle_levels_unavailable"}
    result = {
        "available": True,
        "at_multi_year_support": None,
        "macro_log_support_box": {"low": box_low, "high": box_high},
        "micro_support_box": None,
        "micro_breakout_pivot": None,
        "micro_timeframe": None,
    }
    support_top = max(low + (high - low) * 0.35, box_high)

    def overlaps(a, b):
        return a <= support_top and b >= low or a <= box_high and b >= box_low

    at_support = overlaps(price, price)
    for tf in ("1h", "4h"):
        wave = reads.get(tf) or {}
        if not wave.get("available") or wave.get("bias") != "bullish":
            continue
        zone = wave.get("projected_c_zone") or {}
        zlow, zhigh = _num(zone.get("low")), _num(zone.get("high"))
        if zlow is not None and zhigh is not None:
            at_support = at_support or overlaps(min(zlow, zhigh), max(zlow, zhigh))
        points = {str(p.get("label")): _num(p.get("price")) for p in wave.get("wave_points") or [] if isinstance(p, dict)}
        c_price = points.get("C")
        if c_price is not None:
            at_support = at_support or overlaps(c_price, c_price)
        is_abc = wave.get("active_pattern") in {"abc_in_progress", "abc_complete"}
        origin, peak, pivot = (points.get("start"), points.get("0"), points.get("B")) if is_abc else (None, None, None)
        if origin is None or peak is None:
            pivots = wave.get("pivots") or []
            for first, second in reversed(list(zip(pivots, pivots[1:]))):
                if first.get("kind") == "low" and second.get("kind") == "high":
                    origin, peak = _num(first.get("price")), _num(second.get("price"))
                    break
        if result["micro_timeframe"] is None and origin is not None and peak is not None and 0 < origin < peak:
            span = peak - origin
            result.update(
                micro_timeframe=tf,
                micro_support_box={"low": peak - span * 0.786, "high": peak - span * 0.5},
                micro_breakout_pivot=pivot if pivot is not None and pivot > 0 else None,
            )
    # Multi-year structure: a channel trendline, double-bottom or base test
    # counts as support even when price sits above the lower third of the range.
    structure = cycle.get("corrective_structure") or {}
    daily = cycle.get("daily_structure") or {}
    in_box = overlaps(price, price) or bool(structure.get("testing_support"))
    at_support = at_support or in_box
    result["at_multi_year_support"] = at_support
    result["in_accumulation_box"] = in_box
    result["cycle_pattern"] = _cycle_pattern(structure, daily, in_box)
    result["confirmation_breakout"] = daily.get("confirmation_breakout") or {"broken": False}
    result["low_confirmation_pivot"] = None
    pivot = daily.get("low_confirmation_pivot")
    if at_support and pivot and _num(pivot.get("price")):
        result["low_confirmation_pivot"] = {
            **pivot,
            "message": f"Break above {_money(pivot['price'])} signals cycle low is in",
        }
    result["accumulation_invalidation_stop"] = _invalidation_stop(daily, price) if in_box else None
    result["fib_confluence_clusters"] = cycle.get("fib_confluence_clusters") or []
    result["rollover_target_box"] = cycle.get("rollover_target_box") or {"available": False}
    result["full_extension_targets"] = cycle.get("full_extension_targets") or {"available": False}
    # Stages 1-2 of the industry gate read the conservative box; the caller
    # switches this to the full extensions in stages 3-4.
    result["active_target_tier"] = "rollover_target_box"
    result["outcome_validated"] = False
    return result


TARGET_TIER_BY_STAGE = {
    "stage_1_macro_compression": "rollover_target_box",
    "stage_2_btc_majors_lead": "rollover_target_box",
    "stage_3_alt_index_breakout": "full_extension_targets",
    "stage_4_alt_season_expansion": "full_extension_targets",
}


def apply_macro_regime(confluence: dict[str, Any], regime: dict[str, Any] | None) -> dict[str, Any]:
    """Attach the industry gate to one coin's top-down read. Returns ``confluence``.

    The gate chooses which target tier is the active expectation. With no
    regime, or a tier the coin has no levels for, the conservative box stays.
    """
    if not isinstance(confluence, dict) or not confluence.get("available"):
        return confluence
    stage = (regime or {}).get("liquidity_rotation_stage")
    gate = (regime or {}).get("macro_regime_gate")
    tier = TARGET_TIER_BY_STAGE.get(stage, "rollover_target_box")
    if not (confluence.get(tier) or {}).get("available"):
        tier = "rollover_target_box"
    confluence["macro_regime_gate"] = gate if stage else None
    confluence["liquidity_rotation_stage"] = stage
    confluence["active_target_tier"] = tier
    return confluence


def _money(price: Any) -> str:
    try:
        value = float(price)
    except (TypeError, ValueError):
        return "—"
    if value >= 1000:
        return f"${value:,.0f}"
    if value >= 1:
        return f"${value:,.2f}"
    return f"${value:.4g}"


def _num(value: Any) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if out == out and abs(out) != float("inf") else None


# ─── swing history ────────────────────────────────────────────────────────────


def _run(swings: list[dict[str, Any]], kind: str, keep: set[str]) -> list[dict]:
    """The latest unbroken chain of ``kind`` swings whose relation is in ``keep``.

    Returned oldest first and including the swing the chain started from.
    """
    same = [s for s in swings if s["kind"] == kind]
    chain: list[dict] = []
    for swing in reversed(same):
        chain.append(swing)
        if swing["relation"] not in keep:
            break
    chain.reverse()
    if len(chain) < 2 or chain[-1]["relation"] not in keep:
        return []
    return chain


def _line(chain: list[dict], kind: str, intact: bool) -> dict[str, Any] | None:
    if len(chain) < 2:
        return None
    return {
        "kind": kind,
        "count": len(chain) - 1,
        "intact": intact,
        "points": [{"ts": s["ts"], "price": s["price"]} for s in chain],
    }


def swing_history(
    pivots: list[dict[str, Any]] | None, last_price: float | None = None
) -> dict[str, Any]:
    """Label confirmed swings and describe the run they form.

    ``pivots`` are the engine's confirmed swing points (``ts``, ``price``,
    ``kind``). Every label uses only the swings before it in the list, so
    adding later swings never changes an earlier label. ``last_price`` is the
    latest close; with it the text says when price has already slipped under
    the last higher low (or over the last lower high) before a new swing is
    confirmed.
    """
    points = []
    for p in pivots or []:
        ts, price = _num(p.get("ts")), _num(p.get("price"))
        if ts is None or price is None or price <= 0:
            continue
        if p.get("kind") not in ("high", "low"):
            continue
        points.append({"ts": ts, "price": price, "kind": p["kind"]})
    points.sort(key=lambda p: p["ts"])

    last: dict[str, float | None] = {"high": None, "low": None}
    swings: list[dict[str, Any]] = []
    legs: list[float] = []
    for i, p in enumerate(points):
        if i:
            legs.append(abs(p["price"] - points[i - 1]["price"]))
        # Typical swing size so far; later swings never move an earlier label.
        tolerance = HOLD_TOLERANCE * median(legs) if legs else 0.0
        prev = last[p["kind"]]
        if prev is None:
            relation = "first"
        elif abs(p["price"] - prev) <= tolerance:
            relation = "equal"
        else:
            relation = "higher" if p["price"] > prev else "lower"
        swings.append(
            {**p, "relation": relation, "label": _SWING_LABEL[(p["kind"], relation)]}
        )
        last[p["kind"]] = p["price"]

    floor_chain = _run(swings, "low", {"higher", "equal"})
    ceiling_chain = _run(swings, "high", {"lower", "equal"})
    higher_lows = max(0, len(floor_chain) - 1)
    lower_highs = max(0, len(ceiling_chain) - 1)
    higher_highs = max(0, len(_run(swings, "high", {"higher"})) - 1)
    lower_lows = max(0, len(_run(swings, "low", {"lower"})) - 1)

    if higher_lows >= 2 and higher_highs >= 1:
        trend = "up"
    elif lower_highs >= 2 and lower_lows >= 1:
        trend = "down"
    elif higher_lows >= 2:
        trend = "higher_lows"
    elif lower_highs >= 2:
        trend = "lower_highs"
    else:
        trend = "mixed"

    last_price = _num(last_price)
    floor_intact = not (
        floor_chain and last_price is not None and last_price < floor_chain[-1]["price"]
    )
    ceiling_intact = not (
        ceiling_chain
        and last_price is not None
        and last_price > ceiling_chain[-1]["price"]
    )

    watch_level = None
    if not swings:
        headline = (
            "Not enough confirmed swings yet to show a pattern of highs and lows."
        )
        why = ""
    elif higher_lows >= 2:
        watch_level = floor_chain[-1]["price"]
        headline = (
            f"{higher_lows} higher lows in a row: each dip has stopped at a "
            "higher price than the one before."
        )
        if floor_intact:
            why = (
                "That rising floor is why this read watches for the next dip to "
                f"hold above {_money(watch_level)}. A drop below it would end the "
                "run of higher lows."
            )
        else:
            why = (
                f"Price is now below the latest of them ({_money(watch_level)}), "
                "so that rising floor is under pressure until price gets back "
                "above it."
            )
    elif lower_highs >= 2:
        watch_level = ceiling_chain[-1]["price"]
        headline = (
            f"{lower_highs} lower highs in a row: each bounce has stalled at a "
            "lower price than the one before."
        )
        if ceiling_intact:
            why = (
                "That falling ceiling is why this read treats bounces with "
                f"caution until price gets back above {_money(watch_level)}."
            )
        else:
            why = (
                f"Price is now above the latest of them ({_money(watch_level)}), "
                "which ends the run of lower highs if it holds."
            )
    elif higher_lows == 1:
        watch_level = floor_chain[-1]["price"]
        headline = "The last dip stopped at a higher price than the one before it."
        if floor_intact:
            why = (
                f"One higher low is a start, not a run. Holding above "
                f"{_money(watch_level)} on the next dip would make it two."
            )
        else:
            why = (
                f"Price has since slipped below that low ({_money(watch_level)}), "
                "so the higher low has not held."
            )
    elif lower_highs == 1:
        watch_level = ceiling_chain[-1]["price"]
        headline = "The last bounce stalled at a lower price than the one before it."
        if ceiling_intact:
            why = (
                f"One lower high is a caution, not a run. A move back above "
                f"{_money(watch_level)} would cancel it."
            )
        else:
            why = (
                f"Price has since moved back above that high "
                f"({_money(watch_level)}), which cancels it if it holds."
            )
    else:
        headline = (
            "Recent swings are mixed: no run of higher lows or lower highs right now."
        )
        why = ""

    return {
        "swings": swings,
        "trend": trend,
        "higher_lows": higher_lows,
        "higher_highs": higher_highs,
        "lower_highs": lower_highs,
        "lower_lows": lower_lows,
        "floor": _line(floor_chain, "rising_floor", floor_intact),
        "ceiling": _line(ceiling_chain, "falling_ceiling", ceiling_intact),
        "watch_level": watch_level,
        "headline": headline,
        "why": why,
    }


# ─── plain-English story ──────────────────────────────────────────────────────

# (plain wording when the read is bullish, when bearish, technical name)
_FACTOR_TEXT: dict[str, tuple[str, str, str]] = {
    "higher_tf_trend": (
        "Bigger trend points up too",
        "Bigger trend points down too",
        "Higher-timeframe trend",
    ),
    "rsi_divergence": (
        "Selling pressure slowing",
        "Buying pressure slowing",
        "RSI divergence",
    ),
    "macd_divergence": (
        "Downward momentum fading",
        "Upward momentum fading",
        "MACD divergence",
    ),
    "volume_contraction": (
        "Dipping on lighter volume",
        "Bouncing on lighter volume",
        "Volume contraction",
    ),
    "bollinger_reclaim": (
        "Back inside its usual price range",
        "Back inside its usual price range",
        "Bollinger reclaim",
    ),
    "ema_reclaim": (
        "Stepping back above short-term trend",
        "Slipping back below short-term trend",
        "EMA reclaim",
    ),
    "prior_impulse": (
        "Follows a strong five-step advance",
        "Follows a strong five-step decline",
        "Prior five-wave impulse",
    ),
}
_OPPOSED_TEXT = {
    "higher_tf_trend": ("Bigger trend points down", "Bigger trend points up"),
}


def _why_it_matters(wave: dict[str, Any], up: bool) -> list[dict[str, Any]]:
    out = []
    higher = wave.get("higher_timeframe")
    for factor in wave.get("confluence_factors") or []:
        name, state = factor.get("name"), factor.get("state")
        if name not in _FACTOR_TEXT or state not in ("present", "opposed"):
            continue
        plain_up, plain_down, technical = _FACTOR_TEXT[name]
        if state == "opposed":
            pair = _OPPOSED_TEXT.get(name)
            if not pair:
                continue
            plain = pair[0] if up else pair[1]
        else:
            plain = plain_up if up else plain_down
        if name == "higher_tf_trend" and higher:
            technical = f"{higher} trend"
        out.append(
            {
                "name": name,
                "state": state,
                "plain": plain,
                "technical": technical,
                "detail": str(factor.get("detail") or ""),
            }
        )
    return out


def _pct(a: float, b: float) -> float:
    return abs(b / a - 1.0) * 100.0 if a else 0.0


def _abc_story(wave: dict[str, Any], up: bool) -> dict[str, Any]:
    pts = {p.get("label"): p for p in wave.get("wave_points") or []}
    start, peak, c_point = pts.get("start"), pts.get("0"), pts.get("C")
    zone = wave.get("projected_c_zone") or {}
    target, breaks = wave.get("target_price"), wave.get("invalidation_price")
    status = wave.get("status")
    complete = wave.get("active_pattern") == "abc_complete"
    side = "below" if up else "above"
    dip, bounce = ("dip", "bounce") if up else ("bounce", "dip")

    if complete and status == "target_reached":
        headline = (
            "Pullback finished and price recovered to the last bounce high"
            if up
            else "Relief bounce finished and price fell back to the last dip low"
        )
    elif complete:
        headline = (
            "Pullback looks finished: price has turned back up"
            if up
            else "Relief bounce looks finished: price has turned back down"
        )
    elif status == "in_c_zone":
        headline = (
            "Pulling back after an advance, now inside the usual dip zone"
            if up
            else "Bouncing inside a decline, now inside the usual bounce zone"
        )
    else:
        headline = (
            "Pulling back after an advance, not yet at the usual dip zone"
            if up
            else "Bouncing inside a decline, not yet at the usual bounce zone"
        )

    steps: list[dict[str, Any]] = []
    if start and peak:
        verb = "Rose" if up else "Fell"
        steps.append(
            {
                "key": "prior_move",
                "number": 1,
                "title": "Prior advance" if up else "Prior decline",
                "text": (
                    f"{verb} {_pct(start['price'], peak['price']):.1f}% from "
                    f"{_money(start['price'])} to {_money(peak['price'])}."
                ),
                "from_price": start["price"],
                "to_price": peak["price"],
            }
        )
    if zone.get("low") and zone.get("high"):
        if complete and c_point:
            where = f"The {dip} ended inside it at {_money(c_point['price'])}."
        elif status == "in_c_zone":
            where = "Price is inside it now."
        else:
            where = "Price has not reached it yet."
        steps.append(
            {
                "key": "zone",
                "number": 2,
                "title": "Pullback / dip zone" if up else "Relief bounce zone",
                "short_title": "Dip zone" if up else "Bounce zone",
                "text": f"{_money(zone['low'])} to {_money(zone['high'])}. {where}",
                "low": zone["low"],
                "high": zone["high"],
            }
        )
    if target:
        text = f"{_money(target)}, the {'high' if up else 'low'} of the last {bounce}."
        if status == "target_reached":
            text += " Price has already returned to it."
        elif peak:
            text += f" The prior {'peak' if up else 'low'} is {_money(peak['price'])}."
        steps.append(
            {
                "key": "target",
                "number": 3,
                "title": "Recovery target" if up else "Downside target",
                "text": text,
                "price": target,
                "prior_extreme": peak["price"] if peak else None,
            }
        )
    if breaks:
        steps.append(
            {
                "key": "breaks",
                "title": f"Setup breaks {side} {_money(breaks)}",
                "text": (
                    f"A trade {side} that price means this read no longer applies."
                ),
                "price": breaks,
                "side": side,
            }
        )
    return {
        "kind": "pullback_in_advance" if up else "bounce_in_decline",
        "headline": headline,
        "steps": steps,
    }


def _impulse_story(wave: dict[str, Any], up: bool) -> dict[str, Any]:
    points = [p for p in wave.get("wave_points") or [] if p.get("confirmed", True)]
    status = wave.get("status")
    breaks = wave.get("invalidation_price")
    side = "below" if up else "above"
    move, push = ("advance", "push higher") if up else ("decline", "push lower")
    steps: list[dict[str, Any]] = []
    if len(points) >= 2:
        first = points[0]
        prices = [p["price"] for p in points]
        extreme = max(prices) if up else min(prices)
        steps.append(
            {
                "key": "prior_move",
                "number": 1,
                "title": "Run so far",
                "text": (
                    f"{'Up' if up else 'Down'} {_pct(first['price'], extreme):.1f}% "
                    f"from {_money(first['price'])} to {_money(extreme)} in a "
                    f"stair-step {move}."
                ),
                "from_price": first["price"],
                "to_price": extreme,
            }
        )
    if status == "complete":
        headline = f"Extended run: a five-step {move} looks complete"
        stage = {
            "title": "Run looks finished",
            "text": (
                f"Three pushes and two pauses are complete. A {'pullback' if up else 'bounce'} "
                "often follows a finished run."
            ),
        }
    elif status == "wave_5_underway":
        headline = f"Stair-step {move}, on what looks like the final push"
        stage = {
            "title": "Final push underway",
            "text": f"A third {push} is underway. Runs often tire at this stage.",
        }
    else:
        headline = f"Stair-step {move}, pausing before another push"
        stage = {
            "title": "Pausing",
            "text": (
                f"Price is {'pulling back' if up else 'bouncing'} after the second "
                f"push. The run stays intact while it holds {'above' if up else 'below'} "
                f"{_money(breaks)}."
            ),
        }
    steps.append({"key": "stage", "number": 2, **stage})
    if breaks:
        steps.append(
            {
                "key": "breaks",
                "title": f"Setup breaks {side} {_money(breaks)}",
                "text": (
                    f"A trade {side} that price means this read no longer applies."
                ),
                "price": breaks,
                "side": side,
            }
        )
    return {
        "kind": "run_up" if up else "run_down",
        "headline": headline,
        "steps": steps,
    }


def plain_story(wave: dict[str, Any] | None) -> dict[str, Any]:
    """Restate an engine read as numbered, jargon-free steps. Never raises."""
    empty = {
        "kind": "none",
        "headline": "No clear setup in the recent swings.",
        "steps": [],
        "why_it_matters": [],
    }
    try:
        if not wave or not wave.get("available"):
            return empty
        pattern = wave.get("active_pattern")
        if pattern in (None, "none"):
            return empty
        up = wave.get("bias") == "bullish"
        story = (
            _abc_story(wave, up)
            if str(pattern).startswith("abc")
            else _impulse_story(wave, up)
        )
        story["why_it_matters"] = _why_it_matters(wave, up)
        return story
    except Exception as exc:  # the chart read must survive a wording failure
        logging.warning("[ChartStructure] plain story failed: %s", exc)
        return empty


def short_headline(wave: dict[str, Any] | None) -> str | None:
    """One line for a coin header: the active setup, else the run of swings.

    Returns ``None`` when there is no usable read, so the caller can fall back
    to something else. Never raises.
    """
    try:
        if not wave or not wave.get("available"):
            return None
        pattern = str(wave.get("active_pattern") or "none")
        status = wave.get("status")
        up = wave.get("bias") == "bullish"
        zone = wave.get("projected_c_zone") or {}
        target, breaks = wave.get("target_price"), wave.get("invalidation_price")
        if pattern.startswith("abc") and zone.get("low") and zone.get("high"):
            band = f"{_money(zone['low'])}–{_money(zone['high'])}"
            name = "dip zone" if up else "bounce zone"
            goal = "recovery target" if up else "downside target"
            if pattern == "abc_complete":
                if status == "target_reached":
                    return (
                        f"Pullback recovered to {_money(target)}"
                        if up
                        else f"Relief bounce faded back to {_money(target)}"
                    )
                points = {p.get("label"): p for p in wave.get("wave_points") or []}
                end = (points.get("C") or {}).get("price", breaks)
                swing = "Dip" if up else "Bounce"
                return (
                    f"{swing} looks finished near {_money(end)} · "
                    f"{goal} {_money(target)}"
                )
            if status == "in_c_zone":
                move = "bounce" if up else "turn back down"
                return (
                    f"Inside {name} ({band}) · watching for a {move} toward "
                    f"{_money(target)}"
                )
            lead = "Pulling back toward" if up else "Bouncing toward"
            return f"{lead} {name} ({band}) · {goal} {_money(target)}"
        if pattern.startswith("impulse"):
            move = "advance" if up else "decline"
            if status == "complete":
                return (
                    f"Extended run · five-step {move} looks complete · breaks "
                    f"{'below' if up else 'above'} {_money(breaks)}"
                )
            return (
                f"Stair-step {move} · intact while {'above' if up else 'below'} "
                f"{_money(breaks)}"
            )
        history = wave.get("swing_history") or {}
        watch = history.get("watch_level")
        if (history.get("higher_lows") or 0) >= 2:
            return (
                f"{history['higher_lows']} higher lows in a row · floor at "
                f"{_money(watch)}"
            )
        if (history.get("lower_highs") or 0) >= 2:
            return (
                f"{history['lower_highs']} lower highs in a row · needs a break "
                f"above {_money(watch)}"
            )
        if history.get("swings"):
            return "No clear setup in the recent swings"
        return None
    except Exception as exc:  # a header line must never break the chart read
        logging.warning("[ChartStructure] short headline failed: %s", exc)
        return None


# ─── Radar posture ────────────────────────────────────────────────────────────

_REVIEW_NOTE = (
    "Context only. It does not block, rank or change any alert, and it has not "
    "been confirmed on new data."
)


def trend_state(candles: list[list[Any]] | None) -> str:
    """``up``, ``down``, ``flat`` or ``unknown`` from completed candles.

    Uses the wave engine's own higher-timeframe rule (close against EMA(20)
    and the EMA's slope over five bars), so "4h downtrend" means the same thing
    here as it does inside a wave read.
    """
    try:
        from elliott_wave_engine import HTF_EMA, HTF_SLOPE_BARS, _ema, _rows
    except ImportError:
        from backend.elliott_wave_engine import HTF_EMA, HTF_SLOPE_BARS, _ema, _rows

    rows = _rows(candles)
    if len(rows) < HTF_EMA + HTF_SLOPE_BARS + 1:
        return "unknown"
    closes = [r[4] for r in rows]
    ema = _ema(closes, HTF_EMA)
    slope = ema[-1] / ema[-1 - HTF_SLOPE_BARS] - 1.0
    if closes[-1] > ema[-1] and slope > 0:
        return "up"
    if closes[-1] < ema[-1] and slope < 0:
        return "down"
    return "flat"


def _has(wave: dict[str, Any], name: str) -> bool:
    return any(
        f.get("name") == name and f.get("state") == "present"
        for f in wave.get("confluence_factors") or []
    )


def radar_posture(
    reads: dict[str, dict[str, Any] | None], trend_4h: str = "unknown"
) -> dict[str, Any] | None:
    """One structural posture for a gainer row, or ``None`` when nothing stands out.

    ``reads`` maps a timeframe (``15m``, ``1h``, ``4h``) to an engine read.
    Risk postures win over constructive ones.
    """

    def state(tf: str) -> tuple[str, str, str]:
        wave = reads.get(tf) or {}
        if not wave.get("available"):
            return ("none", "none", "neutral")
        return (
            str(wave.get("active_pattern")),
            str(wave.get("status")),
            str(wave.get("bias")),
        )

    for tf in ("4h", "1h", "15m"):
        if state(tf) == ("impulse_complete", "complete", "bullish"):
            return {
                "key": "extended_run",
                "tone": "risk",
                "label": "Extended run · pullback risk",
                "short_label": "Extended run",
                "timeframe": tf,
                "detail": (
                    f"A five-step run up looks finished on the {tf} chart. In our "
                    "Oct 13 to Nov 12 review, 3-minute gainer flags at this point "
                    "crashed more often than other flags. " + _REVIEW_NOTE
                ),
            }
    if trend_4h == "down":
        return {
            "key": "fighting_downtrend",
            "tone": "risk",
            "label": "Fighting 4h downtrend",
            "short_label": "vs 4h downtrend",
            "timeframe": "4h",
            "detail": (
                "This pop is against a falling 4-hour trend: price is below its "
                "4h average and that average is still sloping down. " + _REVIEW_NOTE
            ),
        }
    if state("1h") == ("abc_complete", "confirmed", "bullish"):
        return {
            "key": "bounce_in_uptrend",
            "tone": "constructive",
            "label": "Bounce in 1h uptrend",
            "short_label": "1h bounce",
            "timeframe": "1h",
            "detail": (
                "On the 1-hour chart a pullback inside a larger advance looks "
                "finished and price has turned back up. " + _REVIEW_NOTE
            ),
        }
    for tf in ("1h", "4h"):
        wave = reads.get(tf) or {}
        if state(tf) == ("abc_in_progress", "in_c_zone", "bullish") and (
            _has(wave, "ema_reclaim") or _has(wave, "bollinger_reclaim")
        ):
            return {
                "key": "reclaiming_zone",
                "tone": "constructive",
                "label": "Reclaiming pullback zone",
                "short_label": "Reclaiming dip",
                "timeframe": tf,
                "detail": (
                    f"On the {tf} chart price dipped into the usual pullback zone "
                    "after an advance and is stepping back up out of it. "
                    + _REVIEW_NOTE
                ),
            }
    return None


def radar_structure(
    candles_15m: list[list[Any]] | None,
    candles_1h: list[list[Any]] | None,
    *,
    as_of_ts: float | None = None,
) -> dict[str, Any]:
    """Posture for one product from its 15m and 1h candles. Never raises.

    The 4h bars are built from the 1h candles. ``as_of_ts`` drops bars that
    have not closed, so a forming candle cannot change the posture.
    """
    out: dict[str, Any] = {
        "posture": None,
        "trend_4h": "unknown",
        "reads": {},
        "outcome_validated": False,
    }
    try:
        try:
            from chart_reader import build_wave_analysis
            from elliott_wave_engine import resample_candles
        except ImportError:
            from backend.chart_reader import build_wave_analysis
            from backend.elliott_wave_engine import resample_candles

        def closed(raw, step):
            rows = [c for c in raw or [] if c and len(c) >= 6]
            if as_of_ts is not None:
                rows = [c for c in rows if float(c[0]) + step <= as_of_ts]
            return sorted(rows, key=lambda c: float(c[0]))

        c15, c1h = closed(candles_15m, 900), closed(candles_1h, 3600)
        c4h = resample_candles(c1h, 14400)
        reads: dict[str, dict[str, Any]] = {}
        if c1h:
            reads["1h"] = build_wave_analysis(c1h, "1h", c4h)
            reads["4h"] = build_wave_analysis(c4h, "4h", [])
        if c15:
            reads["15m"] = build_wave_analysis(c15, "15m", c4h)
        out["trend_4h"] = trend_state(c4h)
        out["posture"] = radar_posture(reads, out["trend_4h"])
        out["reads"] = {
            tf: {
                "active_pattern": wave.get("active_pattern"),
                "status": wave.get("status"),
                "bias": wave.get("bias"),
            }
            for tf, wave in reads.items()
            if wave.get("available")
        }
    except Exception as exc:
        logging.warning("[ChartStructure] radar structure failed: %s", exc)
    return out
