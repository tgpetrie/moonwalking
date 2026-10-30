"""Bounded offline verification of one pinned capture; never evaluates returns."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
from decimal import Decimal
import gzip
import hashlib
import json
from pathlib import Path
import time

from micro_baseline import build_baseline
from micro_replay import GRID, ReplayStore, digest


VERSION = "preserved-feed-replay-verification-v1"
MAX_PACKETS = 100000
MAX_REST_ROWS = 1000000
MAX_ID_SPAN = 1000000
FILES = (
    "capture.json",
    "MANIFEST.json",
    "REPORT.json",
    "STATUS.json",
    "websocket.jsonl.gz",
    "rest.jsonl.gz",
)


def write(path, value):
    path.write_text(
        json.dumps(value, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def records(path):
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        for line in stream:
            yield json.loads(line)


def verify_source(capture, manifest_path, capture_key):
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    verified = {}
    for name in FILES:
        expected = manifest["files"][capture_key + "/" + name]
        path = capture / name
        if (
            path.stat().st_size != expected["bytes"]
            or digest(path) != expected["sha256"]
        ):
            raise ValueError("preserved source hash/size differs: " + name)
        verified[name] = expected
    return verified


def trade(message):
    price, size = Decimal(str(message["price"])), Decimal(str(message["size"]))
    if not price.is_finite() or not size.is_finite() or min(price, size) <= 0:
        raise ValueError("invalid preserved trade amount")
    return price, size, message.get("side")


def reconcile(matches, rest, heartbeats):
    if len(heartbeats) < 2:
        return dict(passed=False, reason="insufficient_heartbeats")
    low, high = (
        int(heartbeats[0]["message"]["last_trade_id"]),
        int(heartbeats[-1]["message"]["last_trade_id"]),
    )
    if high < low or high - low > MAX_ID_SPAN:
        raise ValueError("heartbeat trade-ID span is invalid or exceeds replay bound")
    expected = set(range(low + 1, high + 1))
    missing_ws = expected - matches.keys()
    missing_rest = expected - rest.keys()
    mismatch = [
        tid
        for tid in expected & matches.keys() & rest.keys()
        if matches[tid]["trade"] != rest[tid]
    ]
    return dict(
        passed=not (missing_ws or missing_rest or mismatch),
        reason=None,
        low_exclusive=low,
        high_inclusive=high,
        expected_ids=len(expected),
        missing_ws_ids=sorted(missing_ws),
        missing_rest_ids=sorted(missing_rest),
        mismatch_ids=sorted(mismatch),
    )


def coverage_spans(matches, heartbeats, reconciliation):
    """Retrospective interior only: ordered watermarks/receipts and full ID reconciliation."""
    if not reconciliation["passed"]:
        return []
    intervals = []
    for a, b in zip(heartbeats, heartbeats[1:]):
        start, end = a["receipt_ts_ms"], b["receipt_ts_ms"]
        if (
            end <= start
            or end - start > GRID
            or int(b["message"]["last_trade_id"]) < int(a["message"]["last_trade_id"])
        ):
            continue
        if intervals and intervals[-1][1] == start:
            intervals[-1][1] = end
        else:
            intervals.append([start, end])
    aligned = [
        [((a + GRID - 1) // GRID) * GRID, (b // GRID) * GRID] for a, b in intervals
    ]
    aligned = [(a, b) for a, b in aligned if a < b]
    low, high = reconciliation["low_exclusive"], reconciliation["high_inclusive"]
    bad_buckets = sorted(
        {
            r["receipt"] // GRID * GRID
            for tid, r in matches.items()
            if not low < tid <= high
        }
    )
    for bad in bad_buckets:
        split = []
        for a, b in aligned:
            if bad >= b or bad + GRID <= a:
                split.append((a, b))
            else:
                if a < bad:
                    split.append((a, bad))
                if bad + GRID < b:
                    split.append((bad + GRID, b))
        aligned = split
    return aligned


def near(actual, expected):
    if actual is None or abs(Decimal(str(actual)) - expected) > Decimal("0.000001"):
        raise ValueError(
            f"volume differs by more than one micro-dollar: {actual}, {expected}"
        )


def verify(capture, manifest_path, capture_key, output):
    capture, manifest_path, output = map(Path, (capture, manifest_path, output))
    source_hashes = verify_source(capture, manifest_path, capture_key)
    metadata = json.loads((capture / "capture.json").read_text(encoding="utf-8"))
    audit = json.loads((capture / "REPORT.json").read_text(encoding="utf-8"))
    raw_manifest = json.loads((capture / "MANIFEST.json").read_text(encoding="utf-8"))
    if set(raw_manifest["sha256"]) != {
        "capture.json",
        "websocket.jsonl.gz",
        "rest.jsonl.gz",
    }:
        raise ValueError("unexpected internal manifest paths")
    for name, want in raw_manifest["sha256"].items():
        if digest(capture / name) != want:
            raise ValueError("capture internal manifest mismatch")
    if (
        metadata.get("completed") is not True
        or metadata.get("elapsed_seconds", float("inf")) > 3605
    ):
        raise ValueError("one completed bounded capture required")
    if (
        metadata.get("reconnects")
        or metadata.get("errors")
        or audit.get("errors")
        or audit.get("rest_request_errors")
    ):
        raise ValueError(
            "source has transport/parser/REST errors; no coverage assertions generated"
        )
    products = metadata["products"]
    if not products or len(products) != len(set(products)):
        raise ValueError("nonempty unique product list required")
    if output.resolve().is_relative_to(capture.resolve()):
        raise ValueError("replay outputs must be outside the preserved capture")
    output.mkdir(parents=True, exist_ok=False)
    store = ReplayStore(output / "replay.sqlite", create=True)
    matches = {p: {} for p in products}
    heartbeats = {p: [] for p in products}
    counts = defaultdict(Counter)
    total = 0
    first_receipt = None
    last_receipt = None
    acknowledgments = []
    connections = set()
    try:
        for row in records(capture / "websocket.jsonl.gz"):
            total += 1
            if total > MAX_PACKETS:
                raise ValueError("packet bound exceeded; capture not truncated")
            store.ingest(row)
            first_receipt = (
                row["receipt_ts_ms"] if first_receipt is None else first_receipt
            )
            last_receipt = row["receipt_ts_ms"]
            message = row["message"]
            pid = message.get("product_id")
            kind = message.get("type")
            connections.add(row.get("connection_id"))
            if kind == "subscriptions":
                acknowledgments.append(row)
            if kind == "error":
                raise ValueError("preserved WS error")
            if pid not in matches:
                continue
            counts[pid][kind] += 1
            if kind == "heartbeat":
                heartbeats[pid].append(row)
            if kind == "match" and row.get("source", "ws") == "ws":
                tid = int(message["trade_id"])
                value = trade(message)
                if tid in matches[pid] and matches[pid][tid]["trade"] != value:
                    raise ValueError("conflicting preserved trade ID")
                matches[pid].setdefault(
                    tid, dict(trade=value, receipt=row["receipt_ts_ms"])
                )
        if not total or total != metadata["messages"]:
            raise ValueError("capture message count mismatch")
        if len(connections) != 1 or None in connections or len(acknowledgments) != 1:
            raise ValueError(
                "this bounded adapter requires one acknowledged connection"
            )
        ack = acknowledgments[0]
        channels = {
            c["name"]: set(c.get("product_ids", [])) for c in ack["message"]["channels"]
        }
        if any(
            not set(products) <= channels.get(name, set())
            for name in ("ticker", "matches", "heartbeat")
        ):
            raise ValueError("required product/channel membership was not acknowledged")
        rest = {p: {} for p in products}
        rest_rows = 0
        latest_source_receipt = last_receipt
        for row in records(capture / "rest.jsonl.gz"):
            if row.get("error"):
                raise ValueError("saved REST error")
            pid = row["product_id"]
            latest_source_receipt = max(latest_source_receipt, row["receipt_ts_ms"])
            for message in row.get("trades", []):
                rest_rows += 1
                if rest_rows > MAX_REST_ROWS:
                    raise ValueError("REST row bound exceeded")
                if pid not in rest:
                    raise ValueError("unexpected REST product")
                tid = int(message["trade_id"])
                value = trade(message)
                if tid in rest[pid] and rest[pid][tid] != value:
                    raise ValueError("conflicting REST trade ID")
                rest[pid][tid] = value
        spans = []
        reconciliations = {}
        amounts = {}
        summary = {}
        evidence_hash = source_hashes["REPORT.json"]["sha256"]
        for pid in products:
            original = audit["products"][pid]
            amount = sum(
                (r["trade"][0] * r["trade"][1] for r in matches[pid].values()),
                Decimal(0),
            )
            if len(matches[pid]) != original["unique_matches"] or amount != Decimal(
                original["match_quote_usd"]
            ):
                raise ValueError(
                    "raw match count/volume disagrees with preserved audit: " + pid
                )
            if dict(counts[pid]) != original["messages"]:
                raise ValueError("product message counts differ")
            if any(a > b for a, b in zip(matches[pid], list(matches[pid])[1:])):
                raise ValueError(
                    "reordered match IDs need separate receipt-coverage policy"
                )
            reconciliation = reconcile(matches[pid], rest[pid], heartbeats[pid])
            reconciliations[pid] = reconciliation
            eligible = coverage_spans(matches[pid], heartbeats[pid], reconciliation)
            eligible = [
                (max(a, ((ack["receipt_ts_ms"] + GRID - 1) // GRID) * GRID), b)
                for a, b in eligible
            ]
            eligible = [(a, b) for a, b in eligible if a < b]
            if original["coverage_verdict"] != "rest_reconciled":
                eligible = []
            for start, end in eligible:
                item = dict(
                    product=pid,
                    start=start,
                    end=end,
                    verified=True,
                    evidence=f"retrospective only; source audit SHA256 {evidence_hash}; independently reconciled IDs and bounded heartbeat continuity",
                )
                spans.append(item)
            amounts[pid] = amount
        available = time.time_ns() // 1000000
        if available < latest_source_receipt:
            raise ValueError("current clock precedes the preserved evidence")
        for item in spans:
            item["available"] = available
            store.add_health(**item)
        write(output / "retrospective_health.json", spans)
        store.finalize(
            dict(
                source_files=source_hashes,
                transfer_manifest_sha256=digest(manifest_path),
                replay_adapter_version=VERSION,
                replay_adapter_sha256=hashlib.sha256(
                    Path(__file__).read_text(encoding="utf-8").encode("utf-8")
                ).hexdigest(),
                retrospective_health_available_ts_ms=available,
                feed_gate_pass=False,
            )
        )
        start = ((first_receipt + GRID - 1) // GRID) * GRID + GRID
        end = last_receipt // GRID * GRID
        for pid in products:
            expected = matches[pid]
            db = store.db.execute(
                "SELECT COUNT(*),COALESCE(SUM(usd),0) FROM trades WHERE product=?",
                (pid,),
            ).fetchone()
            if db[0] != len(expected):
                raise ValueError("recorder unique trade count mismatch")
            near(db[1], amounts[pid])
            results = Counter()
            old_count = 0
            for cutoff in range(start, end + 1, GRID):
                old = store.snapshot(pid, cutoff)
                if old["coverage_verified"] or old["trade_count"] is not None:
                    raise ValueError(
                        "retrospective coverage leaked into original as-of"
                    )
                old_count += 1
                snapshot = store.snapshot(pid, cutoff, asof=available)
                results["grid_cutoffs"] += 1
                if snapshot["coverage_verified"]:
                    bucket = [
                        r
                        for r in expected.values()
                        if cutoff - GRID <= r["receipt"] < cutoff
                    ]
                    if snapshot["trade_count"] != len(bucket):
                        raise ValueError("bucket count mismatch")
                    near(
                        snapshot["quote_volume_usd"],
                        sum(
                            (r["trade"][0] * r["trade"][1] for r in bucket), Decimal(0)
                        ),
                    )
                    buy = sum(
                        (
                            r["trade"][0] * r["trade"][1]
                            for r in bucket
                            if r["trade"][2] == "sell"
                        ),
                        Decimal(0),
                    )
                    sell = sum(
                        (
                            r["trade"][0] * r["trade"][1]
                            for r in bucket
                            if r["trade"][2] == "buy"
                        ),
                        Decimal(0),
                    )
                    near(snapshot["taker_buy_usd"], buy)
                    near(snapshot["taker_sell_usd"], sell)
                    if snapshot["trade_count_at_bucket_start"] != sum(
                        r["receipt"] == cutoff - GRID for r in bucket
                    ):
                        raise ValueError("boundary trade count mismatch")
                    results["retrospectively_verified_buckets"] += 1
                    results["healthy_zero_trade_buckets"] += int(not bucket)
                results["fresh_midpoint_buckets"] += int(snapshot["mid"] is not None)
                results["size_eligible_buckets"] += int(snapshot["bbo_size_available"])
                results["signed_flow_unavailable_buckets"] += int(
                    snapshot["coverage_verified"] and not snapshot["flow_available"]
                )
                if snapshot["reason"]:
                    results["reason_" + snapshot["reason"]] += 1
                if store.snapshot(pid, cutoff) != old:
                    raise ValueError("original as-of changed")
            live_baseline = build_baseline(store, pid, end)
            sigma_start = (end - 35000) // 60000 * 60000 - 3600000
            summary[pid] = dict(
                unique_live_matches=db[0],
                audit_unique_matches=audit["products"][pid]["unique_matches"],
                exact_raw_quote_usd=str(amounts[pid]),
                recorder_quote_usd=db[1],
                original_asof_unverified_cutoffs=old_count,
                retrospective_statistics=dict(results),
                last_capture_anchor_baseline_status=live_baseline["status"],
                last_capture_anchor_baseline_reason=live_baseline["reason"],
                required_sigma_history_starts_before_capture=sigma_start
                < first_receipt,
                sigma_required_start_ts_ms=sigma_start,
                original_mapping_verdict=audit["products"][pid]["mapping_verdict"],
            )
        verify_source(capture, manifest_path, capture_key)
        occupied = store.db.execute("SELECT COUNT(*) FROM micro_bars_5s").fetchone()[0]
        identity = store.provenance()
    except Exception as exc:
        write(
            output / "FAILURE.json",
            dict(
                version=VERSION,
                error=type(exc).__name__,
                message=str(exc),
                feed_gate_pass=False,
                new_capture=False,
            ),
        )
        raise
    finally:
        store.close()
    result = dict(
        version=VERSION,
        scope="single_preserved_capture_receipt_replay_no_return_labels_or_fitting",
        source_capture_key=capture_key,
        source_files=source_hashes,
        source_capture_code_commit=metadata["code_commit"],
        source_capture_elapsed_seconds=metadata["elapsed_seconds"],
        source_capture_started_utc=metadata["started_utc"],
        source_capture_ended_utc=metadata["ended_utc"],
        replay_utc=datetime.now(timezone.utc).isoformat(),
        retrospective_health_available_ts_ms=available,
        packets_replayed=total,
        rest_trade_rows_read=rest_rows,
        occupied_buckets=occupied,
        database_bytes=(output / "replay.sqlite").stat().st_size,
        producer_identity=identity,
        products=summary,
        reconciliation=reconciliations,
        original_hour_gate_pass=audit["hour_gate_pass"],
        feed_gate_pass=False,
        original_contemporaneous_coverage_available=False,
        study_frozen=False,
        fitting_allowed=False,
        new_capture=False,
        historical_outcome_comparison_rerun=False,
        live_changes=False,
        limitations=[
            "Health asserted only at current verification time, never backdated",
            "Only aligned interior receipt buckets with ordered reconciled IDs and bounded heartbeat continuity are asserted",
            "Boundary/outside-watermark buckets are excluded; quote age remains independently enforced",
            "This one-hour audit does not provide the required pre-trigger baseline warmup",
            "No production throughput or all-product storage extrapolation; no live health monitor is certified",
        ],
    )
    write(output / "REPLAY_REPORT.json", result)
    write(
        output / "ARTIFACT_MANIFEST.json",
        dict(
            files={
                name: dict(
                    bytes=(output / name).stat().st_size, sha256=digest(output / name)
                )
                for name in (
                    "replay.sqlite",
                    "retrospective_health.json",
                    "REPLAY_REPORT.json",
                )
            }
        ),
    )
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--capture-key", required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    result = verify(args.capture, args.manifest, args.capture_key, args.out_dir)
    print(
        json.dumps(
            {
                k: result[k]
                for k in (
                    "packets_replayed",
                    "occupied_buckets",
                    "database_bytes",
                    "original_hour_gate_pass",
                    "feed_gate_pass",
                )
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
