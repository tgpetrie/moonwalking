"""Offline F1–F5 evidence from declared, receipt-time observations."""

from decimal import Decimal, DecimalException
import math
from pathlib import Path

from instant_book import MAX_QUOTE_AGE_MS
from instant_coverage import MAX_HEARTBEAT_GAP_MS
from instant_input_evidence import BENCHMARK, DIRECTIONS, _sha
from instant_timed_baseline import MINUTE_MS, PACE_MS, build_timed_baseline


VERSION = "instant-timed-features-v1-draft"
SLOW_MS = 180000
SIGMA_FLOOR = 0.0015
CANDLE_COUNT = 15
MIN_TRADED_CANDLES = 10
MIN_MATCHES = 5


def _missing(reason, **details):
    return dict(status="unavailable", reason=reason, **details)


def _value(value, *known, **details):
    if not math.isfinite(value):
        return _missing("nonfinite_feature", **details)
    return dict(
        status="ready", value=value, evidence_available_ts_ms=max(known), **details
    )


def _price_point(recorder, product, cutoff, asof):
    if cutoff < 0:
        return _missing(
            "insufficient_history", product_id=product, endpoint_ts_ms=cutoff
        )
    quote, known = recorder._quote_at(product, cutoff, asof)
    if not quote["available"]:
        return _missing(quote["reason"], product_id=product, endpoint_ts_ms=cutoff)
    bid, ask = float(quote["bid"]), float(quote["ask"])
    mid = bid + (ask - bid) / 2
    return _value(math.log(mid), known, spread_bps=(ask - bid) / mid * 10000)


def _move(start, stop):
    for point in (start, stop):
        if point["status"] != "ready":
            return point
    return _value(
        stop["value"] - start["value"],
        start["evidence_available_ts_ms"],
        stop["evidence_available_ts_ms"],
    )


def _participation(recorder, product, start, end, asof, pace, sign):
    if start < 0:
        return _missing("insufficient_history"), {}
    _, trades, reason, known = recorder._trade_window(product, start, end, asof)
    if reason:
        return _missing(reason), {}

    counts = dict(verified_match_count=len(trades))
    try:
        amounts = {"buy": Decimal(0), "sell": Decimal(0), None: Decimal(0)}
        for trade in trades:
            amounts[trade.taker_side] += Decimal(trade.price) * Decimal(trade.size)
        total = sum(amounts.values())
        if not total.is_finite():
            return _missing("invalid_quote_amount"), counts
        counts["verified_quote_usd"] = str(total)
        counts["unknown_side_usd"] = str(amounts[None])
        if pace["status"] != "ready":
            return (
                _missing("pace_baseline_unavailable", baseline_reason=pace["reason"]),
                counts,
            )
        median = Decimal(pace["pace_quote_usd_median_30s"])
        if median <= 0:
            return _missing("nonpositive_pace_median"), counts
        ratio = float(total / median)
        if not math.isfinite(ratio) or (total > 0 and ratio == 0):
            return _missing("invalid_volume_pace"), counts
        counts["unsigned_volume_pace"] = ratio
        if len(trades) < MIN_MATCHES:
            return _missing("too_few_matches"), counts
        if any(trade.taker_side is None for trade in trades):
            return _missing("unknown_match_side"), counts
        if total <= 0:
            return _missing("nonpositive_window_quote_amount"), counts
        imbalance = float((amounts["buy"] - amounts["sell"]) / total)
    except DecimalException:
        return _missing("invalid_quote_amount"), counts
    return (
        _value(
            sign * imbalance * math.log1p(ratio), known, pace["inputs_available_ts_ms"]
        ),
        counts,
    )


