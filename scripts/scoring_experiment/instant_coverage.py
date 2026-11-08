"""Offline, evidence-timed trade coverage monitor. No sockets or live hooks.

Heartbeat ID reconciliation is a scoped receipt/ID check, not authentication
or proof of book continuity. Processing time is measured now on replay; it
must never be replaced by the historical receipt time.
"""

from __future__ import annotations

import argparse
from bisect import bisect_left
from collections import Counter
from decimal import Decimal, InvalidOperation
import gzip
import hashlib
import json
from pathlib import Path
import time

VERSION = "instant-coverage-monitor-v1-draft-amendment-1"
CONTRACT = (
    Path(__file__).resolve().parents[2]
    / "docs/research/INSTANT_COVERAGE_CONTRACT_V1_DRAFT.json"
)
MAX_PACKETS = 100000
WARMUP_PACKET_LIMIT = 250000
MAX_ID_SPAN = 100000
MAX_HEARTBEAT_GAP_MS = 5000
# Amendment 1: adjacent failed proofs may be re-checked as one span. One race
# spans two proofs, so four allows two consecutive races. Engineering limits,
# not fitted to outcomes; the span limit also bounds added proof latency.
MAX_MERGED_PROOFS = 4
MAX_MERGED_SPAN_MS = 10000
MERGEABLE_REASONS = ("missing_live_match_ids", "receipt_ids_outside_watermarks")
INTERVAL_SCOPE = "receipt_interval_ws_trade_ids_only"
MERGED_SCOPE = "merged_adjacent_receipt_intervals_ws_trade_ids_only"


def _integer(value):
    if type(value) is not int or value < 0:
        raise ValueError("nonnegative integer required")
    return value


def _hash(path):
    result = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def _amount(value):
    if isinstance(value, bool):
        raise ValueError("invalid match amount")
    try:
        result = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError("invalid match amount") from exc
    if not result.is_finite() or result <= 0:
        raise ValueError("invalid match amount")
    return result


