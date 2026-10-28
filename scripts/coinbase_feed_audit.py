"""Bounded public Exchange capture and deterministic ticker/matches audit.

Does not import/start the backend or modify its stores. Raw public packets stay
outside Git. REST trade reconciliation uses separate requests and timestamps.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import gzip
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import threading
import time
import urllib.parse
import urllib.request

WS_URL = "wss://ws-feed.exchange.coinbase.com"
REST_URL = "https://api.exchange.coinbase.com"
CHANNELS = ["ticker", "matches", "heartbeat"]
VERSION = "coinbase-side-coverage-audit-v1"


def write_json(path, value):
    path = Path(path)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    temporary.replace(path)


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def envelope(message, sequence=0):
    return {
        "receipt_ts_ms": time.time_ns() // 1_000_000,
        "receipt_monotonic_ns": time.monotonic_ns(),
        "connection_id": 1,
        "receipt_seq": sequence,
        "message": message,
    }


def append_json(stream, value):
    stream.write(json.dumps(value, separators=(",", ":"), allow_nan=False) + "\n")


def records(path):
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        for line in stream:
            yield json.loads(line)


def amount(message, size_key):
    try:
        price, size = Decimal(str(message["price"])), Decimal(str(message[size_key]))
        if not price.is_finite() or not size.is_finite() or price <= 0 or size <= 0:
            raise ValueError("nonpositive/nonfinite trade")
        return price, size
    except (KeyError, InvalidOperation, ValueError) as exc:
        raise ValueError("invalid trade price/size") from exc


def missing_ranges(ids):
    """Compact adjacent missing integer IDs; these are candidates, not proof."""
    ranges = []
    for trade_id in sorted(ids):
        if ranges and trade_id == ranges[-1][1] + 1:
            ranges[-1][1] = trade_id
        else:
            ranges.append([trade_id, trade_id])
    return ranges


def analyze(run_dir):
    """Replay completed raw files. Never read a live backend or historical labels."""
    run_dir = Path(run_dir)
    meta = json.loads((run_dir / "capture.json").read_text(encoding="utf-8"))
    manifest = json.loads((run_dir / "MANIFEST.json").read_text(encoding="utf-8"))
    for filename, expected in manifest["sha256"].items():
        if digest(run_dir / filename) != expected:
            raise ValueError(f"capture hash mismatch: {filename}")
    products = meta["products"]
    messages = {p: {"ticker": {}, "match": {}} for p in products}
    duplicates, conflicts, reordered = Counter(), Counter(), Counter()
    counts, heartbeats, rest = (
        defaultdict(Counter),
        defaultdict(list),
        defaultdict(dict),
    )
    last_ids = {}
    ack_products = defaultdict(set)
    errors = Counter()
    last_wall, last_mono = None, None
    max_dispatch_delay = 0.0
    for row in records(run_dir / "websocket.jsonl.gz"):
        msg = row["message"]
        kind, product = msg.get("type", "unknown"), msg.get("product_id")
        wall, mono = row["receipt_ts_ms"], row["receipt_monotonic_ns"]
        if last_wall is not None and wall < last_wall:
            errors["backward_wall_clock"] += 1
        if last_mono is not None and mono < last_mono:
            errors["backward_monotonic_clock"] += 1
        if last_wall is not None:
            max_dispatch_delay = max(
                max_dispatch_delay,
                abs((wall - last_wall) / 1000 - (mono - last_mono) / 1e9),
            )
        last_wall, last_mono = wall, mono
        if kind == "subscriptions":
            for channel in msg.get("channels", []):
                ack_products[channel["name"]].update(channel.get("product_ids", []))
        if kind.startswith("audit_") or kind == "error":
            errors[kind] += 1
        if product not in messages:
            continue
        counts[product][kind] += 1
        if kind == "heartbeat":
            heartbeats[product].append((mono, int(msg["last_trade_id"])))
        if kind not in ("ticker", "match"):
            continue  # last_match is only a subscription watermark
        key = (product, kind)
        try:
            trade_id = int(msg["trade_id"])
            amount(msg, "size" if kind == "match" else "last_size")
        except (KeyError, ValueError, TypeError):
            errors["invalid_trade"] += 1
            continue
        if trade_id < last_ids.get(key, trade_id):
            reordered[key] += 1
        last_ids[key] = max(last_ids.get(key, trade_id), trade_id)
        prior = messages[product][kind].get(trade_id)
        if prior:
            duplicates[key] += 1
            fields = ("price", "side", "size" if kind == "match" else "last_size")
            if any(prior["message"].get(k) != msg.get(k) for k in fields):
                conflicts[key] += 1
        else:
            messages[product][kind][trade_id] = row
    rest_errors = 0
    for row in records(run_dir / "rest.jsonl.gz"):
        if "error" in row:
            rest_errors += 1
            continue
        for trade in row["trades"]:
            rest[row["product_id"]][int(trade["trade_id"])] = trade

    output = {
        "version": VERSION,
        "capture": meta,
        "raw_manifest": manifest,
        "errors": dict(errors),
        "rest_request_errors": rest_errors,
        "max_wall_monotonic_delta_seconds": max_dispatch_delay,
        "products": {},
        "hour_gate_pass": False,
    }
    for product in products:
        ticks, matches = messages[product]["ticker"], messages[product]["match"]
        overlap = sorted(ticks.keys() & matches.keys())
        cross, maker_sides = Counter(), Counter()
        discrepancies = unknown_sides = 0
        arrival_differences = []
        for tid in overlap:
            ticker, match = ticks[tid]["message"], matches[tid]["message"]
            a, b = ticker.get("side"), match.get("side")
            cross[f"ticker_{a}/match_{b}"] += 1
            if a not in ("buy", "sell") or b not in ("buy", "sell"):
                unknown_sides += 1
            else:
                maker_sides[b] += 1
            if amount(ticker, "last_size") != amount(match, "size"):
                discrepancies += 1
            arrival_differences.append(
                (
                    ticks[tid]["receipt_monotonic_ns"]
                    - matches[tid]["receipt_monotonic_ns"]
                )
                / 1e6
            )
        same = sum(cross[f"ticker_{s}/match_{s}"] for s in ("buy", "sell"))
        opposite = sum(
            cross[f"ticker_{a}/match_{b}"]
            for a, b in (("buy", "sell"), ("sell", "buy"))
        )
        sufficient = all(maker_sides[s] >= 5 for s in ("buy", "sell"))
        mapping = "inconclusive"
        if (
            sufficient
            and not discrepancies
            and not unknown_sides
            and not any(conflicts[(product, k)] for k in ("ticker", "match"))
        ):
            if same == len(overlap):
                mapping = "ticker_maker_side_supported"
            elif opposite == len(overlap):
                mapping = "ticker_taker_side_supported"

        hb = heartbeats[product]
        boundary = [hb[0][1], hb[-1][1]] if len(hb) >= 2 else None
        reconciled, missing, rest_missing, mismatch = False, set(), set(), []
        heartbeat_max_gap = None
        if hb:
            points = [
                meta["start_monotonic_ns"],
                *[v[0] for v in hb],
                meta["end_monotonic_ns"],
            ]
            heartbeat_max_gap = max((b - a) / 1e9 for a, b in zip(points, points[1:]))
        if boundary and boundary[1] >= boundary[0]:
            lo, hi = boundary
            expected = set(range(lo + 1, hi + 1))
            missing = expected - matches.keys()
            rest_missing = expected - rest[product].keys()
            for tid in expected & matches.keys() & rest[product].keys():
                m, r = matches[tid]["message"], rest[product][tid]
                if amount(m, "size") != amount(r, "size") or m.get("side") != r.get(
                    "side"
                ):
                    mismatch.append(tid)
            # Require REST pages to span both watermark boundaries, even on zero-trade products.
            spans = (
                bool(rest[product])
                and min(rest[product]) <= lo
                and max(rest[product]) >= hi
            )
            subscribed = all(product in ack_products[c] for c in CHANNELS)
            reconciled = (
                spans
                and not missing
                and not rest_missing
                and not mismatch
                and heartbeat_max_gap <= 10
                and subscribed
                and not errors
                and not meta.get("errors")
                and not conflicts[(product, "match")]
            )
        volume = sum(
            (
                amount(row["message"], "size")[0] * amount(row["message"], "size")[1]
                for row in matches.values()
            ),
            Decimal(0),
        )
        sampled_volume = sum(
            (
                amount(matches[tid]["message"], "size")[0]
                * amount(matches[tid]["message"], "size")[1]
                for tid in overlap
            ),
            Decimal(0),
        )
        output["products"][product] = {
            "messages": dict(counts[product]),
            "unique_matches": len(matches),
            "unique_ticker_ids": len(ticks),
            "overlap": len(overlap),
            "ticker_only": len(ticks.keys() - matches.keys()),
            "matches_without_ticker": len(matches.keys() - ticks.keys()),
            "ticker_trade_count_coverage": (
                len(overlap) / len(matches) if matches else None
            ),
            "match_quote_usd": str(volume),
            "ticker_represented_match_quote_usd": str(sampled_volume),
            "ticker_trade_volume_coverage": (
                float(sampled_volume / volume) if volume else None
            ),
            "duplicates": {k: duplicates[(product, k)] for k in ("ticker", "match")},
            "conflicting_duplicates": {
                k: conflicts[(product, k)] for k in ("ticker", "match")
            },
            "reordered": {k: reordered[(product, k)] for k in ("ticker", "match")},
            "side_cross_tab": dict(cross),
            "price_size_discrepancies": discrepancies,
            "mapping_verdict": mapping,
            "heartbeat_boundaries": boundary,
            "heartbeat_max_gap_seconds": heartbeat_max_gap,
            "match_id_gap_candidates": missing_ranges(missing),
            "rest_id_gap_candidates": missing_ranges(rest_missing),
            "rest_mismatch_ids": mismatch,
            "coverage_verdict": (
                "rest_reconciled" if reconciled else "incomplete_or_unverified"
            ),
            "ticker_minus_match_receipt_ms_min": (
                min(arrival_differences) if arrival_differences else None
            ),
            "ticker_minus_match_receipt_ms_max": (
                max(arrival_differences) if arrival_differences else None
            ),
        }
    output["hour_gate_pass"] = (
        meta["elapsed_seconds"] >= 3600
        and meta["completed"]
        and not meta.get("code_dirty", False)
        and all(
            p["mapping_verdict"] != "inconclusive"
            and p["coverage_verdict"] == "rest_reconciled"
            for p in output["products"].values()
        )
    )
    output["limits"] = [
        "Coverage verdicts apply only between first/last heartbeat trade-ID watermarks.",
        "Integer ID holes are candidates; REST reconciliation is required.",
        "A sample is not a guarantee of future delivery or every product's side semantics.",
        "Synchronous reader: no application queue; upstream/socket loss is checked by reconciliation.",
    ]
    write_json(run_dir / "REPORT.json", output)
    return output


def rest_page(product, cursor=None):
    query = {"limit": 1000}
    if cursor is not None:
        query["after"] = cursor
    url = f"{REST_URL}/products/{product}/trades?{urllib.parse.urlencode(query)}"
    request = urllib.request.Request(url, headers={"User-Agent": VERSION})
    with urllib.request.urlopen(request, timeout=15) as response:
        return url, json.load(response), response.headers.get("cb-after")


def capture(run_dir, products, seconds, rest_interval=60, max_pages=20):
    import websocket  # existing websocket-client dependency, needed only for capture

    run_dir = Path(run_dir).resolve()
    run_dir.mkdir(parents=True, exist_ok=False)
    repo = Path(__file__).resolve().parents[1]
    head = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=repo, text=True
    ).strip()
    dirty = bool(
        subprocess.check_output(
            ["git", "status", "--porcelain", "--", "scripts/coinbase_feed_audit.py"],
            cwd=repo,
            text=True,
        ).strip()
    )
    meta = {
        "version": VERSION,
        "products": products,
        "channels": CHANNELS,
        "endpoint": WS_URL,
        "requested_seconds": seconds,
        "rest_interval_seconds": rest_interval,
        "max_rest_pages": max_pages,
        "script_sha256": digest(__file__),
        "code_commit": head,
        "code_dirty": dirty,
        "python": platform.python_version(),
        "started_utc": utc_now(),
        "start_monotonic_ns": time.monotonic_ns(),
        "connection_attempts": 1,
        "reconnects": 0,
        "completed": False,
    }
    write_json(run_dir / "capture.json", meta)
    ready, alive, watermarks, last_watermarks = (
        threading.Event(),
        threading.Event(),
        {},
        {},
    )
    alive.set()
    failures, sequence = [], [0]
    ws_stream = gzip.open(
        run_dir / "websocket.jsonl.gz", "wt", encoding="utf-8", compresslevel=1
    )

    def record(message):
        sequence[0] += 1
        append_json(ws_stream, envelope(message, sequence[0]))

    def on_open(socket):
        socket.send(
            json.dumps(
                {"type": "subscribe", "product_ids": products, "channels": CHANNELS}
            )
        )

    def on_message(socket, raw):
        try:
            message = json.loads(raw)
        except (ValueError, TypeError):
            record({"type": "audit_parse_error", "raw": str(raw)})
            return
        record(message)
        if message.get("type") == "subscriptions":
            actual = {
                c["name"]: set(c.get("product_ids", []))
                for c in message.get("channels", [])
            }
            if all(set(products) <= actual.get(c, set()) for c in CHANNELS):
                ready.set()
        if message.get("type") == "heartbeat":
            watermarks.setdefault(message["product_id"], int(message["last_trade_id"]))
            last_watermarks[message["product_id"]] = int(message["last_trade_id"])

    def on_error(socket, error):
        failures.append(str(error))
        record(
            {
                "type": "audit_transport_error",
                "error": str(error),
                "error_type": type(error).__name__,
            }
        )

    def on_close(socket, status_code, reason):
        record(
            {
                "type": "connection_closed",
                "close_code": status_code,
                "close_reason": reason,
            }
        )

    def worker():
        try:
            client.run_forever(ping_interval=20, ping_timeout=10, reconnect=0)
        finally:
            alive.clear()

    client = websocket.WebSocketApp(
        WS_URL,
        on_open=on_open,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close,
    )
    thread = threading.Thread(target=worker, name="coinbase-audit-reader", daemon=True)
    thread.start()
    baseline = {}
    try:
        if not ready.wait(20):
            raise RuntimeError("subscription acknowledgment missing after 20s")
        meta["subscription_ack_utc"] = utc_now()
        meta["start_monotonic_ns"] = time.monotonic_ns()
        deadline = time.monotonic() + seconds
        next_rest = time.monotonic() + min(5, seconds)
        with gzip.open(
            run_dir / "rest.jsonl.gz", "wt", encoding="utf-8", compresslevel=1
        ) as rest_stream:

            def reconcile():
                for product in products:
                    lower = baseline.get(product, watermarks.get(product))
                    cursor = None
                    for _ in range(max_pages):
                        try:
                            started = time.time_ns() // 1_000_000
                            url, trades, cursor_next = rest_page(product, cursor)
                            append_json(
                                rest_stream,
                                {
                                    "product_id": product,
                                    "request_ts_ms": started,
                                    "receipt_ts_ms": time.time_ns() // 1_000_000,
                                    "url": url,
                                    "next_cursor": cursor_next,
                                    "trades": trades,
                                },
                            )
                            if not trades:
                                break
                            ids = [int(t["trade_id"]) for t in trades]
                            baseline[product] = max(baseline.get(product, 0), max(ids))
                            if (
                                lower is None
                                or min(ids) <= lower
                                or not cursor_next
                                or cursor_next == cursor
                            ):
                                break
                            cursor = cursor_next
                            time.sleep(0.15)
                        except Exception as exc:
                            append_json(
                                rest_stream,
                                {
                                    "product_id": product,
                                    "error": str(exc),
                                    "receipt_ts_ms": time.time_ns() // 1_000_000,
                                },
                            )
                            break

            while time.monotonic() < deadline:
                if not alive.is_set():
                    raise RuntimeError("socket ended; uninterrupted capture failed")
                if time.monotonic() >= next_rest:
                    reconcile()
                    next_rest = time.monotonic() + rest_interval
                    write_json(
                        run_dir / "STATUS.json",
                        {
                            "status": "capturing",
                            "utc": utc_now(),
                            "elapsed_seconds": (
                                time.monotonic_ns() - meta["start_monotonic_ns"]
                            )
                            / 1e9,
                            "messages": sequence[0],
                            "first_heartbeat_ids": dict(watermarks),
                        },
                    )
                time.sleep(0.2)
            meta["completed"] = True
            client.close()
            thread.join(timeout=15)
            meta["end_monotonic_ns"] = time.monotonic_ns()
            meta["ended_utc"] = utc_now()
            # Stop the socket first. REST's newest page can briefly lag the feed.
            for attempt in range(10):
                reconcile()
                if all(
                    baseline.get(p, 0) >= last_watermarks.get(p, 1) for p in products
                ):
                    break
                time.sleep(2)
    except Exception as exc:
        failures.append(str(exc))
    finally:
        client.close()
        thread.join(timeout=15)
        if thread.is_alive():
            raise RuntimeError("reader did not stop; raw capture is not finalized")
        ws_stream.close()
        # A failed handshake still gets replayable empty REST evidence.
        if not (run_dir / "rest.jsonl.gz").exists():
            with gzip.open(run_dir / "rest.jsonl.gz", "wt", encoding="utf-8"):
                pass
        meta.setdefault("ended_utc", utc_now())
        meta.setdefault("end_monotonic_ns", time.monotonic_ns())
        meta.update({"errors": failures, "messages": sequence[0]})
        meta["elapsed_seconds"] = (
            meta["end_monotonic_ns"] - meta["start_monotonic_ns"]
        ) / 1e9
        meta["completed"] = meta["completed"] and not failures
        write_json(run_dir / "capture.json", meta)
        names = ["capture.json", "websocket.jsonl.gz", "rest.jsonl.gz"]
        write_json(
            run_dir / "MANIFEST.json",
            {"sha256": {name: digest(run_dir / name) for name in names}},
        )
        result = analyze(run_dir)
        write_json(
            run_dir / "STATUS.json",
            {
                "status": "complete" if meta["completed"] else "failed",
                "utc": utc_now(),
                "hour_gate_pass": result["hour_gate_pass"],
                "report": str(run_dir / "REPORT.json"),
            },
        )
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=["capture", "analyze"])
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument(
        "--products",
        nargs="+",
        default=["BTC-USD", "SOL-USD", "ALCX-USD", "AURORA-USD"],
    )
    parser.add_argument("--seconds", type=float, default=3600)
    args = parser.parse_args()
    if args.phase == "capture":
        if args.seconds <= 0 or len(set(args.products)) != len(args.products):
            parser.error("positive duration and distinct products required")
        result = capture(args.run_dir, args.products, args.seconds)
    else:
        result = analyze(args.run_dir)
    print(
        json.dumps(
            {
                "report": str(args.run_dir / "REPORT.json"),
                "hour_gate_pass": result["hour_gate_pass"],
                "products": {
                    p: {
                        k: v[k]
                        for k in ["mapping_verdict", "coverage_verdict", "overlap"]
                    }
                    for p, v in result["products"].items()
                },
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
