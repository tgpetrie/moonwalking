"""Reproduce a conservative funding-to-Coinbase mapping screen from saved public evidence.

No network calls or application imports. Reads the immutable checkpoint, verifies
the captured-response hashes, and writes audit products beside those responses.
Price correspondence corroborates economic identity; it is not on-chain identity proof.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import statistics
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import freeze_daily_panel as frozen

DAY_MS = 86_400_000
BAR_MS = 30 * DAY_MS
FACTORS = {"BONK": 1000, "FLOKI": 1000, "PEPE": 1000, "SHIB": 1000}
THRESHOLDS = {"minimum_closes": 6, "minimum_return_pairs": 4,
              "maximum_relative_error": 0.1, "minimum_close_pass_fraction": 0.9,
              "minimum_return_correlation": 0.95}


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def compare(bars, coinbase, factor, cutoff_ms, delisted=False):
    """Compare complete 30-day HL closes with Coinbase daily closes at the exact end.

    Ignore zero-trade backfilled candles, unfinished windows, and the final
    returned delisted-market window, which may contain only partial trading.
    """
    kept, dropped = [], Counter()
    final_start = max((int(b["t"]) for b in bars), default=None)
    for b in bars:
        t, end = int(b["t"]), int(b["T"])
        if end + 1 - t != BAR_MS or (end + 1) % DAY_MS:
            dropped["unexpected_interval_or_end_alignment"] += 1
            continue
        if end >= cutoff_ms:
            dropped["ends_after_frozen_panel"] += 1
            continue
        if int(b["n"]) <= 0 or float(b["v"]) <= 0:
            dropped["zero_trade_or_volume_bar"] += 1
            continue
        if delisted and t == final_start:
            dropped["possibly_partial_delisting_window"] += 1
            continue
        cb_day = (end // DAY_MS) * 86400
        candle = coinbase.get(cb_day)
        if candle is None:
            dropped["coinbase_close_missing"] += 1
            continue
        cb_close, hl_close = float(candle[4]), float(b["c"])
        if not (math.isfinite(cb_close) and math.isfinite(hl_close)
                and cb_close > 0 and hl_close > 0):
            raise ValueError("Nonpositive/nonfinite comparison price")
        ratio = hl_close / factor / cb_close
        kept.append({"hl_start_ms": t, "hl_end_ms": end,
                     "coinbase_date": datetime.fromtimestamp(cb_day, timezone.utc).date().isoformat(),
                     "hl_close": hl_close, "coinbase_close": cb_close,
                     "ratio_after_fixed_conversion": ratio, "relative_error": abs(ratio - 1)})
    kept.sort(key=lambda b: b["hl_start_ms"])
    returns = [(math.log(b["hl_close"] / a["hl_close"]),
                math.log(b["coinbase_close"] / a["coinbase_close"]))
               for a, b in zip(kept, kept[1:]) if b["hl_start_ms"] - a["hl_start_ms"] == BAR_MS]
    correlation = None
    if len(returns) >= 2:
        try:
            correlation = statistics.correlation(*zip(*returns))
        except statistics.StatisticsError:
            pass
    fraction = sum(b["relative_error"] <= THRESHOLDS["maximum_relative_error"] for b in kept) / len(kept) if kept else None
    enough = len(kept) >= THRESHOLDS["minimum_closes"] and len(returns) >= THRESHOLDS["minimum_return_pairs"]
    passed = enough and fraction >= THRESHOLDS["minimum_close_pass_fraction"] and correlation is not None and correlation >= THRESHOLDS["minimum_return_correlation"]
    return {"screen_pass": bool(passed), "status": "price_correspondence_pass" if passed else
            ("hold_short_or_nonoverlapping_history" if not enough else "hold_price_correspondence_failed"),
            "common_complete_closes": len(kept), "consecutive_return_pairs": len(returns),
            "fraction_within_10pct": fraction, "return_correlation": correlation,
            "median_ratio_after_fixed_conversion": statistics.median(b["ratio_after_fixed_conversion"] for b in kept) if kept else None,
            "dropped_bars": dict(dropped), "comparisons": kept}


def audit(checkpoint: Path, evidence: Path):
    verification = frozen.verify(checkpoint)
    candidates = read(checkpoint / "metadata" / "funding_candidates.json")
    for record in read(evidence / "SOURCE_MANIFEST.json"):
        if "error" in record or sha(evidence / (record["name"] + ".json")) != record["sha256"]:
            raise ValueError("Missing or changed public metadata response")
    records = read(evidence / "MONTHLY_PRICE_MANIFEST.json")
    if len(records) != len(candidates) or {r["base"] for r in records} != set(candidates):
        raise ValueError("Incomplete or duplicated candidate response manifest")
    for record in records:
        if "error" in record or sha(evidence / "monthly_prices" / (record["base"] + ".json")) != record["sha256"]:
            raise ValueError("Missing or changed monthly response")
    raw, _ = frozen.inspect_panel(checkpoint / "raw")
    currencies = {r["id"]: r for r in read(evidence / "coinbase_currencies.json")}
    products = {r["id"]: r for r in read(evidence / "coinbase_products.json")}
    meta, contexts = read(evidence / "hyperliquid_meta_contexts.json")
    markets = {r["name"]: r for r in meta["universe"]}
    cutoff_ms = (max(t for candles in raw.values() for t in candles) + 86400) * 1000
    rows = []
    for symbol, candidate in candidates.items():
        pid, hl_name = symbol + "-USD", candidate["hl_name"]
        cb, market = currencies[symbol], markets[hl_name]
        if pid not in products or products[pid]["base_currency"] != symbol:
            raise ValueError("Coinbase product identity absent or inconsistent")
        factor = FACTORS.get(symbol, 1)
        if hl_name != ("k" + symbol if factor == 1000 else symbol):
            raise ValueError("Unreviewed contract alias")
        result = compare(read(evidence / "monthly_prices" / (symbol + ".json")), raw[pid], factor,
                         cutoff_ms, bool(market.get("isDelisted", False)))
        result.update(product_id=pid, coinbase_name=cb["name"], coinbase_network=cb.get("default_network"),
                      coinbase_contracts={r["id"]: r.get("contract_address") for r in cb.get("supported_networks", [])},
                      hyperliquid_name=hl_name, hyperliquid_delisted=bool(market.get("isDelisted", False)),
                      price_units_per_contract=factor, funding_rate_multiplier=1,
                      candidate_first_ts_unverified=candidate["first_ts"], benchmark_only=(symbol == "BTC"),
                      admissible_for_primary_research=(result["screen_pass"] and symbol != "BTC"))
        rows.append(result)
    result = {"baseline_reviewed": "5f489a942b59a12fdac104acd53153561408b9fd", "method_version": "M1",
              "input_manifest_sha256": sha(checkpoint / "MANIFEST.json"), "checkpoint_verification": verification,
              "thresholds": THRESHOLDS, "candidate_count": len(rows),
              "status_counts": dict(Counter(r["status"] for r in rows)),
              "admissible_count_excluding_benchmark": sum(r["admissible_for_primary_research"] for r in rows),
              "limitations": ["Price-correspondence QA corroborates economic identity; no claim of on-chain identity proof.",
                              "Current metadata is not point-in-time historical availability.",
                              "Monthly price coverage does not establish funding coverage or listing dates.",
                              "Admissibility is conditional on exact funding/date availability and existing baseline eligibility."],
              "candidates": rows}
    (evidence / "IDENTITY_AUDIT.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    fields = ["product_id", "coinbase_name", "hyperliquid_name", "price_units_per_contract", "funding_rate_multiplier",
              "hyperliquid_delisted", "status", "common_complete_closes", "consecutive_return_pairs",
              "fraction_within_10pct", "return_correlation", "median_ratio_after_fixed_conversion",
              "benchmark_only", "admissible_for_primary_research"]
    with (evidence / "CANDIDATE_MAP.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    approved = {r["product_id"]: {k: r[k] for k in ["hyperliquid_name", "price_units_per_contract",
                "funding_rate_multiplier", "hyperliquid_delisted"]}
                for r in rows if r["admissible_for_primary_research"]}
    (evidence / "APPROVED_FUNDING_MAP.json").write_text(json.dumps(approved, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: result[k] for k in ["candidate_count", "status_counts", "admissible_count_excluding_benchmark"]}, indent=2))
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    args = parser.parse_args()
    audit(args.checkpoint, args.evidence)
