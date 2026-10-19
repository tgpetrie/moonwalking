"""Watch Coinbase's product catalogue and status page, and snapshot Hyperliquid perps, logging what we see when we see it.

Writes to the point-in-time log (`pit_log.py`). Unauthenticated public GETs
only, at least 1.1 s apart.

  python backend/pit_watch.py --once            # one pass
  python backend/pit_watch.py --loop --interval 300

First pass on an empty log records a BASELINE, not listings: products that
already exist were not "listed" at that moment. Later passes record:
  PRODUCT_LISTED         a product id that was not in the catalogue before
  PRODUCT_STATUS_CHANGE  any change in status, trading_disabled, cancel_only,
                         limit_only, post_only, auction_mode or status_message
  PRODUCT_REMOVED        a product id that disappeared from the catalogue
  STATUS_INCIDENT        a status-page incident not seen before (published
                         time = its created_at)
  STATUS_INCIDENT_UPDATE a seen incident whose content changed (revision_of
                         points at the earlier record)
The status page only lists its last 50 incidents, so history before the
first pass is limited to those.

Each pass also takes one Hyperliquid `metaAndAssetCtxs` snapshot (funding,
open interest, mark/oracle/mid prices and impact prices for every perp) into `positioning_snapshot`, with a
POSITIONING_PASS row holding the response hash. `product_id` there is a ticker
match to an existing Coinbase product, not a verified identity.
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path
from typing import Any, Callable, Dict, Optional

import requests

try:
    import pit_log
except ImportError:  # imported as backend.pit_watch
    from backend import pit_log

logger = logging.getLogger("pit_watch")

PRODUCTS_URL = "https://api.exchange.coinbase.com/products"
INCIDENTS_URL = "https://status.coinbase.com/api/v2/incidents.json"
HYPERLIQUID_URL = "https://api.hyperliquid.xyz/info"
USER_AGENT = "moonwalking-pit-watch/1.0 (read-only public data)"
MIN_INTERVAL_SEC = 1.1
STATE_FIELDS = ("status", "trading_disabled", "cancel_only", "limit_only", "post_only", "auction_mode", "status_message")

_last_request = 0.0


class FetchError(Exception):
    def __init__(self, message: str, status: Optional[int] = None):
        super().__init__(message)
        self.status = status


def get_json(url: str) -> Any:
    """Throttled, unauthenticated GET."""
    global _last_request
    wait = MIN_INTERVAL_SEC - (time.monotonic() - _last_request)
    if wait > 0:
        time.sleep(wait)
    try:
        resp = requests.get(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"}, timeout=20)
    except requests.RequestException as exc:
        raise FetchError(str(exc)) from exc
    finally:
        _last_request = time.monotonic()
    if resp.status_code != 200:
        raise FetchError(f"HTTP {resp.status_code}", resp.status_code)
    return resp.json()


def _state(p: Dict[str, Any]) -> Dict[str, Any]:
    return {k: p.get(k) for k in STATE_FIELDS}


def poll_products(conn, fetch: Callable[[str], Any] = get_json) -> Dict[str, int]:
    source, role = "coinbase_products", "event_calendar"
    counts = {"baseline": 0, "listed": 0, "changed": 0, "removed": 0}
    try:
        rows = fetch(PRODUCTS_URL)
        if not isinstance(rows, list):
            raise FetchError("unexpected payload")
    except FetchError as exc:
        pit_log.set_health(conn, source, role, ok=False, http_status=exc.status, error=str(exc))
        conn.commit()
        raise
    now = pit_log.utc_now()
    first_pass = not pit_log.watched_items(conn, source)
    seen = set()
    for p in rows:
        pid = p.get("id")
        if not pid:
            continue
        seen.add(pid)
        state = _state(p)
        kind, prev, prev_id = pit_log.watch(conn, source, pid, state)
        conn.execute(
            """INSERT INTO symbol_registry (product_id, base_currency, quote_currency, coinbase_status, first_seen_utc, last_seen_utc)
               VALUES (?,?,?,?,?,?)
               ON CONFLICT(product_id) DO UPDATE SET coinbase_status=excluded.coinbase_status,
                   last_seen_utc=excluded.last_seen_utc, removed_seen_utc=NULL""",
            (pid, p.get("base_currency") or "", p.get("quote_currency") or "", p.get("status"), now, now),
        )
        if kind == "same":
            continue
        if kind == "new":
            event = "BASELINE" if first_pass else "PRODUCT_LISTED"
            counts["baseline" if first_pass else "listed"] += 1
            payload = {"product": p}
        else:
            event = "PRODUCT_STATUS_CHANGE"
            counts["changed"] += 1
            payload = {"before": prev, "after": state, "product": p}
        rid = pit_log.record(conn, source_id=source, role=role, event_type=event, product_id=pid, venue_symbol=pid,
                             label=f"{(prev or {}).get('status')} -> {state.get('status')}" if kind == "changed" else state.get("status"),
                             source_url=f"{PRODUCTS_URL}/{pid}", payload=payload,
                             revision_of=prev_id if kind == "changed" else None, first_seen_utc=now)
        pit_log.remember(conn, source, pid, state, rid)
    for pid, prev in pit_log.watched_items(conn, source).items():
        if pid in seen or prev.get("status") == "__removed__":
            continue
        rid = pit_log.record(conn, source_id=source, role=role, event_type="PRODUCT_REMOVED", product_id=pid,
                             venue_symbol=pid, label="missing from catalogue", payload={"before": prev}, first_seen_utc=now)
        pit_log.remember(conn, source, pid, {**prev, "status": "__removed__"}, rid)
        conn.execute("UPDATE symbol_registry SET removed_seen_utc=? WHERE product_id=?", (now, pid))
        counts["removed"] += 1
    pit_log.set_health(conn, source, role, ok=True)
    conn.commit()
    return counts


def poll_incidents(conn, fetch: Callable[[str], Any] = get_json) -> Dict[str, int]:
    source, role = "coinbase_status", "event_calendar"
    counts = {"new": 0, "updated": 0}
    try:
        doc = fetch(INCIDENTS_URL)
        incidents = doc.get("incidents") if isinstance(doc, dict) else None
        if not isinstance(incidents, list):
            raise FetchError("unexpected payload")
    except FetchError as exc:
        pit_log.set_health(conn, source, role, ok=False, http_status=exc.status, error=str(exc))
        conn.commit()
        raise
    now = pit_log.utc_now()
    for inc in incidents:
        iid = inc.get("id")
        if not iid:
            continue
        state = {k: inc.get(k) for k in ("name", "status", "impact", "updated_at", "resolved_at")}
        state["updates"] = len(inc.get("incident_updates") or [])
        kind, _prev, prev_id = pit_log.watch(conn, source, iid, state)
        if kind == "same":
            continue
        event = "STATUS_INCIDENT" if kind == "new" else "STATUS_INCIDENT_UPDATE"
        counts["new" if kind == "new" else "updated"] += 1
        rid = pit_log.record(conn, source_id=source, role=role, event_type=event, product_id=None, venue_symbol=iid,
                             source_published_utc=pit_log.to_utc(inc.get("created_at") if kind == "new" else inc.get("updated_at")),
                             label=f"{inc.get('impact')}: {inc.get('name')}"[:300], source_url=inc.get("shortlink"),
                             payload=inc, revision_of=prev_id if kind == "changed" else None, first_seen_utc=now)
        pit_log.remember(conn, source, iid, state, rid)
    pit_log.set_health(conn, source, role, ok=True)
    conn.commit()
    return counts


def post_json(url: str, body: Dict[str, Any]) -> Any:
    """Throttled, unauthenticated POST (Hyperliquid's info endpoint is POST-only)."""
    global _last_request
    wait = MIN_INTERVAL_SEC - (time.monotonic() - _last_request)
    if wait > 0:
        time.sleep(wait)
    try:
        resp = requests.post(url, json=body, headers={"User-Agent": USER_AGENT}, timeout=20)
    except requests.RequestException as exc:
        raise FetchError(str(exc)) from exc
    finally:
        _last_request = time.monotonic()
    if resp.status_code != 200:
        raise FetchError(f"HTTP {resp.status_code}", resp.status_code)
    return resp.json()


def _f(x: Any) -> Optional[float]:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if v == v and v not in (float("inf"), float("-inf")) else None


def poll_hyperliquid(conn, post: Callable[[str, Dict[str, Any]], Any] = post_json) -> Dict[str, int]:
    """One keyless request: funding, open interest and prices for every Hyperliquid perp."""
    source, role = "hyperliquid_perp", "market_positioning"
    try:
        data = post(HYPERLIQUID_URL, {"type": "metaAndAssetCtxs"})
        meta, ctxs = data[0], data[1]
        universe = meta.get("universe") or []
        if not isinstance(ctxs, list) or len(ctxs) != len(universe):
            raise FetchError("unexpected payload")
    except FetchError as exc:
        pit_log.set_health(conn, source, role, ok=False, http_status=exc.status, error=str(exc))
        conn.commit()
        raise
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        pit_log.set_health(conn, source, role, ok=False, error=f"unexpected payload: {exc}")
        conn.commit()
        raise FetchError("unexpected payload") from exc
    now = pit_log.utc_now()
    body = pit_log.canonical(data)
    pass_id = pit_log.record(conn, source_id=source, role=role, event_type="POSITIONING_PASS",
                             metric_primary=len(universe), label="metaAndAssetCtxs",
                             source_url=HYPERLIQUID_URL, payload={"assets": len(universe), "response_sha256": pit_log.sha256(body)},
                             first_seen_utc=now)
    known = pit_log.coinbase_product_ids(conn)
    rows = []
    for asset, ctx in zip(universe, ctxs):
        name = asset.get("name")
        if not name or asset.get("isDelisted"):
            continue
        pid = f"{name}-USD" if f"{name}-USD" in known else None
        impact = ctx.get("impactPxs") if isinstance(ctx.get("impactPxs"), (list, tuple)) else [None, None]
        impact = list(impact) + [None, None]
        rows.append((now, "hyperliquid", name, pid, _f(ctx.get("funding")), 1.0, _f(ctx.get("openInterest")),
                     _f(ctx.get("markPx")), _f(ctx.get("oraclePx")), _f(ctx.get("premium")), _f(ctx.get("dayNtlVlm")), pass_id,
                     _f(ctx.get("midPx")), _f(impact[0]), _f(impact[1])))
    conn.executemany("""INSERT INTO positioning_snapshot (first_seen_utc, venue, venue_symbol, product_id, funding_rate,
                        funding_interval_hours, open_interest, mark_price, oracle_price, premium, day_notional_volume, pass_record_id,
                        mid_price, impact_bid_price, impact_ask_price)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", rows)
    pit_log.set_health(conn, source, role, ok=True)
    conn.commit()
    return {"assets": len(rows), "mapped_to_coinbase": sum(1 for r in rows if r[3])}


def run_once(path: Optional[Path] = None) -> Dict[str, Any]:
    conn = pit_log.connect(path)
    out: Dict[str, Any] = {}
    try:
        for name, fn in (("products", poll_products), ("incidents", poll_incidents), ("hyperliquid", poll_hyperliquid)):
            try:
                out[name] = fn(conn)
            except FetchError as exc:
                out[name] = {"error": str(exc)}
                logger.warning("%s poll failed: %s", name, exc)
    finally:
        conn.close()
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--once", action="store_true")
    mode.add_argument("--loop", action="store_true")
    ap.add_argument("--interval", type=float, default=300.0, help="seconds between passes (min 60)")
    ap.add_argument("--db", default=None, help="log path (default MW_PIT_LOG_DB or backend/data/pit_context.sqlite)")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    path = Path(args.db) if args.db else None
    if args.once:
        print(run_once(path))
        return 0
    interval = max(60.0, args.interval)
    while True:
        started = time.monotonic()
        logger.info("pass: %s", run_once(path))
        time.sleep(max(0.0, interval - (time.monotonic() - started)))


if __name__ == "__main__":
    sys.exit(main())
