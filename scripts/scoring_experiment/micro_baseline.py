"""Causal baseline builder for the offline receipt-time replay contract."""

import math
import statistics
import hashlib
from pathlib import Path

from instant_targets import Baseline


def build_baseline(store, product, anchor, *, benchmark="BTC-USD"):
    if type(anchor) is not int or anchor % 5000:
        raise ValueError("anchor must be a 5s grid timestamp")
    sigma_end = (anchor - 35000) // 60000 * 60000
    sigma_start = sigma_end - 60 * 60000
    pace_end = anchor - 30000
    pace_start = pace_end - 120 * 30000
    provenance = dict(
        sigma_start_ts_ms=sigma_start,
        sigma_end_ts_ms=sigma_end,
        pace_start_ts_ms=pace_start,
        pace_end_ts_ms=pace_end,
        knowledge_asof_ts_ms=anchor,
        builder_version="instant-micro-baseline-v1-draft",
        builder_sha256=hashlib.sha256(
            Path(__file__).read_text(encoding="utf-8").encode("utf-8")
        ).hexdigest(),
        replay_contract_sha256=store.db.execute(
            "SELECT value FROM meta WHERE key='contract_sha256'"
        ).fetchone()[0],
    )
    for pid in (product, benchmark):
        if not store.coverage(pid, sigma_start - 5000, sigma_end, anchor)[0]:
            return dict(
                status="unavailable",
                reason="baseline_coverage",
                product=pid,
                **provenance
            )
    returns = {}
    for pid in (product, benchmark):
        snapshots = [
            store.snapshot(pid, t, asof=anchor)
            for t in range(sigma_start, sigma_end + 1, 60000)
        ]
        if any(r["mid"] is None or r["available_ts_ms"] > anchor for r in snapshots):
            return dict(
                status="unavailable",
                reason="baseline_quote_quality",
                product=pid,
                **provenance
            )
        returns[pid] = [
            math.log(b["mid"]) - math.log(a["mid"])
            for a, b in zip(snapshots, snapshots[1:])
        ]
    coin, btc = returns[product], returns[benchmark]
    coin_mean, btc_mean = statistics.fmean(coin), statistics.fmean(btc)
    variance = sum((r - btc_mean) ** 2 for r in btc)
    fallback = variance == 0
    beta = (
        1.0
        if fallback
        else sum((a - coin_mean) * (b - btc_mean) for a, b in zip(coin, btc)) / variance
    )
    sigma = statistics.stdev(coin)
    if not math.isfinite(beta) or not math.isfinite(sigma):
        return dict(status="unavailable", reason="nonfinite_baseline", **provenance)
    windows = [
        store.trades_window(product, t - 30000, t, asof=anchor)
        for t in range(pace_start + 30000, pace_end + 1, 30000)
    ]
    if any(
        not r["coverage_verified"] or r["available_ts_ms"] > anchor for r in windows
    ):
        return dict(status="unavailable", reason="pace_coverage", **provenance)
    value = Baseline(
        sigma_1m=sigma,
        beta=beta,
        return_count=len(coin),
        end_ts_ms=sigma_end,
        available_ts_ms=anchor,
        beta_available_ts_ms=anchor,
        beta_fallback=fallback,
        pace_trade_median_30s=statistics.median(r["trade_count"] for r in windows),
        pace_quote_usd_median_30s=statistics.median(
            r["quote_volume_usd"] for r in windows
        ),
        pace_window_count=len(windows),
        pace_end_ts_ms=pace_end,
        pace_available_ts_ms=anchor,
    )
    return dict(status="ready", reason=None, baseline=value, **provenance)
