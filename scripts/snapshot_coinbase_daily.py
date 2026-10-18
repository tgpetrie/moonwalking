"""Bounded public-price snapshot for local chart QA; no database or credentials.

Throttle/request approach adapted from Claude's render_history/fetch_public.py
at ad7b7a5. A separate venue product is never treated as the video's CRYPTO feed.
Official API: https://docs.cdp.coinbase.com/api-reference/exchange-api/rest-api/products/get-product-candles
"""
import argparse
import datetime as dt
import hashlib
import json
import math
from pathlib import Path
import re
import time
import urllib.parse
import urllib.request

DAY = 86400
BASE = "https://api.exchange.coinbase.com"


def iso(timestamp):
    return dt.datetime.fromtimestamp(timestamp, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def normalize(rows, start, end):
    """Deduplicate identical boundaries and reject conflicts or malformed OHLCV."""
    by_time = {}
    for row in rows:
        if not isinstance(row, list) or len(row) != 6:
            raise ValueError("Malformed Coinbase candle")
        t, low, high, opening, close, volume = row
        if (isinstance(t, bool) or not isinstance(t, (int, float)) or not math.isfinite(t)
                or t != int(t) or t % DAY):
            raise ValueError("Candle timestamp is not a UTC daily bucket")
        if not all(isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)
                   for x in [low, high, opening, close, volume]):
            raise ValueError("Non-finite candle values")
        if not (0 < low <= min(opening, close) <= max(opening, close) <= high and volume >= 0):
            raise ValueError("Invalid OHLCV candle")
        if not start <= t < end:
            continue
        if t in by_time and by_time[t] != row:
            raise ValueError("Conflicting duplicate candle")
        by_time[t] = row
    if not by_time:
        raise ValueError("No candles within the requested interval")
    return [{"start": int(t), "end": int(t) + DAY, "low": row[1], "high": row[2],
             "open": row[3], "close": row[4], "volume": row[5], "complete": t + DAY <= end}
            for t, row in sorted(by_time.items())]


def snapshot(product, start, end, output):
    if not re.fullmatch(r"[A-Z0-9]{1,20}-[A-Z0-9]{2,12}", product):
        raise ValueError("Use an explicit Coinbase BASE-QUOTE product")
    if start >= end or start % DAY or end % DAY or end > int(time.time()) // DAY * DAY:
        raise ValueError("Use a closed UTC date range")
    if math.ceil((end - start) / (299 * DAY)) > 24:
        raise ValueError("Snapshot is limited to 24 candle requests")
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    raw_dir = output / "raw"
    raw_dir.mkdir()
    requests = []
    last_request = 0.0

    def get(url):
        nonlocal last_request
        time.sleep(max(0, 1.05 - (time.monotonic() - last_request)))
        request = urllib.request.Request(url, headers={"User-Agent": "moonwalking-chart-qa/1.0", "Accept": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                body = response.read()
        finally:
            last_request = time.monotonic()
        digest = hashlib.sha256(body).hexdigest()
        raw_path = raw_dir / f"{len(requests):02d}-{digest[:12]}.json"
        raw_path.write_bytes(body)
        requests.append({"url": url, "fetched_at": iso(int(time.time())), "sha256": digest,
                         "raw_path": str(raw_path.relative_to(output))})
        return json.loads(body)

    metadata = get(f"{BASE}/products/{product}")
    base, quote = product.split("-")
    if metadata.get("id") != product or metadata.get("base_currency") != base or metadata.get("quote_currency") != quote:
        raise ValueError("Product metadata does not match requested units")
    rows = []
    cursor = start
    while cursor < end:
        stop = min(cursor + 299 * DAY, end)
        query = urllib.parse.urlencode({"granularity": DAY, "start": iso(cursor), "end": iso(stop)})
        batch = get(f"{BASE}/products/{product}/candles?{query}")
        if not isinstance(batch, list):
            raise ValueError("Candle endpoint did not return an array")
        rows.extend(batch)
        cursor = stop
    candles = normalize(rows, start, end)
    missing = (candles[-1]["start"] - candles[0]["start"]) // DAY + 1 - len(candles)
    history = {
        "schema_version": "bhabit.chart-history.v1",
        "instrument": {"product_id": product, "symbol": base, "venue": "coinbase-exchange", "quote_currency": quote},
        "interval_seconds": DAY, "captured_at": end, "candles": candles,
        "source": {"contract": "coinbase-chart-qa/v1", "as_of": iso(end), "fetched_at": iso(int(time.time())),
                   "requested_start": iso(start), "requested_end_exclusive": iso(end),
                   "minimum_request_interval_seconds": 1.05, "request_count": len(requests), "requests": requests,
                   "missing_daily_intervals_inside_observed_span": missing,
                   "metadata": metadata, "stitched": False,
                   "identity_scope": "Coinbase venue product only; token migration lineage and chain identity not established.",
                   "coverage_scope": "Requested interval only; not all-time coverage. Missing buckets are not interpolated.",
                   "video_feed_parity": "Unverified; video provider label is CRYPTO, not Coinbase.",
                   "point_in_time_limitation": "Retrospective pull with historical cutoff; not proof of historical vendor availability."},
    }
    path = output / "history.json"
    path.write_text(json.dumps(history, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"path": str(path), "requests": len(requests), "candles": len(candles), "missing_days": missing,
                      "first": iso(candles[0]["start"]), "last": iso(candles[-1]["start"]),
                      "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}))
    return history


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--product", required=True)
    parser.add_argument("--start", required=True, help="UTC YYYY-MM-DD, inclusive")
    parser.add_argument("--end", required=True, help="UTC YYYY-MM-DD, exclusive")
    parser.add_argument("--out", required=True, type=Path, help="New local snapshot directory; never overwrites")
    args = parser.parse_args()
    timestamp = lambda value: int(dt.datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=dt.timezone.utc).timestamp())
    snapshot(args.product, timestamp(args.start), timestamp(args.end), args.out)
