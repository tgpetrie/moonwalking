"""Compute offline baseline components from the timed input ledger."""

from dataclasses import asdict
from decimal import Decimal, DecimalException
import hashlib
import math
from pathlib import Path
import statistics

from instant_coverage import _integer
from instant_input_evidence import BENCHMARK, GRID_MS, _json, _sha


VERSION = "instant-timed-baseline-v1-draft"
MINUTE_MS = 60000
PACE_MS = 30000
RETURN_COUNT = 60
PACE_COUNT = 120


def _volatility(recorder, product, start, end, asof):
    if start < GRID_MS:
        return dict(status="unavailable", reason="insufficient_history")
    if end > asof:
        return dict(status="unavailable", reason="window_not_closed")

    availability, returns = [], {}
    for pid in dict.fromkeys((product, BENCHMARK)):
        # Include the bucket preceding the first close, as in micro_baseline.
        _, _, reason, available = recorder._trade_window(
            pid, start - GRID_MS, end, asof
        )
        if reason:
            return dict(status="unavailable", reason=reason, product_id=pid)
        availability.append(available)
        closes = []
        for cutoff in range(start, end + 1, MINUTE_MS):
            quote, available = recorder._quote_at(pid, cutoff, asof)
            if not quote["available"]:
                return dict(
                    status="unavailable",
                    reason=quote["reason"],
                    product_id=pid,
                    missing_close_ts_ms=cutoff,
                )
            bid, ask = float(quote["bid"]), float(quote["ask"])
            closes.append(math.log(bid + (ask - bid) / 2))
            availability.append(available)
        returns[pid] = [b - a for a, b in zip(closes, closes[1:])]

    coin, btc = returns[product], returns[BENCHMARK]
    coin_mean, btc_mean = statistics.fmean(coin), statistics.fmean(btc)
    variance = sum((value - btc_mean) ** 2 for value in btc)
    fallback = variance == 0
    beta = (
        1.0
        if fallback
        else (
            sum((a - coin_mean) * (b - btc_mean) for a, b in zip(coin, btc)) / variance
        )
    )
    sigma = statistics.stdev(coin)
    if not math.isfinite(beta) or not math.isfinite(sigma):
        return dict(status="unavailable", reason="nonfinite_baseline")
    return dict(
        status="ready",
        inputs_available_ts_ms=max(availability),
        return_count=len(coin),
        sigma_1m=sigma,
        beta=beta,
        beta_fallback=fallback,
    )


def _pace(recorder, product, start, end, asof):
    if start < 0:
        return dict(status="unavailable", reason="insufficient_history")
    if end > asof:
        return dict(status="unavailable", reason="window_not_closed")
    # A single certified chain covers the entire interval, including every
    # empty subwindow. Receipts are then assigned to half-open 30s bins.
    _, trades, reason, available = recorder._trade_window(product, start, end, asof)
    if reason:
        return dict(status="unavailable", reason=reason, product_id=product)
    counts, amounts = [0] * PACE_COUNT, [Decimal(0)] * PACE_COUNT
    try:
        for trade in trades:
            index = (trade.receipt_ts_ms - start) // PACE_MS
            counts[index] += 1
            amounts[index] += Decimal(trade.price) * Decimal(trade.size)
        median = statistics.median(amounts)
    except DecimalException:
        return dict(status="unavailable", reason="invalid_quote_amount")
    if not median.is_finite():
        return dict(status="unavailable", reason="invalid_quote_amount")
    return dict(
        status="ready",
        inputs_available_ts_ms=available,
        window_count=PACE_COUNT,
        pace_trade_median_30s=statistics.median(counts),
        pace_quote_usd_median_30s=str(median),
    )


def build_timed_baseline(recorder, product, cutoff, *, asof):
    """Assess independent volatility and pace components for a declared slot.

    Windows end before cutoff, so a baseline may finish ahead of the slot.
    The evidence as-of is an input limit and completion uses the recorder clock.
    """
    _integer(cutoff)
    _integer(asof)
    if recorder.failed:
        raise ValueError("failed evidence recorder")
    if product not in recorder.products or cutoff not in recorder.cutoffs:
        raise ValueError("product/cutoff outside declared inventory")
    if asof < recorder.inventory_recorded_ts_ms:
        raise ValueError("inventory was not yet recorded at baseline evidence time")
    if asof > recorder._now():
        raise ValueError("baseline evidence time has not been reached")

    sigma_end = (cutoff - 35000) // MINUTE_MS * MINUTE_MS
    sigma_start = sigma_end - RETURN_COUNT * MINUTE_MS
    pace_end = cutoff - PACE_MS
    pace_start = pace_end - PACE_COUNT * PACE_MS
    volatility = _volatility(recorder, product, sigma_start, sigma_end, asof)
    pace = _pace(recorder, product, pace_start, pace_end, asof)
    prefix = hashlib.sha256()
    known_packets = 0
    for packet in recorder.packets:
        if packet.available_ts_ms > asof:
            break
        prefix.update((_json(asdict(packet)) + "\n").encode("utf-8"))
        known_packets += 1

    result = dict(
        version=VERSION,
        product_id=product,
        benchmark=BENCHMARK,
        feature_cutoff_ts_ms=cutoff,
        knowledge_asof_ts_ms=asof,
        sigma_start_ts_ms=sigma_start,
        sigma_end_ts_ms=sigma_end,
        pace_start_ts_ms=pace_start,
        pace_end_ts_ms=pace_end,
        volatility=volatility,
        pace=pace,
        inventory_sha256=recorder.inventory_sha256,
        inventory_recorded_ts_ms=recorder.inventory_recorded_ts_ms,
        known_packet_count=known_packets,
        known_packet_prefix_sha256=prefix.hexdigest(),
        input_implementation_sha256=recorder.source_sha256,
        input_contract_sha256=recorder.contract_sha256,
        book_implementation_sha256=recorder.book.source_sha256,
        book_contract_sha256=recorder.book.contract_sha256,
        monitor_implementation_sha256=recorder.book.monitor.source_sha256,
        monitor_contract_sha256=recorder.book.monitor.contract_sha256,
        builder_sha256=_sha(Path(__file__).read_text(encoding="utf-8").encode("utf-8")),
        scope="offline_baseline_components",
        fitting_allowed=False,
    )
    result["computation_completed_ts_ms"] = recorder._now()
    return result
