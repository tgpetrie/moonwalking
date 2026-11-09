"""Bounded input-evidence ledger and complete planned-slot accounting.

Measured processing is replay time, never historical knowledge. Components
retain their narrow scopes; this stage cannot emit positive study eligibility.
"""

from dataclasses import asdict, dataclass
from decimal import Decimal
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import time

from instant_book import BookReplay
from instant_coverage import _integer


VERSION = "instant-input-evidence-v1-draft"
CONTRACT = (
    Path(__file__).resolve().parents[2]
    / "docs/research/INSTANT_INPUT_EVIDENCE_CONTRACT_V1_DRAFT.json"
)
GRID_MS = 5000
MAX_ROWS = 10000
BENCHMARK = "BTC-USD"
DIRECTIONS = ("up", "down")


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _sha(value):
    return hashlib.sha256(value).hexdigest()


def _packet_line(packet):
    return (_json(asdict(packet)) + "\n").encode("utf-8")


def _file_sha(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


@dataclass(frozen=True)
class PacketEvidence:
    receipt_seq: int
    receipt_ts_ms: int
    processing_started_ts_ms: int
    processing_completed_ts_ms: int
    available_ts_ms: int
    envelope_sha256: str


@dataclass(frozen=True)
class TradeEvidence:
    product_id: str
    trade_id: int
    receipt_seq: int
    receipt_ts_ms: int
    available_ts_ms: int
    connection_id: int | str
    continuity_epoch: int
    price: str
    size: str
    taker_side: str | None


@dataclass(frozen=True)
class SlotEvidence:
    product_id: str
    direction: str
    cutoff_ts_ms: int
    assessment_completed_ts_ms: int
    inventory_sha256: str
    components_json: str
    unavailable_reasons: tuple[str, ...]

    def to_dict(self):
        result = asdict(self)
        result["components"] = json.loads(result.pop("components_json"))
        result["eligibility_status"] = "unavailable"
        result["study_eligible"] = False
        return result


class InputEvidenceRecorder:
    """Static declared inventory plus measured packet/trade processing times.

    The clock is measured by default. Injectable clocks are trusted synthetic
    test inputs, not evidence that old packets were processed historically.
    Frozen cutoff cohorts cannot be rewritten by later messages or failures.
    """

    def __init__(
        self,
        products,
        first_cutoff,
        stop_cutoff,
        *,
        clock_ms=None,
        packet_limit=None,
        indexed=False,
        extended_capacity=False,
    ):
        for value in (first_cutoff, stop_cutoff):
            _integer(value)
        if (
            not isinstance(products, (list, tuple))
            or not products
            or len(products) > 32
            or any(not isinstance(p, str) or not p for p in products)
            or len(set(products)) != len(products)
            or BENCHMARK not in products
            or first_cutoff < 30000
            or first_cutoff % GRID_MS
            or stop_cutoff % GRID_MS
            or stop_cutoff <= first_cutoff
            or (stop_cutoff - first_cutoff) // GRID_MS * len(products) * 2 > MAX_ROWS
        ):
            raise ValueError(
                "bounded unique products including BTC and grid range required"
            )
        raw = CONTRACT.read_text(encoding="utf-8").encode("utf-8")
        cfg = json.loads(raw)
        if (
            cfg["version"] != VERSION
            or cfg["grid_ms"] != GRID_MS
            or cfg["max_inventory_rows"] != MAX_ROWS
            or cfg["max_products"] != 32
            or cfg["max_packets"] != 100000
            or cfg["benchmark"] != BENCHMARK
            or any(
                cfg[key] is not False
                for key in (
                    "positive_eligibility_supported",
                    "directional_report_adapter_supported",
                    "durable_publication_verified",
                    "full_feed_verified",
                    "feed_gate_pass",
                    "study_frozen",
                    "fitting_allowed",
                    "live_integration",
                )
            )
        ):
            raise ValueError("input-evidence contract and implementation differ")
        self.products = tuple(sorted(products))
        self.cutoffs = tuple(range(first_cutoff, stop_cutoff, GRID_MS))
        self.inventory = _json(
            dict(
                products=self.products,
                first_cutoff=first_cutoff,
                stop_cutoff=stop_cutoff,
                grid_ms=GRID_MS,
                directions=DIRECTIONS,
                benchmark=BENCHMARK,
            )
        )
        self.inventory_sha256 = _sha(self.inventory.encode("utf-8"))
        self.contract_sha256 = _sha(raw)
        self.source_sha256 = _sha(
            Path(__file__).read_text(encoding="utf-8").encode("utf-8")
        )
        self.clock = clock_ms or (lambda: time.time_ns() // 1000000)
        self.last_clock = None
        self.inventory_recorded_ts_ms = self._now()
        self.book = BookReplay(
            self.products,
            clock_ms=self._now,
            packet_limit=packet_limit,
            extended_capacity=extended_capacity,
        )
        self.packets = []
        self.trades = []
        self._packet_by_seq = {}
        self._cohorts = {}
        self.failed = False
        self.sealed = False
        self._index = None
        if indexed:
            from instant_evidence_index import EvidenceIndex

            self._index = EvidenceIndex(self)

    def _now(self):
        try:
            value = _integer(self.clock())
            if self.last_clock is not None and value < self.last_clock:
                raise ValueError("input-evidence processing clock regressed")
            self.last_clock = value
            return value
        except Exception:
            self.failed = True
            raise

    def _writable(self):
        if self.failed or self.sealed:
            raise ValueError("failed or sealed evidence recorder")

    def ingest(self, envelope):
        self._writable()
        try:
            started = self._now()
            # Detach from mutable caller buffers and retain a canonical hash.
            encoded = _json(envelope)
            env = json.loads(encoded)
            if not self.packets and env["receipt_seq"] != 1:
                raise ValueError(
                    "complete logger tape must start at receipt sequence 1"
                )
            old_count = len(self.book.monitor.seen)
            self.book.ingest(env)
            message = env["message"]
            trade = None
            if len(self.book.monitor.seen) > old_count:
                pid = message["product_id"]
                receipt, tid, connection, epoch = self.book.monitor.trades[pid][-1]
                price, size, side = self.book.monitor.seen[(pid, tid)][0]
                trade = dict(
                    product_id=pid,
                    trade_id=tid,
                    receipt_seq=env["receipt_seq"],
                    receipt_ts_ms=receipt,
                    connection_id=connection,
                    continuity_epoch=epoch,
                    price=str(price),
                    size=str(size),
                    taker_side={"buy": "sell", "sell": "buy"}.get(side),
                )
            finished = self._now()
            packet = PacketEvidence(
                env["receipt_seq"],
                env["receipt_ts_ms"],
                started,
                finished,
                max(finished, env["receipt_ts_ms"] + 1),
                _sha(encoded.encode("utf-8")),
            )
            self.packets.append(packet)
            self._packet_by_seq[packet.receipt_seq] = packet
            if trade:
                self.trades.append(
                    TradeEvidence(**trade, available_ts_ms=packet.available_ts_ms)
                )
            if self._index is not None:
                self._index.ingested(packet, self.trades[-1] if trade else None)
        except Exception:
            self.failed = True
            raise

    def _quote_at(self, product, cutoff, asof):
        self.book._validate_view(product, cutoff, asof)
        if self._index is None:
            state, transport = self.book._records_at(product, cutoff, asof)
        else:
            state, transport = self._index.quote_records(product, cutoff, asof)
        view = self.book._view_from_records(product, cutoff, asof, state, transport)
        used = ([state.receipt_seq] if state else []) + (
            [transport["receipt_seq"]] if transport else []
        )
        available = max(
            (self._packet_by_seq[s].available_ts_ms for s in used), default=None
        )
        quote_known = available is None or available <= asof
        quote_ready = view.book_state_available and quote_known
        quote = dict(
            available=quote_ready,
            reason=view.reason if quote_known else "quote_row_processing_incomplete",
            observation_ts_ms=view.observation_ts_ms,
            observation_age_ms=view.observation_age_ms,
            book_processing_available_ts_ms=view.available_ts_ms,
            bid=view.bid if quote_ready else None,
            ask=view.ask if quote_ready else None,
        )
        return quote, available if quote_ready else None

    def _prefix_at(self, asof):
        if self._index is not None:
            return self._index.prefix_at(asof)
        prefix = hashlib.sha256()
        for i, packet in enumerate(self.packets):
            if packet.available_ts_ms > asof:
                return i, prefix.hexdigest(), packet
            prefix.update(_packet_line(packet))
        return len(self.packets), prefix.hexdigest(), None

    def _book_window(self, product, start, end, asof):
        if self._index is not None:
            return self._index.book_window(product, start, end, asof)
        states = [
            state
            for state in self.book.history[product]
            if state.receipt_ts_ms < end
            and self._packet_by_seq[state.receipt_seq].available_ts_ms <= asof
        ]
        transport = [
            row
            for row in self.book.monitor.transport
            if row["product_id"] == product
            and row["receipt_ts_ms"] < end
            and self._packet_by_seq[row["receipt_seq"]].available_ts_ms <= asof
        ]
        return states, transport

    def _trade_window(self, product, start, cutoff, asof):
        if self._index is None:
            proof = self.book.monitor.assess(product, start, cutoff, asof=asof)
            intervals = [
                p
                for p in self.book.monitor.proofs
                if p["product_id"] == product
                and p["start_ts_ms"] < cutoff
                and p["end_ts_ms"] > start
                and p["available_ts_ms"] <= asof
            ]
            rows = [
                t
                for t in self.trades
                if t.product_id == product and start <= t.receipt_ts_ms < cutoff
            ]
        else:
            proof, intervals, rows = self._index.trade_window(
                product, start, cutoff, asof
            )
        known = [t for t in rows if t.available_ts_ms <= asof]
        proof_completion = max(
            (
                self._packet_by_seq[p["end_heartbeat_seq"]].available_ts_ms
                for p in intervals
            ),
            default=cutoff,
        )
        proof_rows_known = proof_completion <= asof and len(known) == len(rows)
        owners = {
            (p["connection_id"], p["continuity_epoch"])
            for p in intervals
            if p["verified"]
        }
        # Receipt milliseconds alone cannot place a trade on the safe side of
        # a barrier. Keep the first receipt, but never certify it using a proof
        # from the other epoch, even when the boundary timestamp is identical.
        continuity_ok = len(owners) == 1 and all(
            (t.connection_id, t.continuity_epoch) in owners for t in known
        )
        reason = proof["receipt_id_check_reason"]
        if reason is None:
            if not proof_rows_known:
                reason = "trade_row_processing_incomplete"
            elif not continuity_ok:
                reason = "trade_row_continuity_mismatch"
        return proof, known, reason, proof_completion if reason is None else None

    def _component(self, product, cutoff, asof):
        quote, _ = self._quote_at(product, cutoff, asof)
        proof, known, reason, _ = self._trade_window(
            product, cutoff - 30000, cutoff, asof
        )
        ids_ready = reason is None
        amounts = {
            side: sum(
                (
                    Decimal(t.price) * Decimal(t.size)
                    for t in known
                    if t.taker_side == side
                ),
                Decimal(0),
            )
            for side in ("buy", "sell", None)
        }
        return dict(
            feature_cutoff_ts_ms=cutoff,
            knowledge_asof_ts_ms=asof,
            later_diagnostic=asof > cutoff,
            quote=quote,
            trades_30s=dict(
                receipt_id_check_passed=ids_ready,
                reason=reason,
                known_unique_match_count=len(known),
                verified_trade_count=len(known) if ids_ready else None,
                quote_volume_usd=str(sum(amounts.values())) if ids_ready else None,
                taker_buy_usd=str(amounts["buy"]) if ids_ready else None,
                taker_sell_usd=str(amounts["sell"]) if ids_ready else None,
                unknown_side_usd=str(amounts[None]) if ids_ready else None,
                flow_available=ids_ready
                and all(t.taker_side is not None for t in known),
                proof_available_ts_ms=proof["receipt_id_check_available_ts_ms"],
            ),
            full_feed_verified=False,
            interval_quote_continuity_verified=False,
        )

    def component_evidence(self, product, cutoff, *, asof=None):
        """Explicit later diagnostics cannot replace frozen cutoff cohorts."""
        if self.failed:
            raise ValueError("failed evidence recorder")
        if (
            product not in self.products
            or type(cutoff) is not int
            or cutoff not in self.cutoffs
        ):
            raise ValueError("product/cutoff outside declared inventory")
        asof = cutoff if asof is None else _integer(asof)
        if asof < cutoff or asof > self._now():
            raise ValueError(
                "diagnostic knowledge must be reached and not precede cutoff"
            )
        return self._component(product, cutoff, asof)

    def checkpoint(self, cutoff):
        if self.failed:
            raise ValueError("failed evidence recorder")
        if cutoff not in self.cutoffs or type(cutoff) is not int:
            raise ValueError("cutoff outside declared inventory")
        if cutoff in self._cohorts:
            return self._cohorts[cutoff]
        self._writable()
        if self._now() < cutoff:
            raise ValueError("cutoff has not been reached")
        try:
            components = {p: self._component(p, cutoff, cutoff) for p in self.products}
            # Encode before measuring the producer's own completion.
            payloads = {
                p: _json(dict(coin=components[p], benchmark=components[BENCHMARK]))
                for p in self.products
            }
            finished = self._now()
            rows = []
            for product in self.products:
                reasons = [
                    "baseline_evidence_not_implemented",
                    "feature_evidence_not_implemented",
                    "publication_policy_unfrozen",
                    "full_feed_evidence_not_verified",
                ]
                if self.inventory_recorded_ts_ms >= self.cutoffs[0]:
                    reasons.append("inventory_recorded_after_first_cutoff")
                if finished > cutoff:
                    reasons.append("assessment_completed_after_cutoff")
                for name, comp in (
                    ("coin", components[product]),
                    ("benchmark", components[BENCHMARK]),
                ):
                    if not comp["quote"]["available"]:
                        reasons.append(f"{name}:quote:{comp['quote']['reason']}")
                    if not comp["trades_30s"]["receipt_id_check_passed"]:
                        reasons.append(f"{name}:trades:{comp['trades_30s']['reason']}")
                rows.extend(
                    SlotEvidence(
                        product,
                        d,
                        cutoff,
                        finished,
                        self.inventory_sha256,
                        payloads[product],
                        tuple(reasons),
                    )
                    for d in DIRECTIONS
                )
            self._cohorts[cutoff] = tuple(rows)
            return self._cohorts[cutoff]
        except Exception:
            self.failed = True
            raise

    def seal(self):
        self._writable()
        if self._now() < self.cutoffs[-1]:
            raise ValueError(
                "cannot seal before all declared cutoffs have been reached"
            )
        for cutoff in self.cutoffs:
            self.checkpoint(cutoff)
        self.sealed = True
        return self.report()

    def report(self):
        if self.failed or not self.sealed:
            raise ValueError(
                "only a sealed complete inventory accounting may be reported"
            )
        rows = [r.to_dict() for cutoff in self.cutoffs for r in self._cohorts[cutoff]]
        return dict(
            version=VERSION,
            status="complete_inventory_accounting_only",
            inventory=json.loads(self.inventory),
            inventory_sha256=self.inventory_sha256,
            inventory_recorded_ts_ms=self.inventory_recorded_ts_ms,
            inventory_precedes_first_cutoff=self.inventory_recorded_ts_ms
            < self.cutoffs[0],
            expected_rows=len(self.products) * len(self.cutoffs) * 2,
            recorded_rows=len(rows),
            packet_count=len(self.packets),
            unique_live_matches=len(self.trades),
            rows=rows,
            implementation_sha256=self.source_sha256,
            contract_sha256=self.contract_sha256,
            book_implementation_sha256=self.book.source_sha256,
            monitor_implementation_sha256=self.book.monitor.source_sha256,
            scope="recorded_input_components_not_authenticated_full_feed_or_study_eligibility",
            processing_clock="measured_in_this_run_never_historical_receipt_backdating",
            full_feed_verified=False,
            positive_eligibility_supported=False,
            directional_report_adapter_supported=False,
            durable_publication_verified=False,
            study_frozen=False,
            feed_gate_pass=False,
            fitting_allowed=False,
            live_integration=False,
        )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("packets", type=Path)
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    source, plan_path, output = (
        args.packets.resolve(),
        args.inventory.resolve(),
        args.out_dir.resolve(),
    )
    if any(
        output == p.parent or p.parent in output.parents for p in (source, plan_path)
    ):
        raise ValueError("output must be outside both input directories")
    source_hash, plan_hash = (_file_sha(p) for p in (source, plan_path))
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    recorder = InputEvidenceRecorder(
        plan["products"], plan["first_cutoff"], plan["stop_cutoff"]
    )
    output.mkdir(parents=True, exist_ok=False)
    try:
        opener = gzip.open if source.suffix == ".gz" else open
        with opener(source, "rt", encoding="utf-8") as stream:
            for line in stream:
                recorder.ingest(json.loads(line))
        report = recorder.seal()
        if (_file_sha(source), _file_sha(plan_path)) != (source_hash, plan_hash):
            raise ValueError("input changed during processing")
        report["input_sha256"] = source_hash
        report["inventory_file_sha256"] = plan_hash
        for name, rows in (
            ("packet_processing.jsonl", recorder.packets),
            ("trade_processing.jsonl", recorder.trades),
        ):
            with (output / name).open("x", encoding="utf-8", newline="\n") as target:
                for row in rows:
                    target.write(_json(asdict(row)) + "\n")
            report[name + "_sha256"] = _file_sha(output / name)
        (output / "REPORT.json").write_text(
            json.dumps(report, indent=2) + "\n", encoding="utf-8"
        )
    except Exception as exc:
        (output / "FAILURE.json").write_text(
            _json(dict(status="failed", reason=str(exc))), encoding="utf-8"
        )
        raise


if __name__ == "__main__":
    main()
