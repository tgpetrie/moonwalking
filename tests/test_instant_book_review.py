"""Independent adversarial review probes for instant_book / instant_publication.

Claude review of Codex 8c51878 (inspected at tip 3ad47b3). Every expected value
below is hand-calculated from the contract, not read back from the module.
Probes marked DEFECT failed on the unmodified code; controls passed on it.
Synthetic inputs establish engineering behaviour only, not predictive value.
"""

from dataclasses import FrozenInstanceError
import hashlib
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts/scoring_experiment"))
import instant_book  # noqa: E402
from instant_book import BookReplay  # noqa: E402
from instant_publication import publication_timing  # noqa: E402

A, B = "AAA-USD", "BBB-USD"
CHANNELS = ("level2_batch", "matches", "heartbeat")


class Tape:
    """Independent envelope writer; the clock is a trusted synthetic input."""

    def __init__(self, products=(A,)):
        self.products, self.seq, self.now = products, 0, 0
        self.clocks = None
        self.book = BookReplay(list(products), clock_ms=self._clock)

    def _clock(self):
        return next(self.clocks) if self.clocks else self.now

    def send(self, ts, kind, *, pid=A, conn=1, source="ws", clocks=None, **fields):
        self.seq += 1
        self.now = ts
        self.clocks = iter(clocks) if clocks else None
        self.book.ingest(
            dict(
                receipt_seq=self.seq,
                receipt_ts_ms=ts,
                receipt_monotonic_ns=ts * 1000000,
                connection_id=conn,
                source=source,
                message=dict(type=kind, product_id=pid, **fields),
            )
        )
        self.clocks = None

    def ack(self, ts, products=None, conn=1, channels=CHANNELS):
        ids = list(self.products if products is None else products)
        self.send(
            ts,
            "subscriptions",
            conn=conn,
            channels=[dict(name=c, product_ids=ids) for c in channels],
        )

    def hb(self, ts, pid=A, conn=1, **kw):
        self.send(ts, "heartbeat", pid=pid, conn=conn, last_trade_id=5, **kw)

    def snap(self, ts, pid=A, conn=1, bids=None, asks=None):
        self.send(
            ts,
            "snapshot",
            pid=pid,
            conn=conn,
            bids=bids or [["100.5", "3"], ["100", "4"]],
            asks=asks or [["101", "1"], ["101.5", "2"]],
        )

    def upd(self, ts, changes, pid=A, conn=1, **kw):
        self.send(ts, "l2update", pid=pid, conn=conn, changes=changes, **kw)

    def view(self, cutoff, pid=A, asof=None):
        return self.book.view(pid, cutoff, asof=asof)


def live():
    t = Tape()
    t.ack(10)
    t.hb(500)
    t.snap(600)
    t.hb(1500)
    return t


def quote(v):
    return (v.bid, v.ask, v.bid_size, v.ask_size)


# 1. Hand-calculated book and pressure oracles ------------------------------


def test_oracle_sequence_absolute_replace_zero_delete_repeat_and_deep_levels():
    t = live()
    v = t.view(5000)
    # bid 100.5x3 / ask 101x1: mid 100.75, pressure (3-1)/(3+1).
    assert quote(v) == ("100.5", "101", "3", "1")
    assert v.mid == 100.75 and v.sampled_pressure == 0.5

    t.upd(1600, [["buy", "100.5", "0"], ["buy", "100.75", "6"], ["sell", "101", "5"]])
    t.hb(2500)
    v = t.view(5000)
    assert quote(v) == ("100.75", "101", "6", "5")
    assert v.mid == 100.875 and v.sampled_pressure == pytest.approx(1 / 11)

    t.upd(2600, [["sell", "101", "2"]])  # Absolute replacement, not 5 + 2.
    assert t.view(5000).ask_size == "2"
    assert t.view(5000).sampled_pressure == pytest.approx(0.5)  # (6-2)/8

    t.upd(
        2700, [["buy", "100.75", "1"], ["buy", "100.75", "0"], ["buy", "100.75", "9"]]
    )
    v = t.view(5000)
    assert v.bid_size == "9" and v.sampled_pressure == pytest.approx(7 / 11)
    assert (v.book_change_ts_ms, v.bbo_change_ts_ms) == (2700, 2700)

    t.upd(2800, [["sell", "150", "3"]])  # Deep ask: book changes, BBO does not.
    v = t.view(5000)
    assert (v.observation_ts_ms, v.book_change_ts_ms, v.bbo_change_ts_ms) == (
        2800,
        2800,
        2700,
    )

    t.upd(2900, [["sell", "101", "0"]])  # Delete best ask: next level surfaces.
    v = t.view(5000)
    assert (v.ask, v.ask_size, v.mid) == ("101.5", "2", 101.125)
    assert v.sampled_pressure == pytest.approx(7 / 11)  # (9-2)/(9+2)


