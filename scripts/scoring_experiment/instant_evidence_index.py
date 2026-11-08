"""Append-only indexes for the timed recorder's existing evidence rules."""

from bisect import bisect_left, bisect_right
from decimal import Decimal, getcontext
from functools import lru_cache
import hashlib
from operator import attrgetter, itemgetter
from pathlib import Path

from instant_input_evidence import _packet_line, _sha


CHECKPOINT_PACKETS = 128
receipt_ts = attrgetter("receipt_ts_ms")
available_ts = attrgetter("available_ts_ms")
receipt_key = itemgetter("receipt_ts_ms")
available_key = itemgetter("available_ts_ms")
end_key = itemgetter("end_ts_ms")


def _last(rows, count):
    return rows[count - 1] if count else None


def _before(rows, cutoff, asof, receipt, known):
    return min(
        bisect_left(rows, cutoff, key=receipt), bisect_right(rows, asof, key=known)
    )


def _span(rows, start, end, asof):
    # Closing receipt and proof availability are ordered. Starts may move
    # backwards for a merged proof or a late conflict on an old trade ID.
    left = bisect_right(rows, start, key=end_key)
    right = bisect_right(rows, asof, key=available_key)
    return [row for row in rows[left:right] if row["start_ts_ms"] < end]


def _carry(rows, start, count, key):
    first = bisect_right(rows, start, hi=count, key=key)
    return rows[max(first - 1, 0) : count]


class EvidenceIndex:
    """Append from the recorder after each successfully processed packet."""

    def __init__(self, recorder):
        self.recorder = recorder
        self.monitor = recorder.book.monitor
        self.transport = {pid: [] for pid in recorder.products}
        self.proofs = {pid: [] for pid in recorder.products}
        self.conflicts = {pid: [] for pid in recorder.products}
        self.trades = {pid: [] for pid in recorder.products}
        self._streams = (
            (self.monitor.transport, self.transport),
            (self.monitor.proofs, self.proofs),
            (self.monitor.conflicts, self.conflicts),
        )
        self._positions = [0] * len(self._streams)
        self._hash = hashlib.sha256()
        self._hash_checkpoints = [self._hash.copy()]
        self._last_prefix = None
        self._bin_sum = lru_cache(maxsize=8192)(self._sum_bin)
        self._decimal_signature = None
        self.source_sha256 = _sha(
            Path(__file__).read_text(encoding="utf-8").encode("utf-8")
        )

    def ingested(self, packet, trade):
        for i, (rows, index) in enumerate(self._streams):
            for position in range(self._positions[i], len(rows)):
                row = rows[position]
                index[row["product_id"]].append(row)
            self._positions[i] = len(rows)
        if trade is not None:
            self.trades[trade.product_id].append(trade)
        self._hash.update(_packet_line(packet))
        if len(self.recorder.packets) % CHECKPOINT_PACKETS == 0:
            self._hash_checkpoints.append(self._hash.copy())

    def prefix_at(self, asof):
        packets = self.recorder.packets
        count = bisect_right(packets, asof, key=available_ts)
        if self._last_prefix is not None and self._last_prefix[0] == count:
            digest = self._last_prefix[1]
        elif count == len(packets):
            digest = self._hash.hexdigest()
        else:
            block = count // CHECKPOINT_PACKETS
            prefix = self._hash_checkpoints[block].copy()
            for packet in packets[block * CHECKPOINT_PACKETS : count]:
                prefix.update(_packet_line(packet))
            digest = prefix.hexdigest()
        self._last_prefix = count, digest
        return count, digest, packets[count] if count < len(packets) else None

    def quote_records(self, product, cutoff, asof):
        book = self.recorder.book
        states = book.history[product]
        transport = self.transport[product]
        return (
            _last(states, _before(states, cutoff, asof, receipt_ts, available_ts)),
            _last(
                transport,
                _before(
                    transport,
                    cutoff,
                    asof,
                    receipt_key,
                    lambda row: book.completed[row["receipt_seq"]],
                ),
            ),
        )

    def book_window(self, product, start, end, asof):
        states = self.recorder.book.history[product]
        transport = self.transport[product]
        packets = self.recorder._packet_by_seq
        state_count = _before(
            states,
            end,
            asof,
            receipt_ts,
            lambda row: packets[row.receipt_seq].available_ts_ms,
        )
        transport_count = _before(
            transport,
            end,
            asof,
            receipt_key,
            lambda row: packets[row["receipt_seq"]].available_ts_ms,
        )
        return (
            _carry(states, start, state_count, receipt_ts),
            _carry(transport, start, transport_count, receipt_key),
        )

    def trade_window(self, product, start, end, asof):
        self.monitor._validate_assessment(product, start, end, asof)
        intervals = _span(self.proofs[product], start, end, asof)
        conflict = bool(_span(self.conflicts[product], start, end, asof))
        states = self.transport[product]
        latest = _last(states, bisect_right(states, asof, key=available_key))
        proof = self.monitor._assess_filtered(
            product, start, end, asof, latest, intervals, conflict
        )
        rows = self.trades[product]
        left, right = (
            bisect_left(rows, boundary, key=receipt_ts) for boundary in (start, end)
        )
        return proof, intervals, rows[left:right]

    def _sum_bin(self, product, left, right):
        return sum(
            (
                Decimal(t.price) * Decimal(t.size)
                for t in self.trades[product][left:right]
            ),
            Decimal(0),
        )

    def pace_bins(self, product, start, end, step):
        """Called only after the current as-of's entire window is certified."""
        context = getcontext()
        signature = (
            context.prec,
            context.rounding,
            context.Emin,
            context.Emax,
            context.clamp,
            tuple(context.traps.items()),
        )
        if signature != self._decimal_signature:
            self._bin_sum.cache_clear()
            self._decimal_signature = signature
        rows = self.trades[product]
        boundaries = [
            bisect_left(rows, timestamp, key=receipt_ts)
            for timestamp in range(start, end + 1, step)
        ]
        counts, amounts = [], []
        for left, right in zip(boundaries, boundaries[1:]):
            counts.append(right - left)
            amounts.append(self._bin_sum(product, left, right))
        return counts, amounts
