"""Compare indexed inputs and decisions against the batch evidence path."""

import pytest

from test_instant_input_evidence_review import BTC, COIN, Tape, healthy
from test_instant_timed_features import CUTOFF, feature_tape
from instant_delayed_decision import prepare_decision
from instant_evidence_index import CHECKPOINT_PACKETS
from instant_input_evidence import InputEvidenceRecorder
from instant_timed_features import _book_pressure


class IndexedTape(Tape):
    def __init__(self, products=(COIN, BTC), first=30000, stop=40000, start_clock=0):
        super().__init__(products, first, stop, start_clock)
        self.rec = InputEvidenceRecorder(
            products, first, stop, clock_ms=self._clock, indexed=True
        )


@pytest.mark.parametrize("unknown_side", [False, True])
def test_feature_rows_and_exact_prefixes_match_at_both_knowledge_times(unknown_side):
    batch = feature_tape(unknown_side=unknown_side)
    fast = feature_tape(unknown_side=unknown_side, tape_type=IndexedTape)
    for asof in (CUTOFF + 1, CUTOFF + 180, CUTOFF):
        for direction in ("up", "down"):
            assert prepare_decision(
                fast.rec, COIN, CUTOFF, direction, asof=asof
            ) == prepare_decision(batch.rec, COIN, CUTOFF, direction, asof=asof)

    # Probe prefix edges and the same-time first-pending packet, including
    # a non-current prefix after the incremental hash advanced past it.
    for seq in (
        1,
        CHECKPOINT_PACKETS,
        2 * CHECKPOINT_PACKETS + 1,
        len(batch.rec.packets),
    ):
        at = batch.rec.packets[seq - 1].available_ts_ms
        for timestamp in (at - 1, at):
            assert fast.rec._prefix_at(timestamp) == batch.rec._prefix_at(timestamp)


def test_delayed_book_payload_and_same_ms_barrier_have_batch_parity():
    batch, fast = (
        healthy(cls(first=30000, stop=50000), through=30000)
        for cls in (Tape, IndexedTape)
    )
    for tape in (batch, fast):
        tape.send(30001, "audit_transport_error")
        tape.ack(30001)
        tape.hb(30001, 10)
        tape.snap(30001)
        tape.hb(35000, 10, steps=[35000, 35000, 35000, 35000, 35150])
    for asof in (35001, 35150):
        assert fast.rec._quote_at(COIN, 35000, asof) == batch.rec._quote_at(
            COIN, 35000, asof
        )
        assert fast.rec._trade_window(
            COIN, 25000, 35000, asof
        ) == batch.rec._trade_window(COIN, 25000, 35000, asof)
        assert _book_pressure(fast.rec, COIN, 30000, 35000, asof, 1) == _book_pressure(
            batch.rec, COIN, 30000, 35000, asof, 1
        )


def test_late_merge_and_conflict_are_queried_by_end_and_knowledge_time():
    batch, fast = Tape(), IndexedTape()
    for tape in (batch, fast):
        tape.ack()
        tape.hb(0, 10)
        tape.hb(1000, 11)
        tape.trade(1100, 11)
        tape.hb(2000, 11)
        tape.trade(2400, 11, size="99")
    for asof in (1001, 2001, 2401):
        left = fast.rec._trade_window(COIN, 0, 1000, asof)
        right = batch.rec._trade_window(COIN, 0, 1000, asof)
        assert left == right
    assert fast.rec._trade_window(COIN, 0, 2000, 2001)[2] is None
    assert fast.rec._trade_window(COIN, 1100, 2000, 2401)[2] == "conflicting_trade_id"
