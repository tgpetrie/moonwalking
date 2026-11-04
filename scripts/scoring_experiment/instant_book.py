"""Bounded offline Exchange level2_batch replay; no socket or live imports."""

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import hashlib
import json
import math
from pathlib import Path

from instant_coverage import CoverageMonitor, _integer


VERSION = "instant-book-replay-v1-draft"
CONTRACT = (
    Path(__file__).resolve().parents[2]
    / "docs/research/INSTANT_BOOK_CONTRACT_V1_DRAFT.json"
)
MAX_LEVELS = 100000
MAX_QUOTE_AGE_MS = 10000


def _decimal(value, *, positive):
    if isinstance(value, bool):
        raise ValueError("boolean is not a book amount")
    try:
        result = Decimal(str(value))
        number = float(result)
    except (InvalidOperation, ValueError, OverflowError) as exc:
        raise ValueError("invalid book amount") from exc
    if (
        not result.is_finite()
        or not math.isfinite(number)
        or result < 0
        or (positive and (result <= 0 or number <= 0))
    ):
        raise ValueError("invalid book amount")
    if result > 0 and number <= 0:
        raise ValueError("book amount underflows reader representation")
    return result


@dataclass(frozen=True)
class BookState:
    product_id: str
    receipt_ts_ms: int
    available_ts_ms: int
    receipt_seq: int
    connection_id: int | str
    reason: str | None
    observation_ts_ms: int | None
    book_change_ts_ms: int | None
    bbo_change_ts_ms: int | None
    best: tuple[str, str, str, str] | None
    exchange_time: str | None


@dataclass(frozen=True)
class BookView:
    version: str
    product_id: str
    cutoff_ts_ms: int
    knowledge_asof_ts_ms: int
    book_state_available: bool
    reason: str | None
    bid: str | None
    ask: str | None
    bid_size: str | None
    ask_size: str | None
    mid: float | None
    sampled_pressure: float | None
    observation_ts_ms: int | None
    book_change_ts_ms: int | None
    bbo_change_ts_ms: int | None
    observation_age_ms: int | None
    book_change_age_ms: int | None
    bbo_change_age_ms: int | None
    available_ts_ms: int | None
    connection_id: int | str | None
    exchange_time: str | None
    full_feed_verified: bool
    target_sample_adapter_supported: bool
    contract_sha256: str
    implementation_sha256: str
    monitor_sha256: str


