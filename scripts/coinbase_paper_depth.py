"""Prototype: estimate paper sell proceeds across several bid levels.

The official pilot in ``coinbase_paper_exit`` marks a position against the
single best bid and discards any quote whose top-of-book size is smaller than
the position. A live 30 second BTC-USD window showed why that matters: the best
level alone was worth about ten dollars at its thinnest, so a $714 position was
classified thin on two polls and the window was rejected for insufficient valid
polls. The data was perfectly fresh; only the depth assumption failed.

This module is a separate paper-only prototype. It walks the bid side to
estimate what a market sell would realise, applies the pilot's fee and
slippage convention to that walk, and reports insufficient depth as an explicit
outcome rather than discarding the quote.

It never produces an official pilot result, whatever window it spans, and it
replays synthetic positions only. The official pilot's freshness and fill
limits are untouched: this module reuses the pilot's own staleness rule and
window quality function so the two cannot drift apart, and declares its own
schema so the two tapes cannot be confused.
"""

import argparse
from bisect import bisect_left
from collections import Counter
from decimal import Decimal, DecimalException
import json
from pathlib import Path
import re
import sys

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.paper_fills import (  # noqa: E402
    FILLED,
    INSUFFICIENT_BOOK_DEPTH,
    book_levels,
    estimate_sell_proceeds,
)
from scripts.coinbase_paper_exit import (  # noqa: E402
    BPS,
    PERCENT,
    RULES,
    _integer,
    _number,
    _window_quality,
)


DEPTH_SCHEMA = "depth-prototype-1"
# Why a synthetic depth run can never be an official pilot result.
NOT_OFFICIAL = "DEPTH_PROTOTYPE_IS_NOT_THE_OFFICIAL_PILOT"
# Quote outcomes. "priced" and "insufficient_depth" both carry a mark; the
# other two do not, because there is no book to price the position against.
PRICED = "priced"
INSUFFICIENT_DEPTH = INSUFFICIENT_BOOK_DEPTH
# How a depth outcome maps onto the pilot's window quality categories, so the
# coverage, gap and endpoint rules stay literally the pilot's own.
QUALITY_STATUS = {
    PRICED: "valid",
    INSUFFICIENT_DEPTH: "thin",
    "stale": "stale",
    "unavailable": "unavailable",
}


def _book_levels(quote):
    """Validate one quote's bid ladder with the shared rules."""
    return book_levels(quote.get("bids"))


def _depth_inputs(spec):
    if not isinstance(spec, dict):
        raise ValueError("scenario must be an object")
    if spec.get("schema_version") != DEPTH_SCHEMA:
        raise ValueError(f"depth prototype requires schema_version {DEPTH_SCHEMA}")
    if spec.get("synthetic_position") is not True:
        # There is no cost-basis verification here, so there is nothing to
        # stand behind an account-backed tape. Refuse it outright.
        raise ValueError("depth prototype replays synthetic positions only")
    product = spec.get("product_id")
    if not isinstance(product, str) or not re.fullmatch(r"[A-Z0-9]+-USD", product):
        raise ValueError("product_id must identify a USD spot pair")
    fee_bps = _number(spec, "exit_fee_bps", allow_zero=True)
    slip_bps = _number(spec, "slippage_bps", allow_zero=True)
    if max(fee_bps, slip_bps) >= BPS:
        raise ValueError("fee and slippage must be below 10000 basis points")
    thresholds = spec.get("thresholds")
    if not isinstance(thresholds, dict) or set(thresholds) != set(RULES):
        raise ValueError(f"thresholds must contain exactly {', '.join(RULES)}")
    return {
        "mode": "paper_depth_prototype",
        "synthetic_position": True,
        "product_id": product,
        "quantity": _number(spec, "quantity"),
        "entry_cost_usd": _number(spec, "entry_cost_usd"),
        "exit_fee_bps": fee_bps,
        "slippage_bps": slip_bps,
        "thresholds": {rule: _number(thresholds, rule) for rule in RULES},
    }


def _ordered(quotes):
    if not isinstance(quotes, list):
        raise ValueError("quotes must be a list")
    previous = -1
    for quote in quotes:
        if not isinstance(quote, dict):
            raise ValueError("each quote must be an object")
        observed = quote.get("observed_at_ms")
        if type(observed) is not int or observed <= previous:
            raise ValueError("quote times must be nonnegative and strictly increasing")
        previous = observed
        yield observed, quote