def _book_pressure(recorder, product, start, end, asof, sign):
    if start < 0:
        return _missing("insufficient_history")
    # Each stream is already receipt ordered. Overwriting the start key keeps
    # the last carried state; overwriting a same-ms key keeps the last event.
    states = {
        max(start, state.receipt_ts_ms): state
        for state in recorder.book.history[product]
        if state.receipt_ts_ms < end
        and recorder._packet_by_seq[state.receipt_seq].available_ts_ms <= asof
    }
    transport = {
        max(start, row["receipt_ts_ms"]): row
        for row in recorder.book.monitor.transport
        if row["product_id"] == product
        and row["receipt_ts_ms"] < end
        and recorder._packet_by_seq[row["receipt_seq"]].available_ts_ms <= asof
    }
    boundaries = sorted({start, end, *states, *transport})
    state = heartbeat = None
    known = end
    integral = 0.0
    for left, right in zip(boundaries, boundaries[1:]):
        state = states.get(left, state)
        heartbeat = transport.get(left, heartbeat)
        if state is None or state.best is None or state.reason:
            return _missing("book_state_unavailable", segment_start_ts_ms=left)
        if (
            heartbeat is None
            or heartbeat["reason"] != "heartbeat_observed"
            or state.connection_id != heartbeat["connection_id"]
        ):
            return _missing("heartbeat_unavailable", segment_start_ts_ms=left)
        if right - state.observation_ts_ms > MAX_QUOTE_AGE_MS:
            return _missing(
                "stale_book_span",
                first_invalid_ts_ms=max(
                    left, state.observation_ts_ms + MAX_QUOTE_AGE_MS
                ),
            )
        if right - heartbeat["receipt_ts_ms"] > MAX_HEARTBEAT_GAP_MS:
            return _missing(
                "stale_heartbeat_span",
                first_invalid_ts_ms=max(
                    left, heartbeat["receipt_ts_ms"] + MAX_HEARTBEAT_GAP_MS
                ),
            )
        bid_size, ask_size = map(Decimal, state.best[2:])
        pressure = float((bid_size - ask_size) / (bid_size + ask_size))
        integral += pressure * (right - left)
        known = max(
            known,
            recorder._packet_by_seq[state.receipt_seq].available_ts_ms,
            recorder._packet_by_seq[heartbeat["receipt_seq"]].available_ts_ms,
        )
    return _value(sign * integral / (end - start), known)


def _candle_range(recorder, product, start, end, asof):
    if start < 0:
        return _missing("insufficient_history")
    _, trades, reason, known = recorder._trade_window(product, start, end, asof)
    if reason:
        return _missing(reason)
    candles = {}
    for trade in trades:
        bucket = trade.receipt_ts_ms // MINUTE_MS
        price = Decimal(trade.price)
        low, high = candles.get(bucket, (price, price))
        candles[bucket] = min(low, price), max(high, price)
    counts = dict(
        traded_candles=len(candles), verified_empty_candles=CANDLE_COUNT - len(candles)
    )
    if len(candles) < MIN_TRADED_CANDLES:
        return _missing("too_few_traded_candles", **counts)
    low = min(candle[0] for candle in candles.values())
    high = max(candle[1] for candle in candles.values())
    try:
        log_range = float(high.ln() - low.ln())
    except DecimalException:
        return _missing("invalid_candle_range", **counts)
    return _value(log_range, known, **counts)


def _scaled_velocity(move, baseline, sigma, sign):
    if move["status"] != "ready":
        return move
    if baseline["status"] != "ready":
        return _missing(
            "volatility_baseline_unavailable", baseline_reason=baseline["reason"]
        )
    return _value(
        sign * move["value"] / sigma,
        move["evidence_available_ts_ms"],
        baseline["inputs_available_ts_ms"],
    )


def _acceleration(velocity, prior, sigma, sign):
    for component in (velocity, prior):
        if component["status"] != "ready":
            return component
    return _value(
        velocity["value"] - sign * prior["value"] / (5 * sigma),
        velocity["evidence_available_ts_ms"],
        prior["evidence_available_ts_ms"],
    )