class CoverageMonitor:
    """Retain bounded evidence and answer known-at queries without rewriting them.

    clock_ms is injectable for deterministic tests. It is a trusted processing
    clock, not a way to authenticate historical knowledge. CLI always uses now.
    Results deliberately cannot be passed to ReplayStore.add_health: this
    monitor verifies trades, not quotes, queue durability or exchange latency.
    """

    def __init__(
        self, products, *, quote_channel="ticker", clock_ms=None, packet_limit=None
    ):
        if (
            packet_limit is not None
            and not 1 <= _integer(packet_limit) <= WARMUP_PACKET_LIMIT
        ):
            raise ValueError("coverage packet limit exceeds the supported range")
        self._packet_limit = packet_limit
        if (
            not isinstance(products, (list, tuple))
            or not products
            or len(products) > 32
            or any(not isinstance(p, str) or not p for p in products)
            or len(set(products)) != len(products)
            or quote_channel not in ("ticker", "level2_batch")
        ):
            raise ValueError(
                "explicit unique products and supported quote channel required"
            )
        raw = CONTRACT.read_text(encoding="utf-8").encode("utf-8")
        cfg = json.loads(raw)
        merge = cfg.get("reconciliation") or {}
        if (
            cfg["version"],
            cfg["max_packets"],
            cfg["max_id_span"],
            cfg["max_heartbeat_gap_ms"],
            merge.get("max_merged_proofs"),
            merge.get("max_merged_span_ms"),
            tuple(merge.get("mergeable_reasons", ())),
        ) != (
            VERSION,
            MAX_PACKETS,
            MAX_ID_SPAN,
            MAX_HEARTBEAT_GAP_MS,
            MAX_MERGED_PROOFS,
            MAX_MERGED_SPAN_MS,
            MERGEABLE_REASONS,
        ):
            raise ValueError("coverage contract and implementation differ")
        self.contract_sha256 = hashlib.sha256(raw).hexdigest()
        self.source_sha256 = hashlib.sha256(
            Path(__file__).read_text(encoding="utf-8").encode("utf-8")
        ).hexdigest()
        self.products = tuple(products)
        self.required_channels = {"matches", "heartbeat", quote_channel}
        self.clock_ms = clock_ms or (lambda: time.time_ns() // 1000000)
        self.last = None
        self.connection = None
        self.active = set()
        self.beats = {}
        # Continuity epoch per product, advanced at every lifecycle barrier in
        # receipt-sequence order: connection change, audit/transport/queue
        # failure, or lost/re-added required membership. Receipt milliseconds
        # and a reused connection ID cannot identify a barrier; this can.
        self.epochs = {p: 0 for p in products}
        self.seen = {}
        self.trades = {p: [] for p in products}
        self.times = {p: [] for p in products}
        self.proofs = []
        self.transport = []
        self.conflicts = []
        self.failed = False
        self.packet_count = 0

    def _state(self, product, receipt, known, seq, reason):
        self.transport.append(
            dict(
                product_id=product,
                receipt_ts_ms=receipt,
                available_ts_ms=known,
                receipt_seq=seq,
                connection_id=self.connection,
                reason=reason,
            )
        )

    def _barrier(self, products):
        for product in products:
            self.epochs[product] += 1
            self.beats.pop(product, None)

    def ingest(self, envelope):
        if self.failed:
            raise ValueError("failed monitor cannot accept more input")
        try:
            counts = tuple(
                len(rows) for rows in (self.proofs, self.transport, self.conflicts)
            )
            self._ingest(envelope)
            # The evidence is not known before its computation finishes. A
            # replay's processing clock is now, not the saved event receipt.
            finished = _integer(self.clock_ms())
            if finished < self.last[3]:
                raise ValueError("processing completion clock regressed")
            self.last = (*self.last[:3], finished)
            known = max(finished, self.last[1] + 1)
            for rows, count in zip(
                (self.proofs, self.transport, self.conflicts), counts
            ):
                for record in rows[count:]:
                    record["available_ts_ms"] = known
        except Exception:
            self.failed = True
            raise

    def _ingest(self, env):
        self.packet_count += 1
        limit = MAX_PACKETS if self._packet_limit is None else self._packet_limit
        if self.packet_count > limit:
            raise ValueError("packet bound exceeded; prefix is not a complete capture")
        seq, receipt, mono = map(
            _integer,
            (env["receipt_seq"], env["receipt_ts_ms"], env["receipt_monotonic_ns"]),
        )
        processed = _integer(self.clock_ms())
        if processed < receipt or (
            self.last
            and (
                seq != self.last[0] + 1
                or receipt < self.last[1]
                or mono < self.last[2]
                or processed < self.last[3]
            )
        ):
            raise ValueError("clock, receipt order or local logger sequence failed")
        self.last = (seq, receipt, mono, processed)
        # A receipt at x is excluded from state observed strictly before x.
        known = max(processed, receipt + 1)
        source = env.get("source", "ws")
        if source not in ("ws", "rest", "rest_recovery"):
            raise ValueError("unknown source; never disguise recovery as WebSocket")
        if source != "ws":
            return
        connection = env["connection_id"]
        if (
            type(connection) not in (int, str)
            or connection == ""
            or (type(connection) is int and connection < 0)
        ):
            raise ValueError("connection identity required")
        if connection != self.connection:
            self.connection = connection
            self.active.clear()
            self._barrier(self.products)
            for product in self.products:
                self._state(product, receipt, known, seq, "subscription_unconfirmed")
        message = env["message"]
        kind, product = message.get("type"), message.get("product_id")
        # scripts/coinbase_feed_audit.py records its failures as audit_* markers.
        if kind in ("connection_closed", "error", "queue_overflow") or (
            isinstance(kind, str) and kind.startswith("audit_")
        ):
            self.active.clear()
            self._barrier(self.products)
            for pid in self.products:
                self._state(pid, receipt, known, seq, kind)
            return
        if kind == "subscriptions":
            subscriptions = {}
            for channel in message["channels"]:
                name, ids = channel["name"], channel["product_ids"]
                if (
                    not isinstance(name, str)
                    or not isinstance(ids, list)
                    or any(not isinstance(p, str) for p in ids)
                ):
                    raise ValueError("invalid subscription acknowledgement")
                # Coinbase can acknowledge level2_batch under its legacy name.
                channel = "level2_batch" if name == "level2_50" else name
                subscriptions.setdefault(channel, set()).update(ids)
            active = {
                p
                for p in self.products
                if all(p in subscriptions.get(c, ()) for c in self.required_channels)
            }
            for pid in self.products:
                # Lost or newly (re)gained membership ends continuity; a
                # healthy repeated acknowledgement does not.
                if pid not in active or pid not in self.active:
                    self._barrier((pid,))
                self._state(
                    pid,
                    receipt,
                    known,
                    seq,
                    (
                        "awaiting_heartbeat"
                        if pid in active
                        else "subscription_unconfirmed"
                    ),
                )
            self.active = active
            return
        if product not in self.trades:
            return
        if kind == "match":
            trade_id = _integer(message["trade_id"])
            price, size = _amount(message.get("price")), _amount(message.get("size"))
            side = message.get("side")
            if side not in ("buy", "sell"):
                side = None
            key, signature = (product, trade_id), (price, size, side)
            if key in self.seen:
                old, first_receipt = self.seen[key]
                if old != signature:
                    self.conflicts.append(
                        dict(
                            product_id=product,
                            start_ts_ms=first_receipt,
                            end_ts_ms=receipt + 1,
                            available_ts_ms=known,
                        )
                    )
                return
            self.seen[key] = (signature, receipt)
            self.times[product].append(receipt)
            # Attribution keeps the first receipt time and its receipt-order
            # epoch; a barrier at the same millisecond never moves it.
            self.trades[product].append(
                (receipt, trade_id, connection, self.epochs[product])
            )
        elif kind == "heartbeat" and product in self.active:
            watermark = _integer(message["last_trade_id"])
            previous = self.beats.get(product)
            epoch = self.epochs[product]
            if previous:
                start, low, prior_seq, prior_epoch = previous
                if prior_epoch != epoch:
                    raise ValueError("baseline survived a continuity barrier")
                if receipt > start:
                    left, right = (
                        bisect_left(self.times[product], t) for t in (start, receipt)
                    )
                    ids = {
                        tid
                        for _, tid, owner, era in self.trades[product][left:right]
                        if owner == connection and era == epoch
                    }
                    delta = watermark - low
                    reason = None
                    if receipt - start > MAX_HEARTBEAT_GAP_MS:
                        reason = "heartbeat_gap"
                    elif delta < 0:
                        reason = "watermark_regression"
                    elif delta > MAX_ID_SPAN:
                        reason = "id_span_bound"
                    elif any(not low < tid <= watermark for tid in ids):
                        reason = "receipt_ids_outside_watermarks"
                    elif len(ids) != delta:
                        reason = "missing_live_match_ids"
                    self.proofs.append(
                        dict(
                            product_id=product,
                            start_ts_ms=start,
                            end_ts_ms=receipt,
                            available_ts_ms=known,
                            lower_trade_id_exclusive=low,
                            upper_trade_id_inclusive=watermark,
                            observed_unique_trade_count=len(ids),
                            expected_trade_count=max(delta, 0),
                            verified=reason is None,
                            reason=reason,
                            connection_id=connection,
                            continuity_epoch=epoch,
                            start_heartbeat_seq=prior_seq,
                            end_heartbeat_seq=seq,
                            scope=INTERVAL_SCOPE,
                        )
                    )
                    if reason in MERGEABLE_REASONS:
                        self._reconcile(product, connection, epoch)
                # Same-millisecond heartbeat baselines are ambiguous: retain the
                # older watermark so a new one cannot erase boundary trades.
                else:
                    self._state(
                        product, receipt, known, seq, "heartbeat_time_collision"
                    )
                    return
            self.beats[product] = (receipt, watermark, seq, epoch)
            self._state(product, receipt, known, seq, "heartbeat_observed")

    def _reconcile(self, product, connection, epoch):
        """Re-check the trailing run of adjacent failed proofs as one span.

        Only a heartbeat/match ordering race is repairable: the merged span must
        satisfy the same exact rule (expected IDs == unique IDs received on this
        connection), so a truly lost ID still fails. Trade receipt times and
        bucket counts are untouched. ingest stamps the merged proof with the
        closing heartbeat's processing completion, so nothing is backdated.
        """
        run = []
        for proof in reversed(self.proofs):
            if proof["product_id"] != product:
                continue
            # Verified intervals and earlier merged proofs have no reason, so
            # they end the run: merges stay disjoint and a nested race fails closed.
            if (
                len(run) == MAX_MERGED_PROOFS
                or proof["reason"] not in MERGEABLE_REASONS
                or proof["connection_id"] != connection
                or proof["continuity_epoch"] != epoch
                or (
                    run
                    and (
                        proof["end_ts_ms"] != run[-1]["start_ts_ms"]
                        or proof["upper_trade_id_inclusive"]
                        != run[-1]["lower_trade_id_exclusive"]
                    )
                )
            ):
                break
            run.append(proof)
        # Smallest closing run first, so two separate races stay separate proofs.
        for size in range(2, len(run) + 1):
            first, last = run[size - 1], run[0]
            start, end = first["start_ts_ms"], last["end_ts_ms"]
            low = first["lower_trade_id_exclusive"]
            high = last["upper_trade_id_inclusive"]
            if end - start > MAX_MERGED_SPAN_MS or high - low > MAX_ID_SPAN:
                return
            left, right = (bisect_left(self.times[product], t) for t in (start, end))
            ids = {
                tid
                for _, tid, owner, era in self.trades[product][left:right]
                if owner == connection and era == epoch
            }
            if ids != set(range(low + 1, high + 1)):
                continue
            self.proofs.append(
                dict(
                    product_id=product,
                    start_ts_ms=start,
                    end_ts_ms=end,
                    available_ts_ms=None,
                    lower_trade_id_exclusive=low,
                    upper_trade_id_inclusive=high,
                    observed_unique_trade_count=len(ids),
                    expected_trade_count=high - low,
                    verified=True,
                    reason=None,
                    connection_id=connection,
                    continuity_epoch=epoch,
                    start_heartbeat_seq=first["start_heartbeat_seq"],
                    end_heartbeat_seq=last["end_heartbeat_seq"],
                    scope=MERGED_SCOPE,
                    merged_proof_count=size,
                    supersedes_end_heartbeat_seqs=sorted(
                        p["end_heartbeat_seq"] for p in run[:size]
                    ),
                )
            )
            return

    def _validate_assessment(self, product, start, end, asof):
        if self.failed:
            raise ValueError("failed monitor cannot produce assessments")
        for value in (start, end, asof):
            _integer(value)
        if product not in self.trades or start >= end or asof < end:
            raise ValueError(
                "known product, completed interval and asof >= end required"
            )

    def assess(self, product, start, end, *, asof):
        self._validate_assessment(product, start, end, asof)
        state = next(
            (
                s
                for s in reversed(self.transport)
                if s["product_id"] == product and s["available_ts_ms"] <= asof
            ),
            None,
        )
        spans = [
            p
            for p in self.proofs
            if p["product_id"] == product
            and p["start_ts_ms"] < end
            and p["end_ts_ms"] > start
            and p["available_ts_ms"] <= asof
        ]
        conflict = any(
            c["product_id"] == product
            and c["start_ts_ms"] < end
            and c["end_ts_ms"] > start
            and c["available_ts_ms"] <= asof
            for c in self.conflicts
        )
        return self._assess_filtered(product, start, end, asof, state, spans, conflict)

    def _assess_filtered(self, product, start, end, asof, state, spans, conflict):
        transport_reason = (
            state["reason"] if state else "no_known_subscription_or_heartbeat"
        )
        if state and state["reason"] == "heartbeat_observed":
            transport_reason = (
                None
                if asof - state["receipt_ts_ms"] <= MAX_HEARTBEAT_GAP_MS
                else "stale_heartbeat"
            )
        # A failed proof is superseded only once a merged proof covering it is
        # known. The failed record itself is never rewritten.
        superseded = {
            seq
            for p in spans
            if p["scope"] == MERGED_SCOPE
            for seq in p["supersedes_end_heartbeat_seqs"]
        }
        spans = [
            p
            for p in spans
            if p["scope"] == MERGED_SCOPE or p["end_heartbeat_seq"] not in superseded
        ]
        reason = (
            "conflicting_trade_id"
            if conflict
            else next((p["reason"] for p in spans if not p["verified"]), None)
        )
        cursor, available, prior, merged_used = start, end, None, 0
        if reason is None:
            for span in sorted(spans, key=lambda p: (p["start_ts_ms"], p["end_ts_ms"])):
                if span["end_ts_ms"] <= cursor:
                    continue
                if span["start_ts_ms"] > cursor:
                    break
                # Touching timestamps alone do not prove the ID sequence
                # continued, and nothing joins across a continuity barrier.
                if prior and (
                    span["connection_id"] != prior["connection_id"]
                    or span["continuity_epoch"] != prior["continuity_epoch"]
                    or span["lower_trade_id_exclusive"]
                    != prior["upper_trade_id_inclusive"]
                ):
                    break
                prior = span
                merged_used += span["scope"] == MERGED_SCOPE
                cursor = span["end_ts_ms"]
                available = max(available, span["available_ts_ms"])
                if cursor >= end:
                    break
            if cursor < end:
                reason = "trade_coverage_not_yet_proven"
        return dict(
            version=VERSION,
            product_id=product,
            start_ts_ms=start,
            end_ts_ms=end,
            knowledge_asof_ts_ms=asof,
            receipt_id_check_passed=reason is None,
            receipt_id_check_reason=reason,
            receipt_id_check_available_ts_ms=available if reason is None else None,
            receipt_id_check_merged_proofs=merged_used if reason is None else 0,
            transport_observed_ok=transport_reason is None,
            transport_reason=transport_reason,
            full_feed_verified=False,
            quote_coverage_verified=False,
            quote_reason="order_book_not_verified_by_this_monitor",
            scope="offline_receipt_and_trade_id_evidence_not_live_eligibility",
            contract_sha256=self.contract_sha256,
            implementation_sha256=self.source_sha256,
        )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("packets", type=Path)
    parser.add_argument("--products", nargs="+", required=True)
    parser.add_argument(
        "--quote-channel", choices=("ticker", "level2_batch"), default="ticker"
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        required=True,
        help="new absent directory outside input directory",
    )
    args = parser.parse_args()
    source, output = args.packets.resolve(), args.out_dir.resolve()
    if output == source.parent or source.parent in output.parents:
        raise ValueError("output must be outside the preserved input directory")
    before = _hash(source)
    monitor = CoverageMonitor(args.products, quote_channel=args.quote_channel)
    output.mkdir(parents=True, exist_ok=False)
    try:
        opener = gzip.open if source.suffix == ".gz" else open
        with opener(source, "rt", encoding="utf-8") as stream:
            for line in stream:
                monitor.ingest(json.loads(line))
        if not monitor.packet_count:
            raise ValueError("empty input is not a completed coverage check")
        if _hash(source) != before:
            raise ValueError("source changed while checking")
        intervals = [p for p in monitor.proofs if p["scope"] == INTERVAL_SCOPE]
        repaired = {
            (p["product_id"], seq)
            for p in monitor.proofs
            if p["scope"] == MERGED_SCOPE
            for seq in p["supersedes_end_heartbeat_seqs"]
        }
        proof_path = output / "trade_coverage_proofs.jsonl"
        with proof_path.open("x", encoding="utf-8", newline="\n") as stream:
            for proof in monitor.proofs:
                stream.write(json.dumps(proof, sort_keys=True, allow_nan=False) + "\n")
        report = dict(
            version=VERSION,
            status="complete_offline_check_only",
            input_sha256=before,
            implementation_sha256=monitor.source_sha256,
            contract_sha256=monitor.contract_sha256,
            packet_count=monitor.packet_count,
            unique_ws_matches=len(monitor.seen),
            proof_count=len(intervals),
            verified_proofs=sum(p["verified"] for p in intervals),
            proof_reasons=dict(Counter(p["reason"] or "verified" for p in intervals)),
            merged_proofs=len(monitor.proofs) - len(intervals),
            failed_proofs_reconciled=len(repaired),
            failed_proofs_unreconciled=sum(
                not p["verified"]
                and (p["product_id"], p["end_heartbeat_seq"]) not in repaired
                for p in intervals
            ),
            products=list(monitor.products),
            required_channels=sorted(monitor.required_channels),
            first_proof_available_ts_ms=min(
                (p["available_ts_ms"] for p in monitor.proofs), default=None
            ),
            source_last_receipt_ts_ms=monitor.last[1] if monitor.last else None,
            proof_file_sha256=_hash(proof_path),
            conflicts=len(monitor.conflicts),
            full_feed_verified=False,
            feed_gate_pass=False,
            quote_coverage_verified=False,
            live_integration=False,
            timing="actual_offline_processing_clock_not_historical_receipt_backdating",
        )
        (output / "REPORT.json").write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        print(json.dumps(report, sort_keys=True))
    except Exception as exc:
        (output / "FAILURE.json").write_text(
            json.dumps(dict(status="failed", reason=str(exc))) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        raise


if __name__ == "__main__":
    main()
