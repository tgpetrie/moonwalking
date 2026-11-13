"""Backfill a separate, resumable public Coinbase candle archive for Radar."""

import argparse
import json
import sqlite3
import sys
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from live_movers_run import CAPTURE, digest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

import candle_archive

MOONWALKING = Path.home() / ".moonwalking"
DEFAULT_OUTPUT = MOONWALKING / "analysis/radar_candle_backfill_20261113"
START = int(datetime(2026, 10, 12, 18, tzinfo=timezone.utc).timestamp())
PRODUCT_SOURCES = (
    (MOONWALKING / "data/candle_archive.sqlite", "candles"),
    (CAPTURE / "board_episodes.sqlite", "episodes"),
    (
        MOONWALKING
        / "analysis/live_movers_fresh_replication_20261113/board_episodes.sqlite",
        "episodes",
    ),
    (MOONWALKING / "data/signal_outcomes.sqlite", "board_outcomes_v2"),
)


def roster():
    products = set(candle_archive.usd_products())
    for path, table in PRODUCT_SOURCES:
        with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)) as db:
            products.update(
                row[0]
                for row in db.execute(
                    f"SELECT DISTINCT product_id FROM {table} WHERE product_id LIKE '%-USD'"
                )
            )
    return sorted(products, key=lambda product: (product != "BTC-USD", product))


def write_json(path, payload):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def manifest(db, products, end):
    windows = {start for start, _ in candle_archive.windows(START, end, 60)}
    coverage = {product: {"ok": 0, "empty": 0, "not_found": 0} for product in products}
    for product, start, status, candles in db.execute(
        """SELECT product_id, window_start, status, candles
           FROM fetched_windows WHERE granularity = 60"""
    ):
        if product not in coverage or start not in windows:
            continue
        bucket = "empty" if status == "ok" and candles == 0 else status
        coverage[product][bucket] += 1
    return {
        "range_start_utc": datetime.fromtimestamp(START, timezone.utc).isoformat(),
        "range_end_open_utc": datetime.fromtimestamp(end, timezone.utc).isoformat(),
        "products": len(products),
        "expected_windows_per_product": len(windows),
        "candles_in_range": db.execute(
            "SELECT count(*) FROM candles WHERE granularity=60 AND ts>=? AND ts<=?",
            (START, end),
        ).fetchone()[0],
        "coverage_by_product": {
            product: dict(counts, unrecorded=len(windows) - sum(counts.values()))
            for product, counts in coverage.items()
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--rate", type=float, default=2.0, choices=(1.0, 2.0))
    parser.add_argument("--product-limit", type=int)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    roster_path = args.output / "ROSTER.json"
    if roster_path.is_file():
        products = json.loads(roster_path.read_text(encoding="utf-8"))
    else:
        products = roster()
        write_json(roster_path, products)
    if args.product_limit is not None:
        if args.product_limit < 1:
            parser.error("--product-limit must be positive")
        products = products[: args.product_limit]
    now = int(datetime.now(timezone.utc).timestamp())
    end = now // 18000 * 18000 - 60
    path = args.output / "radar_candles.sqlite"
    print(
        f"{len(products)} products, up to {args.rate:g} public requests/s", flush=True
    )
    with closing(candle_archive.connect(str(path))) as db:
        stats = candle_archive.run(
            db,
            products,
            60,
            START,
            end,
            pacer=candle_archive.Pacer(rate=args.rate),
            note="Radar archived candle backfill",
            progress=lambda i, total, product, stats: print(
                f"{i}/{total} {product} requests={stats.requests} "
                f"candles={stats.candles_written} errors={stats.errors}",
                flush=True,
            ),
        )
        results = manifest(db, products, end)
        results["requests"] = stats.requests
        results["errors"] = stats.errors
        results["rate_limited"] = stats.rate_limited
        db.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    results["archive_sha256"] = digest(path)
    write_json(args.output / "MANIFEST.json", results)
    print(f"Manifest written to {args.output / 'MANIFEST.json'}", flush=True)


if __name__ == "__main__":
    main()