class BookReplay:
    """Last fully processed book state, with original receipt age and known-at time.

    Quote state is not complete feed certification. The existing receipt/ID
    monitor retains its own narrower scope. No state here enters Sample/V1/V2.
    An injectable processing clock is a trusted test input, not historical proof.
    """

    def __init__(self, products, *, clock_ms=None):
        raw = CONTRACT.read_text(encoding="utf-8").encode("utf-8")
        cfg = json.loads(raw)
        if (cfg["version"], cfg["max_levels_per_product"], cfg["max_quote_age_ms"]) != (
            VERSION,
            MAX_LEVELS,
            MAX_QUOTE_AGE_MS,
        ):
            raise ValueError("book contract and implementation differ")
        self.monitor = CoverageMonitor(
            products, quote_channel="level2_batch", clock_ms=clock_ms
        )
        self.contract_sha256 = hashlib.sha256(raw).hexdigest()
        self.source_sha256 = hashlib.sha256(
            Path(__file__).read_text(encoding="utf-8").encode("utf-8")
        ).hexdigest()
        self.connection = None
        self.books = {}
        self.last_heartbeat = {}
        self.history = {p: [] for p in self.monitor.products}
        self.awaiting_ack = set(self.monitor.products)
        self.completed = {}  # receipt_seq -> this packet's book completion.
        self.failed = False

    def _invalidate(self, product, reason):
        self.books.pop(product, None)
        self.pending.append((product, reason))

    @staticmethod
    def _best(book):
        bid, ask = max(book["buy"]), min(book["sell"])
        if bid >= ask:
            raise ValueError("locked or crossed book")
        return tuple(map(str, (bid, ask, book["buy"][bid], book["sell"][ask])))

    def _snapshot(self, message):
        book = {"buy": {}, "sell": {}}
        for side, key in (("buy", "bids"), ("sell", "asks")):
            levels = message.get(key)
            if not isinstance(levels, list) or not levels or len(levels) > MAX_LEVELS:
                raise ValueError("bounded nonempty book side required")
            for row in levels:
                if not isinstance(row, list) or len(row) != 2:
                    raise ValueError("snapshot level must be [price,size]")
                price, size = (_decimal(v, positive=True) for v in row)
                if price in book[side]:
                    raise ValueError("duplicate snapshot price")
                book[side][price] = size
        return book

    def _update(self, previous, message):
        changes = message.get("changes")
        if not isinstance(changes, list) or not changes or len(changes) > MAX_LEVELS:
            raise ValueError("bounded nonempty change batch required")
        book = {side: previous[side].copy() for side in ("buy", "sell")}
        for row in changes:
            if not isinstance(row, list) or len(row) != 3 or row[0] not in book:
                raise ValueError("update must be [buy_or_sell,price,absolute_size]")
            side, price, size = (
                row[0],
                _decimal(row[1], positive=True),
                _decimal(row[2], positive=False),
            )
            if size == 0:
                book[side].pop(price, None)
            else:
                book[side][price] = size
        if not book["buy"] or not book["sell"]:
            raise ValueError("book side exhausted")
        return book

    def ingest(self, envelope):
        if self.failed:
            raise ValueError("book replay failed; no more input accepted")
        try:
            self.monitor.ingest(envelope)
            self.pending = []
            self._consume(envelope)
            finished = _integer(self.monitor.clock_ms())
            if finished < self.monitor.last[3]:
                raise ValueError("book processing clock regressed")
            self.monitor.last = (*self.monitor.last[:3], finished)
            receipt, seq = envelope["receipt_ts_ms"], envelope["receipt_seq"]
            # Monitor records from this packet are not book knowledge until the
            # book has processed the same packet (e.g. a heartbeat gap).
            self.completed[seq] = max(finished, receipt + 1)
            for product, reason in self.pending:
                book = self.books.get(product)
                self.history[product].append(
                    BookState(
                        product,
                        receipt,
                        max(finished, receipt + 1),
                        seq,
                        self.connection,
                        reason,
                        book["observation"] if book else None,
                        book["book_change"] if book else None,
                        book["bbo_change"] if book else None,
                        self._best(book) if book else None,
                        book["exchange_time"] if book else None,
                    )
                )
        except Exception:
            self.failed = True
            raise

    def _consume(self, env):
        if env.get("source", "ws") != "ws":
            return
        receipt = env["receipt_ts_ms"]
        if self.connection != env["connection_id"]:
            self.connection = env["connection_id"]
            self.last_heartbeat.clear()
            self.awaiting_ack.update(self.history)
            for product in self.history:
                self._invalidate(product, "subscription_unconfirmed")
        message = env["message"]
        kind, product = message.get("type"), message.get("product_id")
        if kind in ("connection_closed", "error", "queue_overflow") or (
            isinstance(kind, str) and kind.startswith("audit_")
        ):
            self.last_heartbeat.clear()
            self.awaiting_ack.update(self.history)
            for pid in self.history:
                self._invalidate(pid, kind)
            return
        if kind == "subscriptions":
            for pid in self.history:
                if pid not in self.monitor.active:
                    self.last_heartbeat.pop(pid, None)
                    self.awaiting_ack.add(pid)
                    self._invalidate(pid, "subscription_unconfirmed")
                else:
                    self.awaiting_ack.discard(pid)
                    if pid not in self.books:
                        self._invalidate(pid, "awaiting_snapshot")
            return
        if product not in self.history:
            return
        if kind == "heartbeat" and product in self.monitor.active:
            previous = self.last_heartbeat.get(product)
            if previous is not None and receipt - previous > 5000:
                self._invalidate(product, "heartbeat_gap_requires_snapshot")
            self.last_heartbeat[product] = receipt
        if kind not in ("snapshot", "l2update"):
            return
        if product not in self.monitor.active or product in self.awaiting_ack:
            self._invalidate(product, "subscription_unconfirmed")
            return
        previous = self.books.get(product)
        if kind == "l2update" and previous is None:
            self._invalidate(product, "awaiting_snapshot")
            return
        try:
            candidate = (
                self._snapshot(message)
                if kind == "snapshot"
                else self._update(previous, message)
            )
            if sum(len(candidate[s]) for s in ("buy", "sell")) > MAX_LEVELS:
                raise ValueError("total book level bound exceeded")
            best = self._best(
                candidate
            )  # Validate the final whole batch, never intermediate states.
        except (ValueError, TypeError, InvalidOperation):
            self._invalidate(
                product,
                (
                    "invalid_book_snapshot"
                    if kind == "snapshot"
                    else "invalid_book_update"
                ),
            )
            return
        changed = previous is None or any(
            candidate[s] != previous[s] for s in ("buy", "sell")
        )
        # Compare amounts, not spellings: "3" -> "3.00" is not a BBO change.
        bbo_changed = previous is None or tuple(map(Decimal, best)) != tuple(
            map(Decimal, self._best(previous))
        )
        candidate.update(
            observation=receipt,
            book_change=receipt if changed else previous["book_change"],
            bbo_change=receipt if bbo_changed else previous["bbo_change"],
            exchange_time=(
                message.get("time") if isinstance(message.get("time"), str) else None
            ),
        )
        self.books[product] = candidate
        self.pending.append((product, None))

    def view(self, product, cutoff, *, asof=None):
        if self.failed:
            raise ValueError("failed book replay cannot be queried")
        _integer(cutoff)
        asof = cutoff if asof is None else _integer(asof)
        if product not in self.history or cutoff % 5000 or asof < cutoff:
            raise ValueError("known product, grid cutoff and causal asof required")
        records = [
            r
            for r in self.history[product]
            if r.receipt_ts_ms < cutoff and r.available_ts_ms <= asof
        ]
        state = records[-1] if records else None
        reason = state.reason if state else "no_known_book"
        transport = [
            r
            for r in self.monitor.transport
            if r["product_id"] == product
            and r["receipt_ts_ms"] < cutoff
            and r["available_ts_ms"] <= asof
            and self.completed[r["receipt_seq"]] <= asof
        ]
        latest = transport[-1] if transport else None
        age = (
            cutoff - state.observation_ts_ms
            if state and state.observation_ts_ms is not None
            else None
        )
        if state and reason is None:
            if latest is None or latest["reason"] != "heartbeat_observed":
                reason = "heartbeat_unavailable"
            elif cutoff - latest["receipt_ts_ms"] > 5000:
                reason = "stale_heartbeat"
            elif age > MAX_QUOTE_AGE_MS:
                reason = "stale_book_observation"
        best = state.best if state and reason is None else (None,) * 4
        if best is None:
            best = (None,) * 4
        bid, ask, bid_size, ask_size = best
        return BookView(
            VERSION,
            product,
            cutoff,
            asof,
            reason is None,
            reason,
            bid,
            ask,
            bid_size,
            ask_size,
            float(bid) / 2 + float(ask) / 2 if bid is not None else None,
            (
                float(
                    (Decimal(bid_size) - Decimal(ask_size))
                    / (Decimal(bid_size) + Decimal(ask_size))
                )
                if bid_size is not None
                else None
            ),
            state.observation_ts_ms if state else None,
            state.book_change_ts_ms if state else None,
            state.bbo_change_ts_ms if state else None,
            age,
            (
                cutoff - state.book_change_ts_ms
                if state and state.book_change_ts_ms is not None
                else None
            ),
            (
                cutoff - state.bbo_change_ts_ms
                if state and state.bbo_change_ts_ms is not None
                else None
            ),
            state.available_ts_ms if state else None,
            state.connection_id if state else None,
            state.exchange_time if state else None,
            False,
            False,
            self.contract_sha256,
            self.source_sha256,
            self.monitor.source_sha256,
        )
