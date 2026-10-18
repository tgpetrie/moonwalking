"""Build validated RENDER/RNDR daily and weekly datasets from raw public pulls.

Inputs (read-only):
  --raw       directory written by fetch_public.py
  --archive   a *copy* of candle_archive.sqlite (hourly/minute Coinbase
              candles); opened read-only, used to cross-check the daily
              series and to report intraday coverage. Optional.

Outputs under --out (see docs/developer/RENDER_HISTORY.md):
  index.json, identity.json, coverage.json, validation.json,
  series/<venue>_<product>_1d.json, weekly/<venue>_<product>_1w.json

Series are never merged. Each Coinbase product (RENDER-USD, RNDR-USD,
RNDR-USDT, RNDR-EUR) is its own series. Nothing here is called an
all-time low: lows are labelled with the window they were measured over.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import sqlite3
import statistics
import sys
from pathlib import Path

CONTRACT = "moonwalking.market-history/v1"
METHOD_DAILY = "coinbase-native-daily-v1"
METHOD_WEEKLY = "weekly-from-daily-v1"
DAY = 86400
WEEK = 7 * DAY
PRODUCTS = ["RENDER-USD", "RNDR-USD", "RNDR-USDT", "RNDR-EUR"]
JUMP_WARN = 0.40  # flag (never alter) a day-over-day close move beyond this
VOL_REL_TOL = 1e-6
VOL_WARN = 0.01
PRICE_REL_TOL = 1e-9


def iso(ts: int) -> str:
    return dt.datetime.fromtimestamp(ts, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def day(ts: int) -> str:
    return iso(ts)[:10]


def parse_iso(text: str) -> int:
    return int(dt.datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc).timestamp())


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="
")


def close_enough(a: float, b: float, rel: float) -> bool:
    return math.isclose(a, b, rel_tol=rel, abs_tol=1e-12)


# --------------------------------------------------------------------------
# Loading and validating native Coinbase daily candles
# --------------------------------------------------------------------------

def load_coinbase_daily(raw: Path, product: str) -> dict:
    """Merge windows, drop boundary duplicates (and prove they are identical)."""
    doc = load_json(raw / "coinbase" / f"candles_1d_{product}.json")
    by_ts: dict[int, list] = {}
    dup_identical, dup_conflict = 0, []
    http_ok = all(w["http_status"] == 200 for w in doc["windows"])
    for w in doc["windows"]:
        rows = w["response"] if isinstance(w["response"], list) else []
        for ts, low, high, opn, close, vol in rows:
            row = [int(ts), float(low), float(high), float(opn), float(close), float(vol)]
            if row[0] in by_ts:
                if by_ts[row[0]] == row:
                    dup_identical += 1
                else:
                    dup_conflict.append(day(row[0]))
                continue
            by_ts[row[0]] = row
    rows = [by_ts[k] for k in sorted(by_ts)]
    return {
        "rows": rows,
        "windows": doc["windows"],
        "http_ok": http_ok,
        "dup_identical": dup_identical,
        "dup_conflict": dup_conflict,
        "raw_path": f"coinbase/candles_1d_{product}.json",
    }


def row_problems(rows: list[list]) -> list[str]:
    problems = []
    for ts, low, high, opn, close, vol in rows:
        d = day(ts)
        if ts % DAY:
            problems.append(f"{d}: not aligned to UTC midnight")
        if min(low, high, opn, close) <= 0:
            problems.append(f"{d}: non-positive price")
        if vol < 0:
            problems.append(f"{d}: negative volume")
        if high < max(opn, close, low) or low > min(opn, close, high):
            problems.append(f"{d}: OHLC invariant broken")
    return problems


def missing_ranges(rows: list[list]) -> list[dict]:
    """Days inside [first, last] with no candle (Coinbase: no trades)."""
    out = []
    for a, b in zip(rows, rows[1:]):
        if b[0] - a[0] > DAY:
            start, end = a[0] + DAY, b[0] - DAY
            out.append({"from": day(start), "to": day(end), "days": (end - start) // DAY + 1})
    return out


# --------------------------------------------------------------------------
# Daily series
# --------------------------------------------------------------------------

def build_daily(rows: list[list], as_of: int) -> list[dict]:
    candles, prev_close = [], None
    for ts, low, high, opn, close, vol in rows:
        flags = []
        complete = ts + DAY <= as_of
        if not complete:
            flags.append("open_period")
        if prev_close and abs(close / prev_close - 1) > JUMP_WARN:
            flags.append("large_move_vs_prev_close")
        if vol == 0:
            flags.append("zero_volume")
        candles.append({"t": iso(ts), "o": opn, "h": high, "l": low, "c": close, "v": vol, "complete": complete, "flags": flags})
        prev_close = close
    return candles


# --------------------------------------------------------------------------
# Weekly aggregation (ISO weeks: Monday 00:00Z to Sunday 23:59:59Z)
# --------------------------------------------------------------------------

def week_start(ts: int) -> int:
    # 1970-01-01 was a Thursday; shift so weeks start Monday.
    return ((ts + 3 * DAY) // WEEK) * WEEK - 3 * DAY


def build_weekly(rows: list[list], as_of: int, series_ends: bool) -> list[dict]:
    """Aggregate daily rows into weeks.

    A week is `complete` only when all 7 UTC days lie inside the series'
    observed span and are closed. The first week of a series, the last week
    of a delisted series and the current week of a live one are therefore
    flagged, never dropped and never padded.
    """
    first_day, last_day = rows[0][0], rows[-1][0]
    weeks: dict[int, list[list]] = {}
    for row in rows:
        weeks.setdefault(week_start(row[0]), []).append(row)
    out = []
    for ws in sorted(weeks):
        days = weeks[ws]
        we = ws + 6 * DAY
        flags = []
        if ws < first_day:
            flags.append("starts_before_first_candle")
        if we > last_day:
            flags.append("series_ends_mid_week" if series_ends else "open_period")
        if we + DAY > as_of and "open_period" not in flags:
            flags.append("open_period")
        complete = not flags
        no_trade = 7 - len(days)
        if complete and no_trade:
            flags.append("no_trade_days_inside_week")
        out.append(
            {
                "t": iso(ws),
                "week_end": day(we),
                "o": days[0][3],
                "h": max(r[2] for r in days),
                "l": min(r[1] for r in days),
                "c": days[-1][4],
                "v": round(math.fsum(r[5] for r in days), 8),
                "days_present": len(days),
                "complete": complete,
                "flags": flags,
            }
        )
    return out


# --------------------------------------------------------------------------
# Candle archive (hourly / minute) cross-check and coverage
# --------------------------------------------------------------------------

def open_archive(path: Path) -> sqlite3.Connection:
    return sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)


def archive_hourly(conn: sqlite3.Connection, product: str) -> list[list]:
    return [
        list(r)
        for r in conn.execute(
            "SELECT ts, open, high, low, close, volume FROM candles "
            "WHERE product_id=? AND granularity=3600 ORDER BY ts",
            (product,),
        )
    ]


def archive_windows(conn: sqlite3.Connection, product: str, granularity: int) -> list[tuple[int, int, int, str]]:
    return list(
        conn.execute(
            "SELECT window_start, window_end, candles, status FROM fetched_windows "
            "WHERE product_id=? AND granularity=? ORDER BY window_start",
            (product, granularity),
        )
    )


def contiguous_ranges(windows: list[tuple[int, int, int, str]], step: int) -> list[dict]:
    """Merge fetched windows into contiguous covered ranges (end is inclusive)."""
    out = []
    for start, end, _n, status in windows:
        if status != "ok":
            continue
        if out and start <= out[-1]["end_ts"] + step:
            out[-1]["end_ts"] = max(out[-1]["end_ts"], end)
        else:
            out.append({"start_ts": start, "end_ts": end})
    return [{"from": iso(r["start_ts"]), "to": iso(r["end_ts"])} for r in out]


def crosscheck_daily_vs_hourly(native: list[list], hourly: list[list], windows: list) -> dict:
    """Compare Coinbase native daily candles with days rebuilt from archived hourly candles.

    Only UTC days wholly inside the fetched hourly ranges are compared.
    """
    covered = []
    for start, end, _n, status in windows:
        if status == "ok":
            if covered and start <= covered[-1][1] + 3600:
                covered[-1][1] = max(covered[-1][1], end)
            else:
                covered.append([start, end])

    def day_fully_covered(d0: int) -> bool:
        return any(s <= d0 and d0 + DAY - 3600 <= e for s, e in covered)

    hours_by_day: dict[int, list[list]] = {}
    for row in hourly:
        hours_by_day.setdefault(row[0] - row[0] % DAY, []).append(row)
    native_by_day = {r[0]: r for r in native}

    compared = price_matched = 0
    volume_diffs, absent_native_but_hourly, absent_hourly_but_native, price_mismatches = [], [], [], []
    d0 = hourly[0][0] - hourly[0][0] % DAY if hourly else 0
    for d in range(d0, (hourly[-1][0] if hourly else -1) + 1, DAY):
        if not day_fully_covered(d):
            continue
        hrs, nat = hours_by_day.get(d), native_by_day.get(d)
        if hrs is None and nat is None:
            continue
        if nat is None:
            absent_native_but_hourly.append(day(d))
            continue
        if hrs is None:
            absent_hourly_but_native.append(day(d))
            continue
        compared += 1
        agg = [hrs[0][1], max(h[2] for h in hrs), min(h[3] for h in hrs), hrs[-1][4]]
        got = [nat[3], nat[2], nat[1], nat[4]]  # o h l c
        if all(close_enough(a, b, PRICE_REL_TOL) for a, b in zip(agg, got)):
            price_matched += 1
        else:
            price_mismatches.append({"day": day(d), "hourly_derived_ohlc": agg, "native_ohlc": got})
        hv = math.fsum(h[5] for h in hrs)
        if not close_enough(hv, nat[5], VOL_REL_TOL):
            volume_diffs.append({"day": day(d), "hourly_sum": round(hv, 8), "native": nat[5], "rel_diff": abs(hv - nat[5]) / nat[5]})
    max_rel = max((v["rel_diff"] for v in volume_diffs), default=0.0)
    return {
        "days_compared": compared,
        "ohlc_days_matching": price_matched,
        "ohlc_mismatches": price_mismatches,
        "volume_days_differing": len(volume_diffs),
        "volume_max_rel_diff": max_rel,
        "volume_median_rel_diff": statistics.median(v["rel_diff"] for v in volume_diffs) if volume_diffs else 0.0,
        "volume_differences_over_1pct": [v for v in volume_diffs if v["rel_diff"] > VOL_WARN],
        "days_native_missing_but_hourly_present": absent_native_but_hourly,
        "days_hourly_missing_but_native_present": absent_hourly_but_native,
        "price_rel_tol": PRICE_REL_TOL,
        "volume_exact_rel_tol": VOL_REL_TOL,
        "volume_warn_rel": VOL_WARN,
        "reading": "OHLC must match exactly. Volume may differ slightly because the exchange builds hourly and daily candles at different times; differences above volume_warn_rel are listed.",
        "passed": not price_mismatches and not absent_native_but_hourly and not absent_hourly_but_native and max_rel <= VOL_WARN,
    }


def hourly_gaps(hourly: list[list]) -> list[dict]:
    return [
        {"from": iso(a[0] + 3600), "to": iso(b[0] - 3600), "hours": (b[0] - a[0]) // 3600 - 1}
        for a, b in zip(hourly, hourly[1:])
        if b[0] - a[0] != 3600
    ]


# --------------------------------------------------------------------------
# Identity
# --------------------------------------------------------------------------

def build_identity(raw: Path) -> dict:
    cg = load_json(raw / "coingecko" / "coin_render-token.json")["response"]
    cur = {c: load_json(raw / "coinbase" / f"currency_{c}.json")["response"] for c in ("RENDER", "RNDR")}
    prod = {p: load_json(raw / "coinbase" / f"product_{p}.json")["response"] for p in PRODUCTS}

    def network(c: str) -> dict:
        n = cur[c]["supported_networks"][0] if cur[c].get("supported_networks") else {}
        return {"network": cur[c].get("default_network"), "contract": n.get("contract_address")}

    cg_platforms = {k: v for k, v in (cg.get("platforms") or {}).items() if v}
    tokens = []
    for sym, chain in (("RNDR", "ethereum"), ("RENDER", "solana")):
        net = network(sym)
        contract = net["contract"] or (cur[sym].get("details", {}) or {}).get("crypto_address_link", "")
        cg_contract = cg_platforms.get(chain)
        tokens.append(
            {
                "symbol": sym,
                "name": cur[sym]["name"],
                "chain": chain,
                "coinbase_currency_status": cur[sym]["status"],
                "contract": net["contract"],
                "contract_source": "coinbase /currencies" if net["contract"] else "coingecko only",
                "coingecko_contract": cg_contract,
                "coinbase_contract_matches_coingecko": bool(net["contract"]) and net["contract"].lower() == (cg_contract or "").lower(),
                "explorer_hint": None if net["contract"] else contract,
            }
        )
    # RNDR on Coinbase exposes its token address only inside the explorer link.
    for t in tokens:
        if t["symbol"] == "RNDR" and not t["contract"]:
            link = cur["RNDR"]["details"].get("crypto_address_link", "")
            marker = "/token/"
            if marker in link:
                addr = link.split(marker, 1)[1].split("?", 1)[0]
                t["contract"] = addr
                t["contract_source"] = "coinbase /currencies explorer link"
                t["coinbase_contract_matches_coingecko"] = addr.lower() == (t["coingecko_contract"] or "").lower()
        t.pop("explorer_hint", None)

    return {
        "asset": {
            "name": "Render Network",
            "coingecko_id": cg["id"],
            "coingecko_symbol": cg["symbol"],
            "note": (
                "CoinGecko treats the Ethereum RNDR token and the Solana RENDER token as one asset. "
                "Coinbase lists them as two separate currencies with different contracts, and both "
                "traded on Coinbase at the same time, so Moonwalking keeps them as separate series."
            ),
        },
        "tokens": tokens,
        "markets": [
            {
                "venue": "coinbase-exchange",
                "product_id": p,
                "base_currency": prod[p]["base_currency"],
                "quote_currency": prod[p]["quote_currency"],
                "quote_kind": "fiat" if prod[p]["quote_currency"] in ("USD", "EUR") else "stablecoin",
                "status": prod[p]["status"],
                "trading_disabled": prod[p]["trading_disabled"],
            }
            for p in PRODUCTS
        ],
        "other_venues_checked": [
            {
                "venue": "binance",
                "symbols": ["RENDERUSDT", "RNDRUSDT"],
                "result": "HTTP 451 from this location on api.binance.com; no data obtained and none sought by other means",
            }
        ],
        "probed_coinbase_product_ids_not_found": ["RNDR-BTC", "RENDER-USDC", "RENDER-USDT", "RENDER-BTC", "RENDER-EUR", "RENDER-GBP"],
        "sources": [
            "coinbase /products/{id}",
            "coinbase /currencies/{RENDER,RNDR}",
            "coingecko /coins/render-token",
        ],
    }


# --------------------------------------------------------------------------
# Series documents
# --------------------------------------------------------------------------

def lowest(rows: list[list], lo: int = 0, hi: int = 10**12) -> dict | None:
    sel = [r for r in rows if lo <= r[0] <= hi]
    if not sel:
        return None
    r = min(sel, key=lambda x: (x[1], x[0]))
    return {"price": r[1], "day": day(r[0])}


def highest(rows: list[list]) -> dict:
    r = max(rows, key=lambda x: (x[2], -x[0]))
    return {"price": r[2], "day": day(r[0])}


def series_doc(*, product: str, ident: dict, loaded: dict, as_of: int, granularity: str, candles: list[dict], extra: dict) -> dict:
    market = next(m for m in ident["markets"] if m["product_id"] == product)
    token = next(t for t in ident["tokens"] if t["symbol"] == market["base_currency"])
    return {
        "contract": CONTRACT,
        "series_id": f"coinbase-exchange:{product}:{granularity}",
        "as_of": iso(as_of),
        "asset": {
            "symbol": token["symbol"],
            "name": token["name"],
            "chain": token["chain"],
            "contract": token["contract"],
            "coingecko_id": ident["asset"]["coingecko_id"],
        },
        "market": {
            "venue": market["venue"],
            "product_id": product,
            "base_currency": market["base_currency"],
            "quote_currency": market["quote_currency"],
            "quote_kind": market["quote_kind"],
            "status": market["status"],
            "price_unit": market["quote_currency"],
            "volume_unit": market["base_currency"],
        },
        "interval": {
            "granularity": granularity,
            "seconds": DAY if granularity == "1d" else WEEK,
            "bucket_timestamp": "open",
            "alignment": "UTC midnight" if granularity == "1d" else "Monday 00:00 UTC",
        },
        "candles": candles,
        **extra,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--raw", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--archive", help="read-only copy of candle_archive.sqlite")
    args = ap.parse_args()
    raw, out = Path(args.raw), Path(args.out)

    manifest = load_json(raw / "manifest.json")
    as_of = parse_iso(manifest["end"])
    last_closed = as_of - DAY
    ident = build_identity(raw)

    conn = open_archive(Path(args.archive)) if args.archive else None
    series_index, coverage, validation = [], {}, {}
    daily_rows: dict[str, list[list]] = {}

    for product in PRODUCTS:
        loaded = load_coinbase_daily(raw, product)
        rows = loaded["rows"]
        daily_rows[product] = rows
        market = next(m for m in ident["markets"] if m["product_id"] == product)
        delisted = market["status"] != "online"
        problems = row_problems(rows)
        gaps = missing_ranges(rows)
        no_trade_days = sum(g["days"] for g in gaps)
        windows = loaded["windows"]
        # earliest instant probed that returned an OK-but-empty response before the first candle
        first_ts = rows[0][0]
        probed_back = min(parse_iso(w["window"]["start"]) for w in windows)
        probes_before_first = [
            w for w in windows if w["http_status"] == 200 and parse_iso(w["window"]["end"]) <= first_ts and w["window"]["rows"] == 0
        ]
        has_empty_lead_in = bool(probes_before_first)

        daily = build_daily(rows, as_of)
        weekly = build_weekly(rows, as_of, series_ends=delisted)

        low_all = lowest(rows)
        coverage[product] = {
            "venue": "coinbase-exchange",
            "status": market["status"],
            "first_candle": day(first_ts),
            "last_candle": day(rows[-1][0]),
            "daily_candles": len(rows),
            "complete_daily_candles": sum(1 for c in daily if c["complete"]),
            "no_trade_days_inside_span": no_trade_days,
            "no_trade_ranges": gaps,
            "probed_back_to": iso(probed_back),
            "empty_probe_before_first_candle": has_empty_lead_in,
            "span_is_product_lifetime_on_venue": has_empty_lead_in,
            "lowest_daily_low": {
                **(low_all or {}),
                "scope": "this venue product, first candle through last candle in this file",
                "is_all_time_low": False,
                "why_not_all_time": "Covers one product on one venue; the asset traded elsewhere before and after, and the pre-Coinbase low is not in this data.",
            },
            "highest_daily_high": highest(rows),
            "weekly": {
                "weeks": len(weekly),
                "complete_weeks": sum(1 for w in weekly if w["complete"]),
                "incomplete_weeks": [{"t": w["t"][:10], "flags": w["flags"]} for w in weekly if not w["complete"]],
            },
        }
        validation[product] = {
            "http_all_200": loaded["http_ok"],
            "rows_after_dedupe": len(rows),
            "boundary_duplicates_identical": loaded["dup_identical"],
            "boundary_duplicates_conflicting": loaded["dup_conflict"],
            "row_problems": problems,
            "large_moves": [c["t"][:10] for c in daily if "large_move_vs_prev_close" in c["flags"]],
            "zero_volume_days": [c["t"][:10] for c in daily if "zero_volume" in c["flags"]],
            "passed": loaded["http_ok"] and not loaded["dup_conflict"] and not problems,
        }

        prov = {
            "source": "coinbase-exchange-candles",
            "endpoint": "GET https://api.exchange.coinbase.com/products/{product_id}/candles?granularity=86400",
            "authenticated": False,
            "fetched_at": max(w["fetched_at"] for w in windows),
            "raw_file": {"path": f"raw/{loaded['raw_path']}", "sha256": sha256_file(raw / loaded["raw_path"])},
            "methodology": METHOD_DAILY,
            "stitched": False,
            "derived_from": None,
            "absent_day_means": "no trades on this product that UTC day (Coinbase omits empty candles)",
        }
        cov_doc = {
            "first_candle": day(first_ts),
            "last_candle": day(rows[-1][0]),
            "candle_count": len(rows),
            "last_closed_day": day(last_closed),
            "no_trade_ranges": gaps,
            "probed_back_to": iso(probed_back),
            "empty_probe_before_first_candle": has_empty_lead_in,
            "lowest_daily_low": coverage[product]["lowest_daily_low"],
        }
        d_doc = series_doc(
            product=product, ident=ident, loaded=loaded, as_of=as_of, granularity="1d", candles=daily,
            extra={"coverage": cov_doc, "provenance": prov},
        )
        w_doc = series_doc(
            product=product, ident=ident, loaded=loaded, as_of=as_of, granularity="1w", candles=weekly,
            extra={
                "coverage": {**cov_doc, "candle_count": len(weekly)},
                "provenance": {
                    **prov,
                    "methodology": METHOD_WEEKLY,
                    "derived_from": f"coinbase-exchange:{product}:1d",
                    "week_definition": "Monday 00:00:00Z through Sunday 23:59:59Z; o/c are the first/last day present, h/l the extremes, v the sum",
                    "complete_means": "all 7 UTC days lie inside the series' observed span and have closed",
                },
            },
        )
        d_name, w_name = f"coinbase_{product}_1d.json", f"coinbase_{product}_1w.json"
        write_json(out / "series" / d_name, d_doc)
        write_json(out / "weekly" / w_name, w_doc)
        series_index.append(
            {
                "series_id": d_doc["series_id"], "file": f"series/{d_name}", "candles": len(daily),
                "first": day(first_ts), "last": day(rows[-1][0]),
            }
        )
        series_index.append(
            {
                "series_id": w_doc["series_id"], "file": f"weekly/{w_name}", "candles": len(weekly),
                "first": weekly[0]["t"][:10], "last": weekly[-1]["t"][:10],
            }
        )

    # Hourly archive: cross-check RENDER-USD and report intraday coverage.
    intraday = None
    if conn is not None:
        hourly = archive_hourly(conn, "RENDER-USD")
        w1h = archive_windows(conn, "RENDER-USD", 3600)
        w1m = archive_windows(conn, "RENDER-USD", 60)
        meta = dict(conn.execute("SELECT key, value FROM archive_meta"))
        win_ranges = [(a, b) for a, b, _n, st in w1h if st == "ok"]
        outside = [h[0] for h in hourly if not any(a <= h[0] <= b for a, b in win_ranges)]
        n1m = conn.execute("SELECT COUNT(*) FROM candles WHERE product_id='RENDER-USD' AND granularity=60").fetchone()[0]
        validation["RENDER-USD"]["daily_vs_archived_hourly"] = crosscheck_daily_vs_hourly(daily_rows["RENDER-USD"], hourly, w1h)
        intraday = {
            "source": meta.get("source"),
            "methodology": meta.get("methodology_version"),
            "absent_interval_means": meta.get("absent_minute_means"),
            "RENDER-USD": {
                "1h": {
                    "candles": len(hourly),
                    "first": iso(hourly[0][0]), "last": iso(hourly[-1][0]),
                    "fetched_ranges": contiguous_ranges(w1h, 3600),
                    "no_trade_hour_gaps": hourly_gaps(hourly),
                    "candles_outside_fetched_windows": {
                        "count": len(outside),
                        "first": iso(outside[0]) if outside else None,
                        "last": iso(outside[-1]) if outside else None,
                        "note": "present in the archive but not recorded in fetched_windows; absence of a candle there does not prove a no-trade hour",
                    },
                },
                "1m": {
                    "candles": n1m,
                    "fetched_ranges": contiguous_ranges(w1m, 60),
                    "note": "minute candles exist only for the ranges listed; a minute with no candle inside a fetched range had no trades",
                },
            },
            "other_products_in_archive": "RNDR-* products are not in the archive; the archive holds current USD-quoted Coinbase products only",
        }
        conn.close()

    # RENDER-USD vs RNDR-USD: they overlap. Report, never merge.
    a = {r[0]: r for r in daily_rows["RENDER-USD"]}
    b = {r[0]: r for r in daily_rows["RNDR-USD"]}
    both = sorted(set(a) & set(b))
    ratios = [a[t][4] / b[t][4] for t in both]
    lineage = {
        "stitched": False,
        "predecessor": {"series_id": "coinbase-exchange:RNDR-USD:1d", "token": "RNDR (Ethereum)", "first": day(min(b)), "last": day(max(b))},
        "successor": {"series_id": "coinbase-exchange:RENDER-USD:1d", "token": "RENDER (Solana)", "first": day(min(a)), "last": day(max(a))},
        "overlap_days": len(both),
        "overlap_first": day(both[0]) if both else None,
        "overlap_last": day(both[-1]) if both else None,
        "close_ratio_render_over_rndr": {
            "median": round(statistics.median(ratios), 6),
            "p05": round(sorted(ratios)[int(0.05 * len(ratios))], 6),
            "p95": round(sorted(ratios)[int(0.95 * len(ratios)) - 1], 6),
        } if ratios else None,
        "note": "Two tokens and two order books traded side by side. A chart may place them on one axis only as separate, labelled series.",
    }

    x = validation["RENDER-USD"].get("daily_vs_archived_hourly")
    if x is not None:
        validation["RENDER-USD"]["passed"] = validation["RENDER-USD"]["passed"] and x["passed"]
    all_series_ok = all(v["passed"] for v in validation.values())
    write_json(out / "identity.json", ident)
    write_json(out / "coverage.json", {"as_of": iso(as_of), "last_closed_day": day(last_closed), "products": coverage, "lineage": lineage, "intraday_archive": intraday,
        "all_time_low": {
            "established": False,
            "reason": "No single source covers the asset's whole life. Coinbase starts in 2022 (RNDR) and 2024 (RENDER); CoinGecko's aggregate record cites an earlier low that this dataset does not contain.",
            "external_reference_unverified": {
                "source": "coingecko /coins/render-token market_data.atl",
                "price_usd": load_json(raw / "coingecko" / "coin_render-token.json")["response"]["market_data"]["atl"]["usd"],
                "date": load_json(raw / "coingecko" / "coin_render-token.json")["response"]["market_data"]["atl_date"]["usd"][:10],
            },
        }})
    write_json(out / "validation.json", {"as_of": iso(as_of), "passed": all_series_ok, "products": validation})
    write_json(
        out / "index.json",
        {
            "contract": CONTRACT,
            "as_of": iso(as_of),
            "generated_by": "scripts/render_history/build_datasets.py",
            "requests_made": manifest["requests"],
            "series": series_index,
            "identity": "identity.json",
            "coverage": "coverage.json",
            "validation": "validation.json",
            "raw": "raw/",
        },
    )
    print(json.dumps({p: (v["passed"], v["rows_after_dedupe"]) for p, v in validation.items()}))
    return 0 if all_series_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
