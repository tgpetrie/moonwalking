"""Create a separate, scoped research export using public Coinbase OHLCV.

No credentials, local runtime databases, or production writes. Raw HTTP
responses are cached for audit/replay. Missing candles are never filled.
"""

import argparse
from collections import Counter
from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, quote
from urllib.request import Request, urlopen

from evaluate_trade_hypotheses import HOUR, candle_from_row, load_export


def fetch_window(product, start, end, cache_dir, *, granularity_seconds=HOUR):
    if granularity_seconds not in (900, HOUR):
        raise ValueError("Only native 15m and hourly candles supported")
    suffix = "" if granularity_seconds == HOUR else f"-g{granularity_seconds}"
    cache = Path(cache_dir) / f"{product}-{start}-{end}{suffix}.json"
    if cache.exists():
        response = json.loads(cache.read_text(encoding="utf-8"))
    else:
        params = urlencode(
            {
                "granularity": granularity_seconds,
                "start": datetime.fromtimestamp(start, timezone.utc).isoformat(),
                "end": datetime.fromtimestamp(end, timezone.utc).isoformat(),
            }
        )
        url = f"https://api.exchange.coinbase.com/products/{quote(product, safe='')}/candles?{params}"
        for attempt in range(4):
            try:
                with urlopen(
                    Request(url, headers={"User-Agent": "BHABIT-offline-research/1"}),
                    timeout=30,
                ) as handle:
                    body = handle.read()
                break
            except HTTPError as error:
                if error.code not in (429, 500, 502, 503, 504) or attempt == 3:
                    raise
                time.sleep(2**attempt)
            except URLError:
                if attempt == 3:
                    raise
                time.sleep(2**attempt)
        payload = json.loads(body)
        if not isinstance(payload, list):
            raise ValueError("Expected a candle array")
        response = {
            "url": url,
            "fetched_ts": int(time.time()),
            "body_sha256": hashlib.sha256(body).hexdigest(),
            "candles": payload,
        }
        cache.parent.mkdir(parents=True, exist_ok=True)
        with cache.open("x", encoding="utf-8") as handle:
            json.dump(response, handle)
        time.sleep(0.35)
    rows = []
    for values in response["candles"]:
        if len(values) != 6:
            raise ValueError("Unexpected candle schema")
        ts, low, high, open_, close, volume = values
        # Coinbase can return candles before the requested start.
        if not start <= ts < end or ts + granularity_seconds > response["fetched_ts"]:
            continue
        row = {
            "kind": "candle",
            "product_id": product,
            "candle_ts": ts,
            "granularity_seconds": granularity_seconds,
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "base_volume": volume,
            "source": "coinbase_exchange_ohlcv",
        }
        if granularity_seconds == HOUR:
            row["hour_ts"] = ts  # Compatibility for existing hourly exports.
        if candle_from_row(row, granularity_seconds=granularity_seconds) is None:
            raise ValueError("Malformed exchange candle")
        rows.append(row)
    return rows


def backfill(input_path, output_path, products, cache_dir, *, granularity_seconds=HOUR):
    if Path(output_path).exists():
        raise FileExistsError("Choose a new export path")
    if not products or any(
        not p.endswith("-USD") or not p[:-4].isalnum() for p in products
    ):
        raise ValueError("Explicit Coinbase USD product ids are required")
    signals, _, audit, manifest = load_export(input_path)
    selected = {key: row for key, row in signals.items() if key[0] in products}
    if not selected:
        raise ValueError("No signals for requested products")
    start = min(ts for _, ts in selected) - 72 * HOUR
    end = min(
        max(ts for _, ts in selected) + 24 * HOUR,
        manifest["captured_ts"] // HOUR * HOUR,
    )
    rows = {}
    for product in sorted(set(products)):
        for window_start in range(start, end, 299 * granularity_seconds):
            for row in fetch_window(
                product,
                window_start,
                min(end, window_start + 299 * granularity_seconds),
                cache_dir,
                granularity_seconds=granularity_seconds,
            ):
                key = (row["product_id"], row["candle_ts"])
                if key in rows and rows[key] != row:
                    raise ValueError("Conflicting exchange candles")
                rows[key] = row
        print(
            json.dumps(
                {"product": product, "candles": sum(p == product for p, _ in rows)}
            ),
            flush=True,
        )
    with open(input_path, "rb") as source:
        input_hash = hashlib.file_digest(source, "sha256").hexdigest()
    manifest.update(
        {
            "parent_sha256": input_hash,
            "parent_audit": audit,
            "pilot_products": sorted(set(products)),
            "backfilled_ts": int(time.time()),
            "candle_source": "coinbase_exchange_ohlcv",
            "candle_granularity_seconds": granularity_seconds,
            "raw_response_cache": str(Path(cache_dir).resolve()),
        }
    )
    counts = Counter()
    with gzip.open(output_path, "xt", encoding="utf-8") as output:
        output.write(json.dumps({"kind": "manifest", **manifest}) + "\n")
        # Preserve the source transitions for the pilot, not just winners of
        # deduplication; the loader applies the same policy again.
        with gzip.open(input_path, "rt", encoding="utf-8") as source:
            for line in source:
                row = json.loads(line)
                if row["kind"] == "signal" and row["product_id"] in products:
                    output.write(line)
                    counts["signal"] += 1
        for _, row in sorted(rows.items()):
            output.write(json.dumps(row) + "\n")
            counts["candle"] += 1
        output.write(json.dumps({"kind": "counts", **counts}) + "\n")
    return dict(counts)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--products", required=True, nargs="+")
    parser.add_argument("--cache-dir", required=True, type=Path)
    parser.add_argument("--granularity", choices=(900, HOUR), type=int, default=HOUR)
    args = parser.parse_args()
    print(
        backfill(
            args.input,
            args.output,
            args.products,
            args.cache_dir,
            granularity_seconds=args.granularity,
        )
    )
