"""Single-socket Coinbase Exchange source and latency pilot."""

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import subprocess
import time

from instant_input_evidence import _file_sha
from instant_stream_journal import StreamJournal, read_segment
from instant_timed_features import _book_pressure, build_timed_features


VERSION = "instant-source-pilot-v1"
URL = "wss://ws-feed.exchange.coinbase.com"
PRODUCTS = ("BTC-USD", "SOL-USD", "ALCX-USD", "AURORA-USD")
CHANNELS = ("level2_batch", "matches", "heartbeat", "ticker")
DURATION_S = 67 * 60
WARMUP_MS = 62 * 60000
PROBE_MS = 30000
LATER_ASOF_MS = 5000
ACK_TIMEOUT_S = 20
IDLE_TIMEOUT_S = 15
MAX_CONNECTIONS = 2
SOFT_PACKETS = 99990
SOFT_RECORD_BYTES = 240 * 1024 * 1024


def utc_ms():
    return time.time_ns() // 1000000


def _summary(values):
    if not values:
        return {"n": 0}
    ordered = sorted(values)
    return dict(
        n=len(ordered),
        p50_ms=round(ordered[math.ceil(len(ordered) * 0.5) - 1], 3),
        p95_ms=round(ordered[math.ceil(len(ordered) * 0.95) - 1], 3),
        p99_ms=round(ordered[math.ceil(len(ordered) * 0.99) - 1], 3),
        max_ms=round(ordered[-1], 3),
    )


def _exchange_ms(value):
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value)
        return parsed.timestamp() * 1000 if parsed.tzinfo else None
    except (ValueError, OverflowError, OSError):
        return None


class PilotCallbacks:
    """Socket callbacks run on the same thread as the journal writer."""

    def __init__(self, journal, *, monotonic_ns=time.monotonic_ns):
        self.journal = journal
        self.monotonic_ns = monotonic_ns
        self.connection = None
        self.ack = None
        self.frames = Counter()
        self.metrics = defaultdict(lambda: defaultdict(list))
        self.sides = defaultdict(dict)

    def on_open(self, socket):
        self.ack = None
        self.connection = self.journal.open_connection()
        socket.send(
            json.dumps(dict(type="subscribe", product_ids=PRODUCTS, channels=CHANNELS))
        )

    def on_message(self, raw):
        started = self.monotonic_ns()
        receipt = self.journal.receive(self.connection, raw)
        elapsed = (self.monotonic_ns() - started) / 1000000
        kind, product = receipt.message_type, receipt.product_id
        group = f"{kind}:{product}" if product in PRODUCTS else kind
        self.frames[group] += 1
        metrics = self.metrics[group]
        metrics["callback_through_commit"].append(elapsed)
        metrics["receipt_to_processing"].append(
            receipt.processing_completed_ts_ms - receipt.receipt_ts_ms
        )
        metrics["processing_to_commit_observation"].append(
            receipt.commit_observed_ts_ms - receipt.processing_completed_ts_ms
        )
        exchange = _exchange_ms(receipt.exchange_time)
        if exchange is not None:
            metrics["exchange_stamp_to_callback"].append(
                receipt.receipt_ts_ms - exchange
            )
        if kind in ("match", "ticker") and product in PRODUCTS:
            message = json.loads(raw)
            trade_id, side = message.get("trade_id"), message.get("side")
            if type(trade_id) is int and side in ("buy", "sell"):
                self.sides[(product, trade_id)].setdefault(kind, side)
        if kind == "subscriptions":
            ticker_products = {
                product
                for entry in json.loads(raw)["channels"]
                if entry["name"] == "ticker"
                for product in entry["product_ids"]
            }
            if (
                set(PRODUCTS)
                <= ticker_products & self.journal.evidence.book.monitor.active
            ):
                self.ack = receipt.receipt_ts_ms

    def on_close(self, *, reason="socket_closed"):
        if self.journal.connection_active:
            self.journal.end_connection(self.connection, reason=reason)
        self.connection = None

    def report(self):
        side_pairs = {pid: Counter() for pid in PRODUCTS}
        for (pid, _), sides in self.sides.items():
            if {"match", "ticker"} <= sides.keys():
                side_pairs[pid]["paired"] += 1
                side_pairs[pid][
                    "opposite" if sides["match"] != sides["ticker"] else "same"
                ] += 1
        return dict(
            frames=dict(self.frames),
            latencies={
                group: {
                    metric: {
                        **_summary(values),
                        "negative_n": sum(value < 0 for value in values),
                    }
                    for metric, values in by_metric.items()
                }
                for group, by_metric in self.metrics.items()
            },
            ticker_match_sides={pid: dict(side_pairs[pid]) for pid in PRODUCTS},
        )


