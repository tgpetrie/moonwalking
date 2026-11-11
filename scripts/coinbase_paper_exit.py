"""Compare independent Coinbase spot exit rules on an ordered quote tape."""

import argparse
from bisect import bisect_left
from collections import Counter
from decimal import Decimal, DecimalException
import json
from pathlib import Path
import re


BPS = Decimal(10_000)
PERCENT = Decimal(100)
RULES = ("rebound_usd", "rebound_pct", "net_profit_pct")
PILOT_SCHEMA = "2.0"


def _number(record, field, *, allow_zero=False):
    if not isinstance(record, dict):
        raise ValueError(f"{field} must be a decimal number")
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


def _scenario_inputs(spec):
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
    thresholds = spec.get("thresholds")
    if not isinstance(thresholds, dict) or set(thresholds) != set(RULES):
        raise ValueError(f"thresholds must contain exactly {', '.join(RULES)}")
    return {
        "mode": "paper",
        "product_id": product,
        "quantity": quantity,
        "entry_cost_usd": cost,
        "exit_fee_bps": fee_bps,
        "slippage_bps": slip_bps,
        "thresholds": {rule: _number(thresholds, rule) for rule in RULES},
    }


def _ordered_quotes(quotes, *, allow_empty=False):
    if not isinstance(quotes, list) or (not allow_empty and not quotes):
        raise ValueError("quotes must contain at least one bid observation")
    previous_ms = -1
    for quote in quotes:
        if not isinstance(quote, dict):
            raise ValueError("each quote must be an object")
        observed_at_ms = quote.get("observed_at_ms")
        if type(observed_at_ms) is not int or observed_at_ms <= previous_ms:
            raise ValueError("quote times must be nonnegative and strictly increasing")
        previous_ms = observed_at_ms
        yield observed_at_ms, quote


def _mark_inputs(inputs):
    return (
        inputs["quantity"],
        inputs["entry_cost_usd"],
        inputs["exit_fee_bps"] / BPS,
        inputs["slippage_bps"] / BPS,
    )


def simulate_exit(spec):
    """Evaluate a legacy quote tape or a versioned paper pilot window."""
    inputs = _scenario_inputs(spec)
    version = spec.get("schema_version", "1.0")
    if version == PILOT_SCHEMA:
        return _simulate_window(spec, inputs)
    if version != "1.0" or any(
        key in spec
        for key in ("window_start_ms", "decision_latency_ms", "max_stale_ms")
    ):
        raise ValueError("paper pilot window requires schema_version 2.0")
    exits = dict.fromkeys(RULES)
    low = None
    mark_inputs = _mark_inputs(inputs)
    for observed_at_ms, quote in _ordered_quotes(spec.get("quotes")):
        if any(
            key in quote for key in ("bid_size", "exchange_time_ms", "quote_status")
        ):
            raise ValueError("paper pilot quotes require schema_version 2.0")
        bid = _number(quote, "bid_usd")
        if low is None or bid < low:
            low, low_observed_at_ms = bid, observed_at_ms
        mark = _mark(observed_at_ms, bid, low, low_observed_at_ms, *mark_inputs)
        for rule in RULES:
            if exits[rule] is None and mark[rule] >= inputs["thresholds"][rule]:
                exits[rule] = mark

    return {
        **inputs,
        "first_hypothetical_exits": exits,
        "hold_last_quote": mark,
    }


def _integer(record, name, *, minimum=0):
    value = record.get(name)
    if type(value) is not int or value < minimum:
        raise ValueError(f"{name} must be an integer of at least {minimum}")
    return value


def _pilot_mark(quote, observed, quantity, stale_after, low, low_at, mark_inputs):
    reported = quote.get("quote_status", "VALID")
    if reported == "UNAVAILABLE":
        return "unavailable", None
    if reported == "STALE":
        return "stale", None
    if reported not in ("VALID", "THIN_TOP_BID"):
        raise ValueError("unknown quote_status")
    exchange = _integer(quote, "exchange_time_ms")
    bid = _number(quote, "bid_usd")
    size = _number(quote, "bid_size", allow_zero=True)
    if not 0 <= observed - exchange <= stale_after:
        return "stale", None
    if reported == "THIN_TOP_BID" or size < quantity:
        thin_mark = (
            None if low is None else _mark(observed, bid, low, low_at, *mark_inputs)
        )
        return "thin", thin_mark
    if low is None or bid < low:
        low, low_at = bid, observed
    mark = _mark(observed, bid, low, low_at, *mark_inputs)
    return "valid", {**mark, "exchange_time_ms": exchange, "bid_size": size}


