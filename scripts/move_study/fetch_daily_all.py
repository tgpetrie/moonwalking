"""Fetch public daily candles for every Coinbase USD product, including delisted ones.

Read-only, unauthenticated, one request per 1.05 s, resumable (a product whose
file already exists is skipped). Raw responses are kept per product so the
study can be re-run without refetching. Never writes to a Moonwalking store.

  python scripts/move_study/fetch_daily_all.py --out <dir> [--floor 2022-01-01]
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "render_history"))
import fetch_public as fp  # noqa: E402  (shared throttle: >= 1.05 s between requests)

DAY = fp.DAY


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", required=True)
    ap.add_argument("--floor", default="2022-01-01")
    ap.add_argument("--limit", type=int, default=0, help="only the first N products (testing)")
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    today = dt.datetime.now(dt.timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    end_ts = int(today.timestamp())
    floor_ts = int(dt.datetime.fromisoformat(args.floor).replace(tzinfo=dt.timezone.utc).timestamp())

    listing = out / "products.json"
    if listing.exists():
        products = json.loads(listing.read_text(encoding="utf-8"))
    else:
        rec = fp.fetch_json(f"{fp.CB}/products")
        rows = rec["response"] if isinstance(rec["response"], list) else []
        products = sorted(
            ({"id": p["id"], "base": p["base_currency"], "status": p["status"]}
             for p in rows
             if p.get("quote_currency") == "USD" and p["id"] == f"{p['base_currency']}-USD"
             and re.fullmatch(r"[A-Z0-9]{1,20}", p["base_currency"])),
            key=lambda p: p["id"],
        )
        listing.write_text(json.dumps(products, indent=1) + "\n", encoding="utf-8", newline="\n")
    if args.limit:
        products = products[: args.limit]
    print(f"{len(products)} USD products, {sum(p['status'] != 'online' for p in products)} not online", flush=True)

    started = time.time()
    for i, p in enumerate(products, 1):
        path = out / f"{p['id']}.json"
        if path.exists():
            continue
        doc = fp.coinbase_daily(p["id"], end_ts, floor_ts)
        doc["status"] = p["status"]
        path.write_text(json.dumps(doc) + "\n", encoding="utf-8", newline="\n")
        if i % 10 == 0:
            print(f"{i}/{len(products)} {p['id']} requests={fp.request_count} elapsed={int(time.time() - started)}s", flush=True)
    (out / "manifest.json").write_text(json.dumps({"requests": fp.request_count, "end": fp.iso(end_ts), "floor": fp.iso(floor_ts), "user_agent": fp.UA}, indent=1) + "\n", encoding="utf-8", newline="\n")
    print("done", fp.request_count, "requests", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
