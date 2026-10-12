"""Archive raw Coinbase candles into the separate candle archive.

Examples (times without a zone are local time):

  # Show the periods the collector missed
  python scripts/archive_candles.py --list-gaps

  # Hourly candles for every gap, then 1-minute candles for one week
  python scripts/archive_candles.py --gaps --granularity 3600
  python scripts/archive_candles.py --start 2026-10-05T10:00 --end 2026-10-12T10:00

Safe to stop and re-run: windows already archived are skipped. Rows go to
MW_CANDLE_ARCHIVE_DB (see backend/candle_archive.py), never to a live store.
See docs/developer/CANDLE_ARCHIVE.md.
"""

from __future__ import annotations

import argparse
import datetime as dt
import os
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

import candle_archive  # noqa: E402

# Pad each gap so returns for rows that were still open when collection
# stopped (up to a 60-minute horizon) can be recomputed from the archive.
GAP_PAD_SECONDS = 70 * 60


def parse_time(value: str) -> int:
    parsed = dt.datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.astimezone()  # local time
    return int(parsed.timestamp())


def fmt(ts: int) -> str:
    return dt.datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")


def outcomes_db() -> str:
    return os.getenv("MW_BOARD_OUTCOMES_DB") or str(BACKEND / "data" / "signal_outcomes.sqlite")


def known_products(db: str) -> set[str]:
    try:
        conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        try:
            return {r[0] for r in conn.execute("SELECT DISTINCT product_id FROM board_outcomes_v2")}
        finally:
            conn.close()
    except sqlite3.Error:
        return set()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    span = parser.add_mutually_exclusive_group(required=True)
    span.add_argument("--list-gaps", action="store_true", help="print collection gaps and exit")
    span.add_argument("--gaps", action="store_true", help="archive every collection gap (padded 70 min each side)")
    span.add_argument("--start", help="range start, ISO time")
    parser.add_argument("--end", help="range end, ISO time (default: now)")
    parser.add_argument("--granularity", type=int, default=60, choices=candle_archive.GRANULARITIES)
    parser.add_argument("--products", help="comma-separated product ids (default: all USD products)")
    parser.add_argument("--rate", type=float, default=2.0, help="max requests per second (default 2)")
    parser.add_argument("--db", default=None, help="archive path (default: MW_CANDLE_ARCHIVE_DB)")
    parser.add_argument("--outcomes-db", default=None, help="board outcome store used to find gaps")
    args = parser.parse_args()

    source_db = args.outcomes_db or outcomes_db()
    if args.list_gaps or args.gaps:
        gaps = candle_archive.collection_gaps(source_db)
        if args.list_gaps:
            for a, b in gaps:
                print(f"{fmt(a)} -> {fmt(b)}  ({(b - a) / 86400:.2f} days)")
            return 0
        ranges = [(a - GAP_PAD_SECONDS, b + GAP_PAD_SECONDS) for a, b in gaps]
    else:
        end = parse_time(args.end) if args.end else int(dt.datetime.now().timestamp())
        ranges = [(parse_time(args.start), end)]

    if args.products:
        products = sorted({p.strip().upper() for p in args.products.split(",") if p.strip()})
    else:
        products = sorted(set(candle_archive.usd_products()) | known_products(source_db))

    conn = candle_archive.connect(args.db)
    pacer = candle_archive.Pacer(rate=args.rate)
    print(f"archive: {args.db or candle_archive.default_path()}")
    print(f"{len(products)} products, granularity {args.granularity}s, {len(ranges)} range(s), <= {args.rate}/s")

    def progress(i, total, product_id, stats):
        if i % 10 == 0 or i == total:
            print(f"  {i}/{total} {product_id}: requests={stats.requests} candles={stats.candles_written} "
                  f"skipped={stats.windows_skipped} 429={stats.rate_limited} errors={stats.errors}", flush=True)

    for start, end in ranges:
        print(f"range {fmt(start)} -> {fmt(end)}", flush=True)
        stats = candle_archive.run(
            conn, products, args.granularity, start, end, pacer=pacer, progress=progress,
            note=f"{fmt(start)} -> {fmt(end)}",
        )
        print(f"done: {stats}", flush=True)
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