def capture(
    journal,
    connect,
    *,
    monotonic=time.monotonic,
    monotonic_ns=time.monotonic_ns,
    timeout_errors=(TimeoutError,),
    transport_errors=(OSError,),
    duration_s=DURATION_S,
    packet_stop=SOFT_PACKETS,
    byte_stop=SOFT_RECORD_BYTES,
    progress=print,
):
    """Run the callback path with injectable transport and clocks for dry runs."""
    callbacks = PilotCallbacks(journal, monotonic_ns=monotonic_ns)
    first_ack = deadline = None
    last_progress = monotonic()
    stop = "transport_unavailable"
    attempts = []
    for _ in range(MAX_CONNECTIONS):
        if deadline is not None and monotonic() >= deadline:
            stop = "duration"
            break
        socket = None
        attempt = {}
        attempts.append(attempt)
        close_reason = "socket_closed"
        try:
            socket = connect()
            callbacks.on_open(socket)
            attempt["connection_id"] = callbacks.connection
            opened = last_frame = monotonic()
            while True:
                now = monotonic()
                if deadline is not None and now >= deadline:
                    stop = "duration"
                    break
                if callbacks.ack is None and now - opened >= ACK_TIMEOUT_S:
                    stop = "subscription_timeout"
                    close_reason = "transport_error"
                    break
                if now - last_frame >= IDLE_TIMEOUT_S:
                    stop = "transport_idle"
                    close_reason = "transport_error"
                    break
                try:
                    raw = socket.recv()
                except timeout_errors:
                    continue
                if raw in ("", b""):
                    stop = "remote_close"
                    break
                last_frame = monotonic()
                callbacks.on_message(raw)
                if not journal.connection_active:
                    stop = "exchange_or_source_error"
                    break
                if callbacks.ack is not None:
                    attempt.setdefault("ack_ts_ms", callbacks.ack)
                    if first_ack is None:
                        first_ack = callbacks.ack
                        deadline = monotonic() + duration_s
                        progress(
                            f"Subscriptions acknowledged for {len(PRODUCTS)} products.",
                            flush=True,
                        )
                if (
                    journal.packet_count >= packet_stop
                    or journal.record_bytes >= byte_stop
                ):
                    stop = (
                        "packet_budget"
                        if journal.packet_count >= packet_stop
                        else "byte_budget"
                    )
                    break
                if monotonic() - last_progress >= 60:
                    progress(
                        f"{journal.packet_count} packets committed, {journal.record_bytes} logical bytes.",
                        flush=True,
                    )
                    last_progress = monotonic()
        except transport_errors as exc:
            stop = "transport_error"
            attempt["error"] = str(exc)
            close_reason = "transport_error"
        except KeyboardInterrupt:
            stop = "interrupted"
        except Exception as exc:
            stop = "journal_failure" if journal.evidence.failed else "callback_failure"
            attempt["error"] = f"{type(exc).__name__}: {exc}"
        finally:
            try:
                callbacks.on_close(reason=close_reason)
            except Exception as exc:
                stop = "journal_failure"
                attempt["close_error"] = f"{type(exc).__name__}: {exc}"
            finally:
                if socket is not None:
                    try:
                        socket.close(timeout=1)
                    except transport_errors as exc:
                        attempt["socket_close_error"] = str(exc)
        attempt["stop"] = stop
        if first_ack is None or stop not in (
            "remote_close",
            "transport_idle",
            "transport_error",
        ):
            break
    return dict(
        stop=stop, first_ack_ts_ms=first_ack, attempts=attempts, **callbacks.report()
    )