def test_transient_cross_removed_in_same_batch_is_observation_only():
    t = live()
    t.upd(
        1600,
        [
            ["buy", "102", "1"],
            ["sell", "100", "1"],
            ["buy", "102", "0"],
            ["sell", "100", "0"],
        ],
    )
    v = t.view(5000)
    assert v.book_state_available and quote(v) == ("100.5", "101", "3", "1")
    assert (v.observation_ts_ms, v.book_change_ts_ms, v.bbo_change_ts_ms) == (
        1600,
        600,
        600,
    )
    assert [r.receipt_ts_ms for r in t.book.history[A]].count(1600) == 1


def test_deleting_an_absent_level_is_an_observation_not_a_change():
    t = live()
    t.upd(1600, [["buy", "50", "0"]])
    v = t.view(5000)
    assert (v.observation_ts_ms, v.book_change_ts_ms) == (1600, 600)


@pytest.mark.parametrize(
    "changes",
    [
        [["buy", "101", "1"]],  # final locked
        [["sell", "100.5", "1"]],  # final locked from the ask side
        [["buy", "101.5", "1"], ["sell", "101", "0"]],  # final crossed at depth
        [["buy", "100.5", "0"], ["buy", "100", "0"]],  # bid side exhausted
    ],
)
def test_final_locked_crossed_or_missing_side_is_unavailable(changes):
    t = live()
    t.upd(1600, changes)
    assert t.view(5000).reason == "invalid_book_update"


# B2 DEFECT: a representation-only size change moved the BBO clock.


@pytest.mark.parametrize(
    "changes",
    [
        [["buy", "100.5", "3.00"]],
        [["buy", "100.5", "0"], ["buy", "100.50", "3"]],
    ],
)
def test_numerically_identical_bbo_does_not_move_change_clocks(changes):
    t = live()
    t.upd(1600, changes)
    v = t.view(5000)
    assert v.book_state_available and v.observation_ts_ms == 1600
    # No price or quantity changed, so neither change clock may move, and a
    # BBO change can never be newer than the whole-book change.
    assert (v.book_change_ts_ms, v.bbo_change_ts_ms) == (600, 600)


def test_control_real_bbo_size_change_moves_both_clocks():
    t = live()
    t.upd(1600, [["buy", "100.5", "3.5"]])
    v = t.view(5000)
    assert (v.book_change_ts_ms, v.bbo_change_ts_ms, v.bid_size) == (1600, 1600, "3.5")


# 2. Sessions, acknowledgements, ignored inputs, failures ------------------


def test_multi_product_ack_and_failure_isolation():
    t = Tape((A, B))
    t.ack(10, products=(A,))
    t.hb(500)
    t.hb(500, pid=B)
    t.snap(600)
    t.snap(600, pid=B)
    t.hb(1500)
    t.hb(1500, pid=B)
    assert t.view(5000).book_state_available
    assert t.view(5000, pid=B).reason == "subscription_unconfirmed"
    # An invalid batch on A does not touch B, and vice versa.
    t.ack(1600)
    t.snap(1700, pid=B)
    t.hb(2000, pid=B)
    t.upd(2100, [["buy", "200", "1"]])
    assert t.view(5000).reason == "invalid_book_update"
    assert t.view(5000, pid=B).book_state_available


