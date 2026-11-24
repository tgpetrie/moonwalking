"""Record a credential-free depth tape from Coinbase's public order book.

Calls only the unauthenticated market endpoint. It reads no environment
variables, sends no API key, and touches no account, balance or fill. The
position it records is synthetic: a quantity and entry cost you choose.

The output replays with ``scripts/coinbase_paper_depth.py`` and can never be
an official pilot result.
"""

import argparse
from datetime import datetime, timedelta, timezone
from decimal import DecimalException
import json
from pathlib import Path
import time
import urllib.error
import urllib.parse
import urllib.request

from scripts.coinbase_paper_depth import DEPTH_SCHEMA
from scripts.coinbase_paper_exit import PILOT_SETTINGS, _number

PUBLIC_BOOK = "https://api.coinbase.com/api/v3/brokerage/market/product_book"
MAX_LEVELS = 50
POLL_MS = PILOT_SETTINGS["poll_interval_ms"]
EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)


def _now_ms():
    return time.time_ns() // 1_000_000


def _epoch_ms(value):
    stamp = datetime.fromisoformat(value)
    if stamp.tzinfo is None:
        raise ValueError("book timestamp must include its UTC offset")
    return (stamp - EPOCH) // timedelta(milliseconds=1)


def fetch_public_book(product_id, levels, *, opener=urllib.request.urlopen):
    query = urllib.parse.urlencode({"product_id": product_id, "limit": levels})
    with opener(f"{PUBLIC_BOOK}?{query}", timeout=3) as response:
        return json.loads(response.read().decode("utf-8"))


def poll_depth(product_id, levels, *, now_ms=_now_ms, fetch=fetch_public_book):
    """Timestamp receipt; keep Coinbase's book time and bid ladder separately."""
    try:
        response = fetch(product_id, levels)
        observed = now_ms()
        book = response["pricebook"]
        if book["product_id"] != product_id:
            raise ValueError("book product differs from the request")
        bids = [
            {"price": str(_number(level, "price")), "size": str(_number(level, "size"))}
            for level in book["bids"]
        ]
        if not bids:
            raise ValueError("book has no bids")
        return {
            "observed_at_ms": observed,
            "exchange_time_ms": _epoch_ms(book["time"]),
            "bids": bids,
        }
    except (
        urllib.error.URLError,
        OSError,
        KeyError,
        IndexError,
        TypeError,
        ValueError,
        json.JSONDecodeError,
    ):
        return {"observed_at_ms": now_ms(), "quote_status": "UNAVAILABLE"}


def collect(product_id, start_ms, end_ms, levels, *, now_ms=_now_ms,
            sleep=time.sleep, fetch=fetch_public_book):
    quotes = []
    for slot in range(start_ms, end_ms, POLL_MS):
        now = now_ms()
        if now >= slot + POLL_MS:
            continue
        if now < slot:
            sleep((slot - now) / 1_000)
        quote = poll_depth(product_id, levels, now_ms=now_ms, fetch=fetch)
        if quote["observed_at_ms"] > end_ms:
            break
        if quotes and quote["observed_at_ms"] <= quotes[-1]["observed_at_ms"]:
            raise ValueError("local clock moved backward during collection")
        quotes.append(quote)
    return quotes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--product", required=True, help="USD spot pair")
    parser.add_argument("--quantity", required=True, help="Synthetic quantity")
    parser.add_argument("--entry-cost-usd", required=True, help="Synthetic cost")
    parser.add_argument("--exit-fee-bps", required=True, help="Declared fee")
    parser.add_argument("--slippage-bps", required=True)
    parser.add_argument("--duration-seconds", type=int, default=30)
    parser.add_argument("--levels", type=int, default=MAX_LEVELS)
    parser.add_argument("--out", required=True, type=Path, help="New JSON file")
    args = parser.parse_args()
    try:
        if not 1 <= args.levels <= MAX_LEVELS:
            raise ValueError(f"levels must be between 1 and {MAX_LEVELS}")
        if not 1 <= args.duration_seconds <= 4 * 60 * 60:
            raise ValueError("duration must be between 1 and 14400 seconds")
        output = args.out.resolve()
        if output.is_relative_to(Path(__file__).resolve().parents[1]):
            raise ValueError("choose an output file outside the Git checkout")
        if output.exists() or not output.parent.is_dir():
            raise ValueError("output must be a new file in an existing folder")
        for name in ("quantity", "entry_cost_usd"):
            _number({name: getattr(args, name)}, name)
        start_ms = (_now_ms() // 1_000 + 3) * 1_000
        end_ms = start_ms + args.duration_seconds * 1_000
        spec = {
            "schema_version": DEPTH_SCHEMA,
            "window_id": f"depth_{args.product}_{start_ms}_{args.duration_seconds}s",
            "window_start_ms": start_ms,
            "window_end_ms": end_ms,
            **PILOT_SETTINGS,
            "product_id": args.product,
            "quantity": args.quantity,
            "entry_cost_usd": args.entry_cost_usd,
            "exit_fee_bps": args.exit_fee_bps,
            "slippage_bps": args.slippage_bps,
            "thresholds": {"rebound_usd": 50, "rebound_pct": 8, "net_profit_pct": 8},
            "synthetic_position": True,
            "market_data_source": "coinbase_public_market_product_book",
            "book_levels_requested": args.levels,
        }
        spec["quotes"] = collect(args.product, start_ms, end_ms, args.levels)
        with output.open("x", encoding="utf-8") as tape:
            json.dump(spec, tape, default=str, indent=2)
            tape.write("\n")
        print(output)
    except (OSError, ValueError, DecimalException) as error:
        parser.exit(2, f"{parser.prog}: {error}\n")


if __name__ == "__main__":
    main()