def _depth_mark(observed, exchange, fill, low, low_at, cost, quantity):
    """Price signals and proceeds from what the position could actually get.

    The running low, both rebound rules and net profit all use the executable
    depth-weighted price for the full position size, not the top bid: a
    tiny order at the top of the book is not a price a real exit receives.
    A quote whose book cannot cover the position has no executable price, so
    every rule reads None and it can neither trigger nor set the low.
    """
    top = fill["top_bid_usd"]
    executable = fill["estimated_vwap_usd"]
    net = fill["estimated_net_proceeds_usd"]
    priced = executable is not None and low is not None
    return {
        "observed_at_ms": observed,
        "exchange_time_ms": exchange,
        "top_bid_usd": top,
        "bid_usd": top,
        "executable_price_usd": executable,
        "observed_low_bid_usd": low,
        "low_observed_at_ms": low_at,
        "rebound_usd": (executable - low) * quantity if priced else None,
        "rebound_pct": PERCENT * (executable - low) / low if priced else None,
        "estimated_net_proceeds_usd": net,
        "estimated_pnl_usd": None if net is None else net - cost,
        "net_profit_pct": None if net is None else PERCENT * (net - cost) / cost,
        "depth": fill,
    }


def _depth_quote(quote, observed, inputs, max_stale, fee, slip, low, low_at):
    reported = quote.get("quote_status", "VALID")
    if reported == "UNAVAILABLE":
        return "unavailable", None
    if reported == "STALE":
        return "stale", None
    if reported != "VALID":
        raise ValueError("unknown quote_status")
    exchange = _integer(quote, "exchange_time_ms")
    # The pilot's freshness rule, unchanged.
    if not 0 <= observed - exchange <= max_stale:
        return "stale", None
    fill = estimate_sell_proceeds(
        _book_levels(quote), inputs["quantity"], fee_rate=fee, slippage_rate=slip
    )
    if fill["status"] == FILLED:
        executable = fill["estimated_vwap_usd"]
        # Only a quote that could fill the whole position may set the low.
        if low is None or executable < low:
            low, low_at = executable, observed
    mark = _depth_mark(
        observed, exchange, fill, low, low_at,
        inputs["entry_cost_usd"], inputs["quantity"],
    )
    status = PRICED if fill["status"] == FILLED else INSUFFICIENT_DEPTH
    return status, mark


def _depth_rule_exit(records, times, rule, threshold, latency, max_gap,
                     cost, quantity):
    """First executable exit, plus what became of the first trigger.

    Carries over the two corrections the pilot already makes: an execution
    book that is not newer than the trigger's proves nothing about the book
    after the decision delay, and a trigger whose execution quote is missing
    or unusable leaves the order's outcome unknown even if a later trigger
    executes.
    """
    misses = Counter()
    first = None
    eligible_index = 0
    for index, (observed, status, mark) in enumerate(records):
        if index < eligible_index or mark is None:
            continue
        value = mark.get(rule)
        if value is None or value < threshold:
            continue
        if status != PRICED:
            continue
        misses["candidates"] += 1
        following = bisect_left(times, observed + latency, lo=index)
        exec_observed = execution = None
        if following == len(records):
            reason, counter = "NO_QUOTE_AFTER_DELAY", "execution_unavailable"
        else:
            exec_observed, exec_status, execution = records[following]
            if exec_observed - observed > max_gap:
                reason, counter = "QUOTE_GAP_EXCEEDED", "execution_unavailable"
                eligible_index = following
            elif exec_status == "unavailable":
                reason, counter = "QUOTE_UNAVAILABLE", "execution_unavailable"
                eligible_index = following + 1
            elif exec_status == "stale":
                reason, counter = "QUOTE_STALE", "execution_unavailable"
                eligible_index = following + 1
            elif exec_status == INSUFFICIENT_DEPTH:
                reason = "EXECUTION_INSUFFICIENT_DEPTH"
                counter = "execution_insufficient_depth"
                eligible_index = following + 1
            elif latency and execution["exchange_time_ms"] <= mark["exchange_time_ms"]:
                reason = "BOOK_NOT_AFTER_TRIGGER"
                counter = "execution_book_not_after_trigger"
                eligible_index = following
            else:
                reason = None
        if reason is not None:
            misses[counter] += 1
            if first is None:
                first = {
                    "status": "missed",
                    "reason": reason,
                    "trigger_quote": mark,
                    "execution_observed_at_ms": exec_observed,
                }
            if following == len(records):
                break
            continue
        # As in the pilot, re-measure the execution book from the low the
        # trigger saw. The running low can fall between trigger and execution,
        # and measuring from that later low would report a rebound the
        # trigger's decision never relied on.
        at_trigger_reference = _depth_mark(
            exec_observed,
            execution["exchange_time_ms"],
            execution["depth"],
            mark["observed_low_bid_usd"],
            mark["low_observed_at_ms"],
            cost,
            quantity,
        )
        exit_mark = {
            **at_trigger_reference,
            "trigger_quote": mark,
            "execution_quote": execution,
            "threshold_held_at_exec": at_trigger_reference[rule] >= threshold,
            "prior_missed_executions": misses["candidates"] - 1,
        }
        if first is None:
            first = {"status": "executed"}
        return exit_mark, {**misses, "first_execution": first}
    return None, {**misses, "first_execution": first or {"status": "none"}}