def test_ack_missing_level2_batch_channel_does_not_confirm_book():
    t = Tape()
    t.ack(10, channels=("level2", "matches", "heartbeat"))
    t.hb(500)
    t.snap(600)
    t.hb(1500)
    assert t.view(5000).reason == "subscription_unconfirmed"


def test_rest_input_with_other_connection_neither_resets_nor_replaces_book():
    t = live()
    before = t.view(5000)
    t.send(
        1600, "snapshot", source="rest", conn=99, bids=[["1", "1"]], asks=[["2", "1"]]
    )
    t.send(
        1700,
        "snapshot",
        source="rest_recovery",
        conn=98,
        bids=[["1", "1"]],
        asks=[["2", "1"]],
    )
    t.send(1800, "ticker", best_bid="1", best_ask="2")
    assert t.view(5000) == before


@pytest.mark.parametrize(
    "kind", ["queue_overflow", "audit_parse_error", "audit_transport_error", "error"]
)
def test_failure_marker_invalidates_every_product_and_needs_ack_then_snapshot(kind):
    t = Tape((A, B))
    t.ack(10)
    for ts, step in ((500, t.hb), (600, t.snap), (1500, t.hb)):
        step(ts, pid=A)
        step(ts, pid=B)
    t.send(1600, kind, pid=None)
    for ts, step in ((2000, t.hb), (2100, t.snap)):  # Snapshot without ack.
        step(ts, pid=A)
        step(ts, pid=B)
    for pid in (A, B):
        assert t.view(5000, pid=pid).reason == "subscription_unconfirmed"
    t.ack(2200)
    t.hb(2300)
    assert t.view(5000).reason == "awaiting_snapshot"
    t.snap(2400)
    assert t.view(5000).book_state_available
    assert t.view(5000, pid=B).reason == "awaiting_snapshot"


def test_same_millisecond_heartbeat_collision_fails_closed_until_next_beat():
    t = live()
    t.hb(1500)
    assert t.view(5000).reason == "heartbeat_unavailable"
    t.hb(2500)
    assert t.view(5000).book_state_available


@pytest.mark.parametrize(
    "second,reason", [(6500, None), (6501, "heartbeat_gap_requires_snapshot")]
)
def test_heartbeat_gap_boundary_is_strictly_greater_than_five_seconds(second, reason):
    t = live()
    t.upd(6000, [["buy", "100.5", "4"]])
    t.hb(second)
    assert t.view(10000).reason == reason


# 3. Receipt vs processing completion, TTL and as-of ------------------------


def test_receipt_one_ms_before_cutoff_is_included_receipt_at_cutoff_excluded():
    t = live()
    t.upd(4999, [["buy", "100.5", "7"]])
    t.upd(5000, [["buy", "100.5", "8"]])
    assert t.view(5000).bid_size == "7"
    assert t.view(5000, asof=999999).bid_size == "7"


@pytest.mark.parametrize("beat,ok", [(5000, True), (4999, False)])
def test_heartbeat_freshness_boundary_is_exactly_five_seconds(beat, ok):
    t = Tape()
    t.ack(10)
    t.hb(beat - 1000)
    t.snap(beat - 900)
    t.hb(beat)
    v = t.view(10000)
    assert v.book_state_available is ok
    assert v.reason == (None if ok else "stale_heartbeat")


@pytest.mark.parametrize("obs,reason", [(5000, None), (4999, "stale_book_observation")])
def test_observation_ttl_is_exactly_ten_seconds_and_heartbeats_do_not_renew(
    obs, reason
):
    t = Tape()
    t.ack(10)
    t.hb(obs - 100)
    t.snap(obs)
    for ts in range(obs + 900, 15000, 1000):
        t.hb(ts)
    v = t.view(15000)
    assert v.reason == reason and v.observation_ts_ms == obs


# B1 DEFECT: a heartbeat was usable before the book finished processing it.
# The monitor stamps its transport record at monitor completion; the book's
# heartbeat-gap invalidation from the SAME packet is stamped later, at book
# completion. In between, the gap heartbeat freshened a book it invalidates.