def _coverage(recorder, first_ack, stop_ts):
    probes = list(
        range(
            ((first_ack + PROBE_MS - 1) // PROBE_MS + 1) * PROBE_MS,
            stop_ts - LATER_ASOF_MS + 1,
            PROBE_MS,
        )
    )
    by_product = {}
    for product in PRODUCTS:
        raw = [p for p in recorder.book.monitor.proofs if p["product_id"] == product]
        proofs = Counter(
            (
                "reconciled"
                if p.get("supersedes_end_heartbeat_seqs")
                else "strict_verified" if p["verified"] else p["reason"]
            )
            for p in raw
        )
        views = {}
        for lag in (0, LATER_ASOF_MS):
            quotes, matches, pressure = Counter(), Counter(), Counter()
            quote_ages, proof_lags = [], []
            for cutoff in probes:
                asof = cutoff + lag
                quote, _ = recorder._quote_at(product, cutoff, asof)
                quotes["ready" if quote["available"] else quote["reason"]] += 1
                if quote["available"]:
                    quote_ages.append(quote["observation_age_ms"])
                _, _, reason, available = recorder._trade_window(
                    product, cutoff - PROBE_MS, cutoff, asof
                )
                matches[reason or "ready"] += 1
                if available is not None:
                    proof_lags.append(available - cutoff)
                book = _book_pressure(
                    recorder, product, cutoff - PROBE_MS, cutoff, asof, 1
                )
                pressure[book.get("reason", "ready")] += 1
            views[str(lag)] = dict(
                quote=dict(quotes),
                trade_window=dict(matches),
                sampled_book_window=dict(pressure),
                ready_quote_age=_summary(quote_ages),
                ready_proof_lag_from_cutoff=_summary(proof_lags),
            )
        by_product[product] = dict(
            probes=len(probes),
            proof_counts=dict(proofs),
            asof_offset_ms=views,
            first_receipt_matches=sum(t.product_id == product for t in recorder.trades),
        )
    warm_cutoff = next((t for t in probes if t >= first_ack + WARMUP_MS), None)
    warmup = dict(first_post_warmup_cutoff_ts_ms=warm_cutoff, readiness={})
    if warm_cutoff is not None:
        for product in PRODUCTS:
            started = time.monotonic_ns()
            row = build_timed_features(
                recorder, product, warm_cutoff, "up", asof=warm_cutoff + LATER_ASOF_MS
            )
            warmup["readiness"][product] = dict(
                features={
                    key: value.get("reason", "ready")
                    for key, value in row["features"].items()
                },
                baseline={
                    name: row["baseline"][name].get("reason", "ready")
                    for name in ("volatility", "pace")
                },
                post_capture_calculation_ms=round(
                    (time.monotonic_ns() - started) / 1000000, 3
                ),
            )
    return dict(by_product=by_product, warmup=warmup)


def main():
    import websocket

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    out = args.out_dir.resolve()
    out.mkdir(parents=True, exist_ok=False)
    db_path = out / "capture.sqlite"
    first_cutoff = (utc_ms() // 5000 + 1) * 5000
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    metadata = dict(
        version=VERSION,
        code_commit=commit,
        started_utc=datetime.now(timezone.utc).isoformat(),
        products=PRODUCTS,
        channels=CHANNELS,
        endpoint=URL,
        seconds=DURATION_S,
        packet_stop=SOFT_PACKETS,
        logical_byte_stop=SOFT_RECORD_BYTES,
        max_connections=MAX_CONNECTIONS,
        websocket_client=websocket.__version__,
    )
    (out / "PLAN.json").write_text(
        json.dumps(metadata, indent=2) + "\n", encoding="utf-8"
    )

    def connect():
        socket = websocket.create_connection(URL, timeout=5, enable_multithread=False)
        socket.settimeout(2)
        return socket

    monotonic_start = time.monotonic()
    with StreamJournal(
        db_path, PRODUCTS, first_cutoff, first_cutoff + 4320000
    ) as journal:
        result = capture(
            journal,
            connect,
            timeout_errors=(websocket.WebSocketTimeoutException,),
            transport_errors=(OSError, websocket.WebSocketException),
        )
        stop_ts = utc_ms()
        elapsed = time.monotonic() - monotonic_start
        result["stop_ts_ms"] = stop_ts
        result["elapsed_seconds"] = round(elapsed, 3)
        result["logical_record_bytes"] = journal.record_bytes
        result["coverage"] = None
        if not journal.evidence.failed:
            journal.finish()
            if result["first_ack_ts_ms"] is not None:
                result["coverage"] = _coverage(
                    journal.evidence, result["first_ack_ts_ms"], stop_ts
                )
    result.update(metadata)
    result["segment"] = read_segment(db_path)
    result["journal_sha256"] = _file_sha(db_path)
    result["journal_bytes"] = db_path.stat().st_size
    result["full_feed_verified"] = False
    result["feed_gate_pass"] = False
    result["fitting_allowed"] = False
    result["external_publication_measured"] = False
    (out / "REPORT.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )
    print(
        f"Pilot stopped: {result['stop']}. Report at {out / 'REPORT.json'}", flush=True
    )


if __name__ == "__main__":
    main()
