"""Fetch public, unauthenticated RENDER/RNDR identity and daily candles.

Read-only. Never touches Moonwalking's live stores or the candle archive.
Every request goes through one throttle (>= 1.05 s apart), sends no
credentials, and its raw response is saved with the URL, time and a
SHA-256 so the dataset can be re-derived without refetching.

  python scripts/render_history/fetch_public.py --out data/render-history/raw

Venues are fetched separately and never merged here.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

UA = "moonwalking-render-history/1.0 (read-only public data)"
MIN_INTERVAL = 1.05  # seconds between any two requests
DAY = 86400
CB = "https://api.exchange.coinbase.com"

COINBASE_PRODUCTS = ["RENDER-USD", "RNDR-USD", "RNDR-USDT", "RNDR-EUR"]
COINBASE_CURRENCIES = ["RENDER", "RNDR"]
BINANCE_SYMBOLS = ["RENDERUSDT", "RNDRUSDT"]
COINGECKO_ID = "render-token"
COINGECKO_URL = (
    f"https://api.coingecko.com/api/v3/coins/{COINGECKO_ID}"
    "?localization=false&tickers=false&community_data=false&developer_data=false&sparkline=false"
)

_last = 0.0
request_count = 0


def get(url: str) -> tuple[int, bytes]:
    """One throttled, unauthenticated GET. Returns (http_status, body)."""
    global _last, request_count
    wait = MIN_INTERVAL - (time.monotonic() - _last)
    if wait > 0:
        time.sleep(wait)
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            status, body = resp.status, resp.read()
    except urllib.error.HTTPError as err:
        status, body = err.code, err.read()
    finally:
        _last = time.monotonic()
        request_count += 1
    return status, body


def iso(ts: int) -> str:
    return dt.datetime.fromtimestamp(ts, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def record(url: str, status: int, body: bytes, payload) -> dict:
    return {
        "url": url,
        "http_status": status,
        "fetched_at": iso(int(time.time())),
        "sha256": hashlib.sha256(body).hexdigest(),
        "response": payload,
    }


def save(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=1, sort_keys=True) + "\n", encoding="utf-8")


def fetch_json(url: str):
    status, body = get(url)
    try:
        payload = json.loads(body)
    except ValueError:
        payload = {"unparseable": body[:200].decode("utf-8", "replace")}
    return record(url, status, body, payload)


def coinbase_daily(product: str, end_ts: int, floor_ts: int, patience: int = 2) -> dict:
    """Walk back in 300-day windows. Coinbase omits days with no trades.

    Stops after `patience` consecutive empty windows once data has been seen,
    or at `floor_ts`. Empty windows before any data (e.g. a delisted
    product) are skipped, bounded by `floor_ts`.
    """
    windows, seen, empties = [], False, 0
    hi = end_ts
    while hi > floor_ts:
        lo = max(hi - 300 * DAY, floor_ts)
        url = f"{CB}/products/{product}/candles?granularity={DAY}&start={iso(lo)}&end={iso(hi)}"
        rec = fetch_json(url)
        rows = rec["response"] if isinstance(rec["response"], list) else []
        rec["window"] = {"start": iso(lo), "end": iso(hi), "rows": len(rows)}
        windows.append(rec)
        if rec["http_status"] == 200 and rows:
            seen, empties = True, 0
        else:
            empties += 1
            if seen and empties >= patience:
                break
        hi = lo
    return {"product_id": product, "granularity": DAY, "windows": windows}


def binance_daily(symbol: str, end_ts: int, floor_ts: int) -> dict:
    windows, start = [], floor_ts
    while start < end_ts:
        url = (
            "https://api.binance.com/api/v3/klines"
            f"?symbol={symbol}&interval=1d&startTime={start * 1000}&limit=1000"
        )
        rec = fetch_json(url)
        rows = rec["response"] if isinstance(rec["response"], list) else []
        rec["window"] = {"start": iso(start), "rows": len(rows)}
        windows.append(rec)
        if rec["http_status"] != 200 or not rows:
            break
        last_open = int(rows[-1][0]) // 1000
        if len(rows) < 1000:
            break
        start = last_open + DAY
    return {"symbol": symbol, "interval": "1d", "windows": windows}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", required=True, help="directory for raw responses")
    ap.add_argument("--end", default=None, help="ISO date (UTC) to fetch up to; default today 00:00Z")
    ap.add_argument("--floor", default="2020-01-01", help="oldest date to probe")
    ap.add_argument("--skip-binance", action="store_true")
    ap.add_argument("--only-coingecko", action="store_true", help="fetch just the CoinGecko identity/reference record")
    args = ap.parse_args()

    out = Path(args.out)
    today = dt.datetime.now(dt.timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    end = dt.datetime.fromisoformat(args.end).replace(tzinfo=dt.timezone.utc) if args.end else today
    end_ts = int(end.timestamp())
    floor_ts = int(dt.datetime.fromisoformat(args.floor).replace(tzinfo=dt.timezone.utc).timestamp())

    if args.only_coingecko:
        save(out / "coingecko" / f"coin_{COINGECKO_ID}.json", fetch_json(COINGECKO_URL))
        print(f"requests: {request_count}", file=sys.stderr)
        return 0

    for product in COINBASE_PRODUCTS:
        save(out / "coinbase" / f"product_{product}.json", fetch_json(f"{CB}/products/{product}"))
    for cur in COINBASE_CURRENCIES:
        save(out / "coinbase" / f"currency_{cur}.json", fetch_json(f"{CB}/currencies/{cur}"))
    for product in COINBASE_PRODUCTS:
        save(out / "coinbase" / f"candles_1d_{product}.json", coinbase_daily(product, end_ts, floor_ts))
        print(f"coinbase {product} done, requests so far {request_count}", file=sys.stderr)
    if not args.skip_binance:
        for symbol in BINANCE_SYMBOLS:
            save(out / "binance" / f"klines_1d_{symbol}.json", binance_daily(symbol, end_ts, floor_ts))
            print(f"binance {symbol} done, requests so far {request_count}", file=sys.stderr)

    save(out / "coingecko" / f"coin_{COINGECKO_ID}.json", fetch_json(COINGECKO_URL))
    save(out / "manifest.json", {"requests": request_count, "end": iso(end_ts), "floor": iso(floor_ts), "user_agent": UA})
    print(f"requests: {request_count}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