def _window_quality(start, end, poll, max_stale, max_gap, records, hold):
    valid_times = [observed for observed, status, _ in records if status == "valid"]
    slots = {(observed - start) // poll for observed in valid_times if observed < end}
    expected = (end - start + poll - 1) // poll
    boundaries = [start, *valid_times, end]
    gaps = [b - a for a, b in zip(boundaries, boundaries[1:])]
    long_gaps = [gap for gap in gaps if gap > max_gap]
    endpoint = (
        hold is not None
        and end - hold["observed_at_ms"] <= poll
        and end - hold["exchange_time_ms"] <= max_stale
    )
    if max(gaps) > 30_000:
        reason = "MAX_SINGLE_GAP_EXCEEDED"
    elif 100 * sum(long_gaps) > 2 * (end - start):
        reason = "CUMULATIVE_GAP_EXCEEDED"
    elif 100 * len(slots) < 98 * expected:
        reason = "INSUFFICIENT_VALID_POLLS"
    elif not endpoint:
        reason = "ENDPOINT_UNAVAILABLE"
    else:
        reason = None
    counts = Counter(status for _, status, _ in records)
    return {
        "window_valid": reason is None,
        "rejection_reason": reason,
        "total_polls_expected": expected,
        "valid_poll_slots": len(slots),
        "valid_quotes_count": counts["valid"],
        "stale_quotes_count": counts["stale"],
        "thin_quotes_count": counts["thin"],
        "unavailable_quotes_count": counts["unavailable"],
        "gap_count": len(long_gaps),
        "max_observed_gap_ms": max(gaps),
        "endpoint_quote_actionable": endpoint,
    }


def _rule_exit(records, times, rule, threshold, latency, max_gap, mark_inputs):
    misses = Counter()
    eligible_index = 0
    for index, (observed, status, trigger) in enumerate(records):
        if index < eligible_index or trigger is None or trigger[rule] < threshold:
            continue
        if status == "thin":
            misses["thin_trigger"] += 1
            continue
        misses["candidates"] += 1
        following = bisect_left(times, observed + latency, lo=index)
        if following == len(records):
            misses["execution_unavailable"] += 1
            break
        exec_time, exec_status, execution = records[following]
        if exec_time - observed > max_gap:
            misses["execution_unavailable"] += 1
            eligible_index = following
            continue
        if exec_status != "valid":
            misses["execution_unavailable"] += 1
            eligible_index = following + 1
            continue
        at_trigger_reference = _mark(
            exec_time,
            execution["bid_usd"],
            trigger["observed_low_bid_usd"],
            trigger["low_observed_at_ms"],
            *mark_inputs,
        )
        return {
            **at_trigger_reference,
            "trigger_quote": trigger,
            "execution_quote": execution,
            "threshold_held_at_exec": at_trigger_reference[rule] >= threshold,
        }, dict(misses)
    return None, dict(misses)


def _simulate_window(spec, inputs):
    if (
        spec.get("cost_basis_verified") is not True
        or _number(spec, "cost_basis_coverage_pct", allow_zero=True) != PERCENT
    ):
        raise ValueError("SKIPPED_UNVERIFIED_COST_BASIS")
    start = _integer(spec, "window_start_ms")
    end = _integer(spec, "window_end_ms", minimum=start + 1)
    poll = _integer(spec, "poll_interval_ms", minimum=1)
    latency = _integer(spec, "decision_latency_ms")
    max_stale = _integer(spec, "max_stale_ms")
    max_gap = _integer(spec, "max_gap_ms", minimum=max(1, latency))
    mark_inputs = _mark_inputs(inputs)
    records = []
    low = low_at = None
    for observed, quote in _ordered_quotes(spec.get("quotes"), allow_empty=True):
        if not start <= observed <= end:
            raise ValueError("quote receipt must fall inside the declared window")
        status, mark = _pilot_mark(
            quote, observed, inputs["quantity"], max_stale, low, low_at, mark_inputs
        )
        if status == "valid":
            low, low_at = mark["observed_low_bid_usd"], mark["low_observed_at_ms"]
        records.append((observed, status, mark))
    hold = records[-1][2] if records and records[-1][1] == "valid" else None
    quality = _window_quality(start, end, poll, max_stale, max_gap, records, hold)
    times = [observed for observed, _, _ in records]
    exits, diagnostics, comparisons = {}, {}, {}
    for rule, threshold in inputs["thresholds"].items():
        exit_mark, diagnostics[rule] = _rule_exit(
            records, times, rule, threshold, latency, max_gap, mark_inputs
        )
        exits[rule] = exit_mark
        if quality["window_valid"]:
            baseline = hold["estimated_net_proceeds_usd"]
            proceeds = (
                exit_mark["estimated_net_proceeds_usd"] if exit_mark else baseline
            )
            delta = proceeds - baseline
            comparisons[rule] = {
                "estimated_net_proceeds_usd": proceeds,
                "delta_vs_hold_usd": delta,
                "delta_vs_hold_bps": BPS * delta / baseline,
            }
        else:
            comparisons[rule] = None
    return {
        **inputs,
        "schema_version": PILOT_SCHEMA,
        "window_id": spec.get("window_id"),
        "data_quality": quality,
        "first_hypothetical_exits": exits,
        "hold_last_quote": hold if quality["endpoint_quote_actionable"] else None,
        "rule_diagnostics": diagnostics,
        "hold_comparison": comparisons,
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