def test_gap_heartbeat_cannot_freshen_a_book_before_its_invalidation_is_known():
    t = live()  # Last heartbeat 1500; book observed at 600 (age 9400 at 10000).
    # Gap 8100ms > 5000. Clocks: monitor start, monitor done, book done.
    t.hb(9600, clocks=(9600, 10000, 10500))
    v = t.view(10000)  # asof 10000: monitor done, book not done.
    assert not v.book_state_available and v.bid is None
    assert v.reason == "stale_heartbeat"  # Latest fully processed beat: 1500.
    assert t.view(10000, asof=10500).reason == "heartbeat_gap_requires_snapshot"


def test_control_without_the_gap_heartbeat_the_view_is_stale():
    assert live().view(10000).reason == "stale_heartbeat"


def test_control_ordinary_heartbeat_is_still_usable_while_the_next_one_is_in_flight():
    t = live()
    t.upd(6000, [["buy", "100.5", "4"]])
    t.hb(6400)
    t.hb(9600, clocks=(9600, 10000, 10500))
    assert t.view(10000).book_state_available  # Beat 6400 is 3600ms old.
    assert t.view(10000, asof=10500).book_state_available


def test_late_failure_is_visible_only_after_processing_and_never_rewrites_earlier():
    t = live()
    t.upd(3000, [["buy", "100.5", "4"]])
    t.hb(3500)
    before = t.view(5000)
    t.send(4000, "connection_closed", pid=None, clocks=(4000, 4001, 7000))
    later = t.view(5000, asof=7000)
    assert later.reason == "connection_closed" and later.bid is None
    assert before.book_state_available and before.bid_size == "4"


def test_one_packet_has_one_knowledge_time_for_transport_and_book():
    # Same root cause as B1, in the fail-closed direction: on the pinned code
    # the marker's transport record vetoed the view at 4001 although the book
    # had not yet processed the marker (available 7000). Both now share 7000.
    t = live()
    t.upd(3000, [["buy", "100.5", "4"]])
    t.hb(3500)
    before = t.view(5000)
    t.send(4000, "connection_closed", pid=None, clocks=(4000, 4001, 7000))
    assert t.view(5000) == before
    assert t.view(5000, asof=6999).book_state_available
    assert not t.view(5000, asof=7000).book_state_available


def test_queued_packet_is_not_certified_absent_by_an_older_quote():
    # Documented scope: the view is the last fully processed state, not a
    # queue/completeness certificate. This control pins that behaviour.
    t = live()
    t.upd(4000, [["buy", "100.5", "9"]], clocks=(4000, 4001, 6000))
    v = t.view(5000)
    assert v.bid_size == "3" and v.available_ts_ms == 601
    assert not v.full_feed_verified


@pytest.mark.parametrize(
    "clocks,match",
    [((2000, 2001, 1999), "regressed"), ((2000, 2001, 2000.5), "integer")],
)
def test_bad_book_processing_clock_fails_the_artifact(clocks, match):
    t = live()
    with pytest.raises(ValueError, match=match):
        t.hb(2000, clocks=clocks)
    with pytest.raises(ValueError, match="failed book"):
        t.view(5000)
    with pytest.raises(ValueError, match="failed"):
        t.hb(2500)


@pytest.mark.parametrize(
    "cutoff,asof",
    [(4999, None), (5000, 4999), (True, None), (5000, True), (-5000, None)],
)
def test_query_requires_grid_cutoff_and_causal_integer_asof(cutoff, asof):
    t = live()
    with pytest.raises(ValueError):
        t.view(cutoff, asof=asof)


def test_results_are_frozen_and_carry_provenance():
    t = live()
    v = t.view(5000)
    for attr in ("bid", "reason", "knowledge_asof_ts_ms"):
        with pytest.raises(FrozenInstanceError):
            setattr(v, attr, None)
    src = (ROOT / "scripts/scoring_experiment/instant_book.py").read_text("utf-8")
    con = (ROOT / "docs/research/INSTANT_BOOK_CONTRACT_V1_DRAFT.json").read_text(
        "utf-8"
    )
    assert v.implementation_sha256 == hashlib.sha256(src.encode()).hexdigest()
    assert v.contract_sha256 == hashlib.sha256(con.encode()).hexdigest()
    assert not v.full_feed_verified and not v.target_sample_adapter_supported