def simulate_depth_exit(spec):
    """Replay a synthetic depth tape. Never an official pilot result."""
    inputs = _depth_inputs(spec)
    start = _integer(spec, "window_start_ms")
    end = _integer(spec, "window_end_ms", minimum=start + 1)
    poll = _integer(spec, "poll_interval_ms", minimum=1)
    latency = _integer(spec, "decision_latency_ms")
    max_stale = _integer(spec, "max_stale_ms")
    max_gap = _integer(spec, "max_gap_ms", minimum=max(1, latency))
    fee = inputs["exit_fee_bps"] / BPS
    slip = inputs["slippage_bps"] / BPS

    records = []
    low = low_at = None
    for observed, quote in _ordered(spec.get("quotes")):
        if not start <= observed <= end:
            raise ValueError("quote receipt must fall inside the declared window")
        status, mark = _depth_quote(
            quote, observed, inputs, max_stale, fee, slip, low, low_at
        )
        if status == PRICED:
            low, low_at = mark["observed_low_bid_usd"], mark["low_observed_at_ms"]
        records.append((observed, status, mark))

    hold = records[-1][2] if records and records[-1][1] == PRICED else None
    quality = _window_quality(
        start, end, poll, max_stale, max_gap,
        [(observed, QUALITY_STATUS[status], mark) for observed, status, mark in records],
        hold,
    )
    quality["insufficient_depth_quotes_count"] = quality.pop("thin_quotes_count")
    times = [observed for observed, _, _ in records]

    exits, diagnostics, comparisons, statuses = {}, {}, {}, {}
    for rule, threshold in inputs["thresholds"].items():
        exit_mark, diagnostics[rule] = _depth_rule_exit(
            records, times, rule, threshold, latency, max_gap,
            inputs["entry_cost_usd"], inputs["quantity"],
        )
        exits[rule] = exit_mark
        comparisons[rule] = None
        if not quality["window_valid"]:
            statuses[rule] = "WINDOW_INVALID"
        elif diagnostics[rule]["first_execution"]["status"] == "missed":
            statuses[rule] = "FIRST_EXECUTION_UNKNOWN"
        else:
            statuses[rule] = "AVAILABLE"
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
    return {
        **inputs,
        "schema_version": DEPTH_SCHEMA,
        "window_id": spec.get("window_id"),
        "declared_settings": {
            "poll_interval_ms": poll,
            "decision_latency_ms": latency,
            "max_stale_ms": max_stale,
            "max_gap_ms": max_gap,
        },
        # A synthetic depth run is never official, whatever window it spans.
        "official_pilot_result": False,
        "official_pilot_result_blocked_reason": NOT_OFFICIAL,
        "data_quality": quality,
        "first_hypothetical_exits": exits,
        "hold_last_quote": hold if quality["endpoint_quote_actionable"] else None,
        "rule_diagnostics": diagnostics,
        "hold_comparison": comparisons,
        "hold_comparison_status": statuses,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scenario", type=Path, help="Synthetic depth tape JSON")
    args = parser.parse_args()
    try:
        with args.scenario.open(encoding="utf-8-sig") as source:
            spec = json.load(source, parse_float=Decimal)
        result = simulate_depth_exit(spec)
    except (OSError, ValueError, DecimalException) as error:
        parser.exit(2, f"{parser.prog}: {error}\n")
    print(json.dumps(result, default=str, indent=2))


if __name__ == "__main__":
    main()