def _compression(velocity, candles, sigma):
    for component in (velocity, candles):
        if component["status"] != "ready":
            return component
    expansion = max(velocity["value"], 0)
    return _value(
        expansion / (1 + candles["value"] / (sigma * math.sqrt(CANDLE_COUNT))),
        velocity["evidence_available_ts_ms"],
        candles["evidence_available_ts_ms"],
    )


def _market_relative(coin_move, btc_move, baseline, sigma, sign):
    for component in (coin_move, btc_move):
        if component["status"] != "ready":
            return component
    if baseline["status"] != "ready":
        return _missing(
            "volatility_baseline_unavailable", baseline_reason=baseline["reason"]
        )
    return _value(
        sign * (coin_move["value"] - baseline["beta"] * btc_move["value"]) / sigma,
        coin_move["evidence_available_ts_ms"],
        btc_move["evidence_available_ts_ms"],
        baseline["inputs_available_ts_ms"],
        beta_fallback=baseline["beta_fallback"],
    )


def build_timed_features(recorder, product, cutoff, direction, *, asof):
    """Calculate a single offline feature row with explicit evidence and clocks."""
    if direction not in DIRECTIONS:
        raise ValueError("direction must be up or down")
    if type(cutoff) is not int or type(asof) is not int or asof < cutoff:
        raise ValueError("feature as-of must be at or after the integer cutoff")
    baseline = build_timed_baseline(recorder, product, cutoff, asof=asof)
    vol, pace = baseline["volatility"], baseline["pace"]
    sigma = max(vol["sigma_1m"], SIGMA_FLOOR) if vol["status"] == "ready" else None
    sign = 1 if direction == "up" else -1
    slow, fast = cutoff - SLOW_MS, cutoff - PACE_MS

    start, middle, end = (
        _price_point(recorder, product, t, asof) for t in (slow, fast, cutoff)
    )
    recent, prior = _move(middle, end), _move(start, middle)
    coin = _move(start, end)
    btc = (
        coin
        if product == BENCHMARK
        else _move(
            _price_point(recorder, BENCHMARK, slow, asof),
            _price_point(recorder, BENCHMARK, cutoff, asof),
        )
    )
    candle_end = fast // MINUTE_MS * MINUTE_MS
    candle_start = candle_end - CANDLE_COUNT * MINUTE_MS
    candles = _candle_range(recorder, product, candle_start, candle_end, asof)
    velocity = _scaled_velocity(recent, vol, sigma, sign)
    flow, activity = _participation(recorder, product, fast, cutoff, asof, pace, sign)
    features = {
        "F1": _acceleration(velocity, prior, sigma, sign),
        "F2": flow,
        "F3": _book_pressure(recorder, product, fast, cutoff, asof, sign),
        "F4": _compression(velocity, candles, sigma),
        "F5": _market_relative(coin, btc, vol, sigma, sign),
    }

    row = dict(
        version=VERSION,
        product_id=product,
        direction=direction,
        feature_cutoff_ts_ms=cutoff,
        knowledge_asof_ts_ms=asof,
        baseline=baseline,
        sigma_used=sigma,
        candle_start_ts_ms=candle_start,
        candle_end_ts_ms=candle_end,
        features=features,
        controls=dict(
            current_velocity_sigma=velocity,
            unsigned_activity=activity,
            cutoff_spread_bps=end.get("spread_bps"),
            candle_range=candles,
            expansion=(
                max(velocity["value"], 0) if velocity["status"] == "ready" else None
            ),
            raw_signed_180s=sign * coin["value"] if coin["status"] == "ready" else None,
        ),
        builder_sha256=_sha(Path(__file__).read_text(encoding="utf-8").encode("utf-8")),
        scope="offline_feature_components",
        fitting_allowed=False,
    )
    row["computation_completed_ts_ms"] = recorder._now()
    row["later_diagnostic"] = row["computation_completed_ts_ms"] > cutoff
    return row