# 4. Publication chronology -------------------------------------------------


def clocks(**kw):
    args = dict(
        publication_id="p",
        product_id=A,
        feature_cutoff=20000,
        inputs_available=20040,
        decision_completed=20070,
        published=20150,
    )
    args.update(kw)
    return publication_timing(**args)


def test_publication_hand_calculated_ages_and_anchor_flags():
    row = clocks()
    assert (
        row.feature_age_at_publication_ms,
        row.verification_lag_from_cutoff_ms,
        row.decision_to_publication_ms,
    ) == (150, 40, 80)
    assert not row.legacy_cutoff_inputs_compatible
    assert row.publication_target_amendment_required
    assert row.readiness_reason == "publication_age_policy_unfrozen"
    assert not row.eligible_for_fitting


def test_inputs_at_cutoff_but_late_publication_still_needs_amendment():
    row = clocks(inputs_available=20000)
    assert row.legacy_cutoff_inputs_compatible
    assert row.publication_target_amendment_required


@pytest.mark.parametrize(
    "kw",
    [
        dict(inputs_available=20000, decision_completed=20000, published=20000),
        dict(decision_completed=20040),
        dict(published=20070),
    ],
)
def test_publication_equal_neighbouring_clocks_are_allowed(kw):
    assert clocks(**kw).published_ts_ms >= clocks(**kw).feature_cutoff_ts_ms


@pytest.mark.parametrize(
    "bound,within,reason",
    [
        (149, False, "feature_window_too_old"),
        (150, True, "study_and_source_gates_unfrozen"),
        (0, False, "feature_window_too_old"),
    ],
)
def test_publication_age_bound_is_exact_and_never_approves_fitting(
    bound, within, reason
):
    row = clocks(max_feature_age_ms=bound)
    assert row.within_declared_feature_age is within and row.readiness_reason == reason
    assert not row.eligible_for_fitting


@pytest.mark.parametrize(
    "kw",
    [
        dict(publication_id=7),
        dict(product_id=None),
        dict(inputs_available=19999),
        dict(decision_completed=20039),
        dict(published=20069),
        dict(feature_cutoff=20000.0),
        dict(max_feature_age_ms=1.5),
        dict(
            feature_cutoff=-5000, inputs_available=0, decision_completed=0, published=0
        ),
    ],
)
def test_publication_rejects_malformed_or_noncausal_metadata(kw):
    with pytest.raises(ValueError):
        clocks(**kw)


def test_publication_is_keyword_only_frozen_and_hashes_its_sources():
    with pytest.raises(TypeError):
        publication_timing("p", A, 20000, 20000, 20000, 20000)
    row = clocks()
    with pytest.raises(FrozenInstanceError):
        row.published_ts_ms = 1
    src = (ROOT / "scripts/scoring_experiment/instant_publication.py").read_text(
        "utf-8"
    )
    assert row.implementation_sha256 == hashlib.sha256(src.encode()).hexdigest()


# 5. Offline imports ------------------------------------------------------


def test_modules_import_without_network_or_backend_dependencies():
    code = (
        "import sys; sys.path.insert(0, sys.argv[1]);"
        "import instant_book, instant_publication;"
        "bad = {'socket', 'ssl', 'http', 'urllib.request', 'requests', 'websocket',"
        " 'websockets', 'aiohttp', 'backend', 'app'} & set(sys.modules);"
        "print(sorted(bad)); sys.exit(1 if bad else 0)"
    )
    run = subprocess.run(
        [sys.executable, "-I", "-c", code, str(ROOT / "scripts/scoring_experiment")],
        capture_output=True,
        text=True,
    )
    assert run.returncode == 0, run.stdout + run.stderr


def test_book_level_cap_is_inherited_not_raised():
    assert instant_book.MAX_LEVELS == 100000 and instant_book.MAX_QUOTE_AGE_MS == 10000
