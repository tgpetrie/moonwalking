"""Independent cross-boundary probes: receipt -> decision -> publication -> outcome.

Claude Fable review at pin 257be69. Everything here is synthetic and offline.
The probes join stages that earlier accepted reviews examined one at a time.
Tests named ``limitation`` assert behavior that is still open; they document a
boundary and are not approval of it. Nothing here authenticates a feed,
measures public delivery, grades a real outcome or supports fitting.
"""

import json
import ssl

import pytest

from test_instant_delayed_decision import start
from test_instant_input_evidence_review import BTC, COIN, Tape, healthy
from test_instant_stream_journal import Clock, send
from test_instant_timed_features import CUTOFF, feature_tape, features
import instant_association as association
import instant_directional_exposure as directional
from instant_delayed_decision import (
    grade_publication,
    observe_publication,
    prepare_decision,
)
from instant_delayed_eligibility import LocalDelivery, assess_cohort
from instant_input_evidence import GRID_MS, _file_sha
from instant_real_indexed_pilot import (
    MAX_OBSERVER_S,
    TIMING_PRODUCTS,
    TIMING_STEP_MS,
    DiagnosticCohorts,
    QueuedSocket as QueuedSocketForTest,
    _observation_report,
    _observe,
    _timing_readiness,
)
from instant_source_pilot import DURATION_S, WARMUP_MS
from instant_stream_journal import StreamJournal, read_segment
from instant_timed_baseline import MINUTE_MS, PACE_COUNT, PACE_MS, RETURN_COUNT
from verify_instant_timing_attempt import verify


CHANNELS = ["matches", "heartbeat", "level2_batch", "ticker"]
TICKER = json.dumps(dict(type="ticker", product_id=BTC))


class Attempt:
    """A two-cohort synthetic attempt directory in the verifier's format."""

    def __init__(self, folder, *, batch_frames=1):
        self.folder, self.path = folder, folder / "capture.sqlite"
        self.clock = Clock()
        self.plan = dict(
            products=[BTC, COIN],
            channels=CHANNELS,
            warmup_ms=0,
            cohort_count=2,
            cohort_step_ms=5000,
            cohort_evidence_offsets_ms=[1500, 5000],
            diagnostic_deadlines_ms={"1500": 2500, "5000": 6000},
        )
        self.rows, self.observations = [], []
        self.journal = StreamJournal(
            self.path,
            [BTC, COIN],
            30000,
            45000,
            clock_ms=self.clock,
            monotonic_ns=self.clock.mono,
            indexed=True,
            batch_frames=batch_frames,
        )
        self.connection = self.journal.open_connection()
        self.clock.now = 30000
        ack = dict(
            type="subscriptions",
            channels=[dict(name=c, product_ids=[BTC, COIN]) for c in CHANNELS],
        )
        if batch_frames == 1:
            send(self.journal, self.connection, **ack)
        else:
            self.batch((json.dumps(ack), 30000))

    def batch(self, *frames):
        return self.journal.receive_batch(
            self.connection, [(raw, (stamp, stamp * 1000000)) for raw, stamp in frames]
        )

    def publish(self, name, product, cutoff, direction, offset, *, seen=None):
        asof = cutoff + offset
        self.clock.now = max(self.clock.now, asof)
        decision = prepare_decision(
            self.journal.evidence, product, cutoff, direction, asof=asof
        )
        receipt = self.journal.append_publication(name, decision)
        row = dict(
            publication_id=name,
            decision_sha256=receipt.decision_sha256,
            commit_observed_ts_ms=receipt.local_commit_observed_ts_ms,
            cutoff_ts_ms=cutoff,
            knowledge_asof_ts_ms=asof,
            decision_completed_ts_ms=decision.decision_completed_ts_ms,
            product_id=product,
            direction=direction,
        )
        if seen is not None:
            self.observe(row, seen)
        self.rows.append(row)
        return decision, receipt

    def observe(self, row, seen):
        self.observations.append(
            dict(
                publication_id=row["publication_id"],
                decision_sha256=row["decision_sha256"],
                commit_observed_ts_ms=row["commit_observed_ts_ms"],
                consumer_seen_ts_ms=seen,
            )
        )
        row["consumer_seen_ts_ms"] = seen

    def finish(self, *, write_observations=True):
        self.clock.now = max(self.clock.now, 46000)
        self.journal.end_connection(self.connection)
        self.journal.finish()
        self.journal.close()
        (self.folder / "PLAN.json").write_text(json.dumps(self.plan), encoding="utf-8")
        if write_observations:
            (self.folder / "observed.jsonl").write_text(
                "".join(json.dumps(row) + "\n" for row in self.observations),
                encoding="utf-8",
            )
        self.report()

    def report(self):
        report = dict(
            self.plan,
            stop="duration",
            segment=read_segment(self.path),
            journal_sha256=_file_sha(self.path),
            first_ack_ts_ms=30000,
            recovered_pending_ingress_frames=0,
            diagnostic_rows=self.rows,
        )
        (self.folder / "REPORT.json").write_text(json.dumps(report), encoding="utf-8")


def forward_tape(tape, mid_at, *, horizon=300, break_ts=None, matches=3):
    """Extend the feature tape through one horizon with a chosen coin path."""
    end = CUTOFF + horizon * 1000
    watermark, connection, made = tape.rec.trades[-1].trade_id, 1, 0
    for ts in range(CUTOFF, end, 5000):
        if ts == break_ts:
            tape.send(ts + 500, "audit_transport_error", pid=None, conn=connection)
            connection = 2
            tape.ack(ts + 600, conn=connection)
        if made < matches:
            watermark, made = watermark + 1, made + 1
            tape.trade(ts + 1000, watermark, conn=connection)
        for pid, mid in ((COIN, mid_at(ts + 5000)), (BTC, 51000)):
            tape.send(
                ts + 2000,
                "snapshot",
                pid,
                conn=connection,
                bids=[[str(mid - 1), "3"]],
                asks=[[str(mid + 1), "1"]],
            )
        tape.hb(ts + 5000, watermark, conn=connection)
        tape.hb(ts + 5000, 10, BTC, conn=connection)
    tape.hb(end + 5000, watermark, conn=connection)
    tape.hb(end + 5000, 10, BTC, conn=connection)
    tape.now = end + 6000
    return end


def ramp(ts):
    return 110 + 40 * (ts - CUTOFF) / 300000


# --- Receipt and processing to a causal decision -------------------------------


def test_limitation_asof_view_stays_open_while_the_clock_reads_that_millisecond():
    tape = healthy(Tape(), through=29000)
    asof = tape.now = 31500
    count, digest, _ = tape.rec._prefix_at(asof)
    first_quote, _ = tape.rec._quote_at(COIN, 30000, asof)
    decision = prepare_decision(tape.rec, COIN, 30000, "up", asof=asof)
    # Stamped by the reader before the cutoff, still queued, and completed by
    # the owner while the wall clock continues to read the as-of millisecond.
    tape.send(29900, "snapshot", COIN, bids=[["109", "2"]], asks=[["111", "1"]])
    assert tape.rec.packets[-1].available_ts_ms == asof
    assert tape.rec._prefix_at(asof)[:2] != (count, digest)
    assert tape.rec._prefix_at(asof)[0] == count + 1
    second_quote, _ = tape.rec._quote_at(COIN, 30000, asof)
    assert (first_quote["bid"], second_quote["bid"]) == ("99", "109")
    with pytest.raises(ValueError, match="evidence prefix differ"):
        observe_publication(tape.rec, decision, publication_id="x", published=asof)
    # Once the clock has passed the as-of, later packets cannot enter it.
    tape.now = asof + 1
    closed = tape.rec._prefix_at(asof)
    tape.send(29950, "snapshot", COIN, bids=[["119", "2"]], asks=[["121", "1"]])
    assert tape.rec._prefix_at(asof)[:2] == closed[:2]


def test_cohort_waits_until_its_asof_has_closed_before_freezing(tmp_path, monkeypatch):
    clock = Clock()
    first = 5000 + WARMUP_MS
    asof = first + 1500
    monkeypatch.setattr("instant_real_indexed_pilot.utc_ms", clock)
    monkeypatch.setattr(
        "instant_real_indexed_pilot.subprocess.Popen", lambda *a, **k: object()
    )
    with StreamJournal(
        tmp_path / "capture.sqlite",
        TIMING_PRODUCTS,
        first,
        first + 200000,
        clock_ms=clock,
        monotonic_ns=clock.mono,
        indexed=True,
    ) as journal:
        connection = journal.open_connection()
        cohorts = DiagnosticCohorts(
            journal,
            tmp_path,
            products=TIMING_PRODUCTS,
            offsets=(1500, 5000),
            step_ms=10000,
        )
        clock.now = asof
        cohorts.after_commit(4999)
        assert cohorts.rows == []  # the as-of millisecond is still open
        journal.receive(connection, TICKER, received=(asof - 100, 0))
        assert journal.evidence.packets[-1].available_ts_ms == asof
        clock.now = asof + 1
        cohorts.after_commit(4999)
        assert len(cohorts.rows) == 2 * len(TIMING_PRODUCTS)
        counts = {
            json.loads(snapshot.feature_json)["baseline"]["known_packet_count"]
            for snapshot in cohorts.snapshots.values()
        }
        assert counts == {2}  # connection marker and the same-millisecond frame
        # The final report can still rebuild every frozen prefix.
        report = _timing_readiness(cohorts)
    assert report["1500"]["products"][BTC]["committed_rows"] == 2


class QueuedTape(Tape):
    """Frames stamped from CUTOFF-4000 wait in the reader queue until CUTOFF+90."""

    def send(self, ts, kind, pid=COIN, conn=1, source=None, steps=None, **fields):
        if ts >= CUTOFF - 4000:
            floor = max(self.now, CUTOFF + 90)
            steps = [max(step, floor) for step in (steps or [ts] * 5)]
        return super().send(ts, kind, pid, conn, source, steps, **fields)


def test_limitation_queued_pre_cutoff_quote_is_ready_but_never_a_complete_vector():
    tape = feature_tape(tape_type=QueuedTape)
    early, final = CUTOFF + 50, CUTOFF + 180
    tape.now = final
    before, after = features(tape, asof=early), features(tape, asof=final)
    stale, _ = tape.rec._quote_at(COIN, CUTOFF, early)
    fresh, _ = tape.rec._quote_at(COIN, CUTOFF, final)
    # The reader had already stamped a newer pre-cutoff book (CUTOFF-4000).
    # At the early as-of the quote-only inputs are marked ready on the older
    # book, with no field saying that received input was still unprocessed.
    assert (stale["available"], stale["bid"], stale["observation_age_ms"]) == (
        True,
        "100",
        9000,
    )
    assert (fresh["available"], fresh["bid"], fresh["observation_age_ms"]) == (
        True,
        "109",
        4000,
    )
    for name in ("F1", "F4", "F5"):
        assert before["features"][name]["status"] == "ready"
        assert before["features"][name]["value"] != after["features"][name]["value"]
    assert before["features"]["F1"]["value"] < 0 < after["features"]["F1"]["value"]
    assert before["features"]["F3"]["status"] == "ready"
    # Control: the cutoff-closing trade proof cannot be known before every
    # earlier frame has been processed, so the row is not a complete vector.
    assert before["features"]["F2"]["reason"] == "trade_coverage_not_yet_proven"
    decisions = {
        asof: prepare_decision(tape.rec, COIN, CUTOFF, "up", asof=asof)
        for asof in (early, final)
    }
    for asof, complete in ((early, False), (final, True)):
        cohort = assess_cohort(tape.rec, CUTOFF, asof=asof, decisions=[decisions[asof]])
        row = next(
            r
            for r in cohort["rows"]
            if (r["product_id"], r["direction"]) == (COIN, "up")
        )
        assert row["complete_vector_candidate"] is complete
        assert row["anchor_reasons"] == {}
    assert set(row["feature_reasons"]) == set()


def test_in_flight_batch_stays_outside_the_frozen_prefix_and_verifier_agrees(tmp_path):
    attempt = Attempt(tmp_path, batch_frames=16)
    known = attempt.journal.evidence._prefix_at(31500)[0]
    # Two frames were stamped before the as-of; the owner reaches them after it.
    attempt.clock.now = 31600
    attempt.batch((TICKER, 31400), (TICKER, 31450))
    decision, _ = attempt.publish("fast", COIN, 30000, "up", 1500, seen=32000)
    baseline = json.loads(decision.feature_json)["baseline"]
    assert baseline["known_packet_count"] == known == 2
    assert decision.decision_completed_ts_ms == 31600
    attempt.finish()
    result = verify(tmp_path)
    assert result["publication_prefixes_verified"] == 1
    assert result["batch_ingress_clocks_verified"] == 3
    assert result["schedule_results"]["1500"]["products"][COIN]["within_bound"] == 1


def test_schedule_fits_warmup_duration_and_observer_but_no_horizon_can_mature():
    worst_history = worst_tail = None
    for phase in range(0, 60000, 7):
        ack = 1794356673393 + phase
        first = ((ack + WARMUP_MS + GRID_MS - 1) // GRID_MS) * GRID_MS
        assert WARMUP_MS <= first - ack < WARMUP_MS + GRID_MS
        sigma_end = (first - 35000) // MINUTE_MS * MINUTE_MS
        earliest = min(
            sigma_end - RETURN_COUNT * MINUTE_MS - GRID_MS,
            first - PACE_MS - PACE_COUNT * PACE_MS,
        )
        history = earliest - ack
        last_asof = first + 19 * TIMING_STEP_MS + 5000
        tail = ack + DURATION_S * 1000 - last_asof
        worst_history = (
            history if worst_history is None else min(worst_history, history)
        )
        worst_tail = tail if worst_tail is None else min(worst_tail, tail)
        # The observer is started no earlier than one grid step before the
        # first cutoff and lives for a fixed 240 seconds.
        assert first - GRID_MS + MAX_OBSERVER_S * 1000 - last_asof == 40000
        # Even the first cutoff's 300s horizon ends at or after the capture
        # deadline anchor, and the journal inventory stops 69 minutes after a
        # first grid point that precedes the acknowledgment.
        assert first + 300000 >= ack + DURATION_S * 1000
        assert first + 900000 > ack + 69 * MINUTE_MS
    assert worst_history >= 20000
    assert worst_tail >= 95000


@pytest.mark.parametrize(
    ("case", "error"),
    [
        ("planned_only", None),
        ("journal_only", None),
        ("report_only", "unknown publication"),
        ("unscheduled_cutoff", "publication slot or decision clock differs"),
        ("wrong_arm", "publication slot or decision clock differs"),
    ],
)
def test_verifier_accounts_for_missing_slots_in_both_directions(tmp_path, case, error):
    attempt = Attempt(tmp_path)
    attempt.publish("fast", COIN, 30000, "up", 1500, seen=32000)
    if case == "journal_only":
        attempt.publish("unreported", COIN, 35000, "down", 5000)
        attempt.rows.pop()
    elif case == "report_only":
        attempt.rows.append(dict(attempt.rows[0], publication_id="phantom"))
    elif case == "unscheduled_cutoff":
        attempt.publish("stray", COIN, 40000, "up", 1500)
    elif case == "wrong_arm":
        attempt.publish("stray", COIN, 35000, "up", 1500)
    attempt.finish()
    if error:
        with pytest.raises(ValueError, match=error):
            verify(tmp_path)
        return
    result = verify(tmp_path)
    fast, slow = (
        result["schedule_results"][arm]["products"] for arm in ("1500", "5000")
    )
    # Every planned product and direction stays in each arm's denominator.
    assert {p: row["planned"] for p, row in fast.items()} == {BTC: 2, COIN: 2}
    assert (fast[COIN]["journaled"], fast[BTC]["journaled"]) == (1, 0)
    assert slow[COIN]["journaled"] == (1 if case == "journal_only" else 0)
    assert result["journal_only_publications"] == (1 if case == "journal_only" else 0)


# --- Decision to publication ---------------------------------------------------


def test_torn_final_observer_line_is_counted_and_only_that_row_is_unobserved(tmp_path):
    attempt = Attempt(tmp_path)
    attempt.publish("fast", COIN, 30000, "up", 1500, seen=32000)
    attempt.publish("slow", COIN, 35000, "up", 5000)
    attempt.finish()
    # The observer was killed while writing its second receipt.
    with (tmp_path / "observed.jsonl").open("a", encoding="utf-8") as stream:
        stream.write('{"publication_id":"slow","decision_sha')
    result = verify(tmp_path)
    assert result["torn_final_observation_lines"] == 1
    assert result["local_observations_verified"] == 1
    assert result["schedule_results"]["5000"]["products"][COIN]["observed"] == 0
    # A damaged complete line cannot be explained by an interrupted append.
    (tmp_path / "observed.jsonl").write_text(
        '{"unfinished":\n' + json.dumps(attempt.observations[0]) + "\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="unreadable local observation"):
        verify(tmp_path)


@pytest.mark.parametrize(
    ("case", "error"),
    [
        ("orphan", "unknown publication"),
        ("duplicate", "duplicate publication_id"),
        ("other_decision", "consumer observation differs"),
        ("other_commit", "consumer observation differs"),
        ("unreported_clock", "consumer observation differs"),
    ],
)
def test_verifier_rejects_orphan_duplicate_and_mismatched_receipts(
    tmp_path, case, error
):
    attempt = Attempt(tmp_path)
    attempt.publish("fast", COIN, 30000, "up", 1500, seen=32000)
    _, other = attempt.publish("slow", COIN, 35000, "up", 5000)
    first = attempt.observations[0]
    if case == "orphan":
        attempt.observations.append(dict(first, publication_id="phantom"))
    elif case == "duplicate":
        attempt.observations.append(dict(first))
    elif case == "other_decision":
        first["decision_sha256"] = other.decision_sha256
    elif case == "other_commit":
        first["commit_observed_ts_ms"] += 1
    elif case == "unreported_clock":
        first["consumer_seen_ts_ms"] += 1
    attempt.finish()
    with pytest.raises(ValueError, match=error):
        verify(tmp_path)


@pytest.mark.parametrize(
    ("age", "status"), [(2500, "within_bound"), (2501, "after_bound")]
)
def test_deadline_is_inclusive_and_late_rows_stay_in_the_denominator(
    tmp_path, age, status
):
    attempt = Attempt(tmp_path)
    decision, receipt = attempt.publish(
        "fast", COIN, 30000, "up", 1500, seen=30000 + age
    )
    delivery = LocalDelivery(
        receipt.decision_sha256, receipt.local_commit_observed_ts_ms, 30000 + age
    )
    cohort = assess_cohort(
        attempt.journal.evidence,
        30000,
        asof=31500,
        decisions=[decision],
        local_deliveries={(COIN, "up"): delivery},
        deadline_age_ms=2500,
    )
    row = next(r for r in cohort["rows"] if r["delivery"]["consumer_age_ms"] == age)
    assert row["delivery"]["status"] == status
    assert cohort["planned_rows"] == 4
    attempt.finish()
    stats = verify(tmp_path)["schedule_results"]["1500"]["products"][COIN]
    assert (stats["planned"], stats["observed"]) == (2, 1)
    assert stats["within_bound"] == (status == "within_bound")


def test_rows_committed_after_the_observer_exits_are_unobserved_not_dropped(tmp_path):
    attempt = Attempt(tmp_path)
    attempt.publish("fast", COIN, 30000, "up", 1500)
    stop = tmp_path / "observer.stop"
    stop.touch()
    _observe(attempt.path, tmp_path / "observed.jsonl", stop)
    attempt.publish("slow", COIN, 35000, "up", 5000)
    local = _observation_report(tmp_path, attempt.rows)
    assert local["missing_or_invalid"] == 1 and local["discrepancies"] == {}
    attempt.finish(write_observations=False)
    result = verify(tmp_path)
    assert result["local_observations_verified"] == 1
    assert result["unacknowledged_publications"] == 0
    slow = result["schedule_results"]["5000"]["products"][COIN]
    assert (slow["planned"], slow["journaled"], slow["observed"]) == (2, 1, 0)
    # Limitation: nothing in the artifacts says when the observer stopped, so
    # an expired observer and a slow consumer leave the same missing row.
    assert set(
        json.loads((tmp_path / "observed.jsonl").read_text().splitlines()[0])
    ) == {
        "publication_id",
        "decision_sha256",
        "commit_observed_ts_ms",
        "consumer_seen_ts_ms",
    }


# --- Publication to later outcome ----------------------------------------------


@pytest.mark.parametrize(("direction", "success"), [("up", True), ("down", False)])
def test_grade_moves_from_pending_through_waiting_to_an_own_direction_outcome(
    direction, success
):
    tape = feature_tape()
    decision, publication = start(tape, direction=direction)
    frozen = decision.sha256
    end = forward_tape(tape, ramp)
    grades = [
        grade_publication(tape.rec, publication, 300, asof=asof)
        for asof in (end - 1, end, end + 1)
    ]
    assert [(g["status"], g["reason"]) for g in grades] == [
        ("pending", "horizon_not_mature"),
        ("unavailable", "trade_coverage_not_yet_proven"),
        ("ready", None),
    ]
    assert [g["cutoff_verified_forward"] for g in grades] == [None, None, success]
    # A valid negative is a ready False, never a missing label.
    assert grades[2]["forward_match_count"] == 3
    assert {g["decision_sha256"] for g in grades} == {frozen}
    assert {g["publication_id"] for g in grades} == {"synthetic-1"}
    assert {g["feature_cutoff_ts_ms"] for g in grades} == {CUTOFF}
    assert decision.sha256 == frozen


def test_flat_path_is_a_valid_negative_on_both_boards():
    for direction in ("up", "down"):
        tape = feature_tape()
        _, publication = start(tape, direction=direction)
        end = forward_tape(tape, lambda ts: 110)
        grade = grade_publication(tape.rec, publication, 300, asof=end + 1)
        assert (grade["status"], grade["cutoff_verified_forward"]) == ("ready", False)
        assert grade["direction"] == direction


def test_limitation_a_permanent_break_and_a_short_wait_share_status_and_reason():
    waiting_tape = feature_tape()
    _, waiting = start(waiting_tape)
    end = forward_tape(waiting_tape, ramp)
    transient = grade_publication(waiting_tape.rec, waiting, 300, asof=end)

    broken_tape = feature_tape()
    decision, broken = start(broken_tape)
    forward_tape(broken_tape, ramp, break_ts=CUTOFF + 150000)
    broken_tape.now = end + 600000
    permanent = grade_publication(broken_tape.rec, broken, 300, asof=end + 600000)

    for grade in (transient, permanent):
        assert (grade["status"], grade["reason"], grade["cutoff_verified_forward"]) == (
            "unavailable",
            "trade_coverage_not_yet_proven",
            None,
        )
    assert permanent["evidence_scope"] == "outcome_trade_window"
    # The continuity break never becomes a negative and never edits the row.
    assert permanent["decision_sha256"] == decision.sha256
    # Control: the unbroken tape becomes gradable one millisecond later.
    assert grade_publication(waiting_tape.rec, waiting, 300, asof=end + 1)[
        "status"
    ] == ("ready")


def test_break_after_the_horizon_does_not_invalidate_a_matured_outcome():
    tape = feature_tape()
    _, publication = start(tape)
    end = forward_tape(tape, ramp)
    before = grade_publication(tape.rec, publication, 300, asof=end + 6000)
    tape.send(end + 7000, "audit_transport_error", pid=None)
    tape.now = end + 8000
    after = grade_publication(tape.rec, publication, 300, asof=end + 8000)
    assert (before["status"], after["status"]) == ("ready", "ready")
    assert after["cutoff_verified_forward"] is before["cutoff_verified_forward"] is True
    assert (
        after["grading_packet_prefix_sha256"] != before["grading_packet_prefix_sha256"]
    )


def test_limitation_publication_after_the_horizon_is_flagged_but_still_ready():
    tape = feature_tape()
    decision = prepare_decision(tape.rec, COIN, CUTOFF, "up", asof=CUTOFF + 180)
    end = forward_tape(tape, ramp)
    late = observe_publication(
        tape.rec, decision, publication_id="late", published=end + 5
    )
    grade = grade_publication(tape.rec, late, 300, asof=end + 6000)
    assert (grade["status"], grade["cutoff_verified_forward"]) == ("ready", True)
    assert grade["publication_before_horizon_end"] is False
    assert late.durable_publication_verified is False


def test_limitation_cutoff_grade_is_not_an_entry_at_the_publication_price():
    tape = feature_tape()
    decision = prepare_decision(tape.rec, COIN, CUTOFF, "up", asof=CUTOFF + 180)
    # The whole favorable move happens before the row is observed as published.
    end = forward_tape(tape, lambda ts: 150)
    publication = observe_publication(
        tape.rec, decision, publication_id="after-move", published=CUTOFF + 6000
    )
    grade = grade_publication(tape.rec, publication, 300, asof=end + 6000)
    assert grade["cutoff_verified_forward"] is True
    assert grade["scope"] == "offline_cutoff_outcome_diagnostic"
    at_publication, _ = tape.rec._quote_at(COIN, CUTOFF + 5000, end + 6000)
    at_end, _ = tape.rec._quote_at(COIN, end, end + 6000)
    # Nothing moved between the first quote after publication and the horizon.
    assert (at_publication["bid"], at_publication["ask"]) == (
        at_end["bid"],
        at_end["ask"],
    )
    assert not any("publication_price" in key or "entry" in key for key in grade)


def test_limitation_no_executable_bridge_from_grade_or_delayed_row_to_exposure():
    tape = feature_tape()
    _, publication = start(tape)
    end = forward_tape(tape, ramp)
    grade = grade_publication(tape.rec, publication, 300, asof=end + 1)
    assert sorted(set(association.LABEL_KEYS) - set(grade)) == [
        "anchor_ts_ms",
        "contract_sha256",
        "contract_version",
        "evaluator_sha256",
        "label_maturity_ts_ms",
        "verified_forward",
    ]
    with pytest.raises(ValueError, match="malformed label row"):
        association.association_report([grade], [], asof_ts_ms=end + 1)
    delayed = dict(
        product_id=COIN,
        ts_ms=CUTOFF,
        available_ts_ms=CUTOFF + 1500,
        universe_member=True,
        warmup_complete=True,
        health_verified=True,
        candidate_eligible=True,
    )
    with pytest.raises(ValueError, match="known by its cutoff"):
        directional.exposure_report(
            [],
            [dict(delayed, direction=side) for side in ("up", "down")],
            asof_ts_ms=end + 1,
        )


# --- Transport failure classification (pinned websocket-client 1.9.0) ---------


class Wire:
    """Raw socket bytes: one server text frame, optional timeouts, then an end."""

    FRAME = b"\x81" + bytes([len(TICKER)]) + TICKER.encode()

    def __init__(self, ending, *, timeouts=0):
        self.script = [self.FRAME] + [TimeoutError("idle")] * timeouts + [ending]

    def recv(self, size):
        item = self.script[0]
        if isinstance(item, Exception):
            self.script.pop(0)
            raise item
        result, rest = item[:size], item[size:]
        if rest:
            self.script[0] = rest
        else:
            self.script.pop(0)
            if not self.script:
                self.script.append(b"")
        return result

    def send(self, data):
        return len(data)

    def gettimeout(self):
        return 1

    def close(self):
        pass


def reader_end(ending, *, timeouts=0):
    import websocket

    ws = websocket.WebSocket()
    ws.sock, ws.connected = Wire(ending, timeouts=timeouts), True
    reader = QueuedSocketForTest(ws, (websocket.WebSocketTimeoutException,))
    try:
        reader.send('{"type":"subscribe"}')
        assert reader.done.wait(5)
        assert json.loads(reader.recv().raw) == json.loads(TICKER)
        return reader.reader_report()["transport"], reader.failure
    finally:
        reader.stopping.set()


@pytest.mark.parametrize(
    ("ending", "kind", "error_type", "message"),
    [
        (
            b"",
            "exception",
            "WebSocketConnectionClosedException",
            "remote host was lost",
        ),
        (
            ConnectionResetError(10054, "reset"),
            "exception",
            "ConnectionResetError",
            "reset",
        ),
        (
            ConnectionAbortedError(10053, "aborted"),
            "exception",
            "ConnectionAbortedError",
            "aborted",
        ),
        (
            # Only reachable if a diagnostic run sets suppress_ragged_eofs=False.
            ssl.SSLEOFError(8, "EOF occurred in violation of protocol"),
            "exception",
            "SSLEOFError",
            "violation of protocol",
        ),
        (b"\x88\x02\x03\xe8", "empty_return", None, None),
    ],
    ids=[
        "tcp-or-tls-eof",
        "tcp-reset",
        "local-abort",
        "ragged-tls-eof-unsuppressed",
        "websocket-close-1000",
    ],
)
def test_reader_snapshot_separates_eof_reset_abort_and_protocol_close(
    capsys, ending, kind, error_type, message
):
    transport, failure = reader_end(ending)
    assert transport["kind"] == kind
    assert transport["received"] == transport["delivered"] + 1 == 1
    assert transport["close_status"] is None  # never exposed by recv()
    if error_type is None:
        assert failure is None and transport["exception_chain"] == []
    else:
        first = transport["exception_chain"][0]
        assert first["type"].endswith(error_type) and message in first["message"]
        assert first["errno"] == (None if ending == b"" else ending.errno)
    assert capsys.readouterr().err.count("READER_TRANSPORT ") == 1


def test_reader_snapshot_counts_silent_timeouts_before_the_loss():
    flowing, _ = reader_end(b"")
    stalled, _ = reader_end(b"", timeouts=3)
    assert (
        flowing["timeouts_since_last_return"],
        stalled["timeouts_since_last_return"],
    ) == (
        0,
        3,
    )


def test_observed_asia_text_means_an_orderly_or_ragged_eof_not_reset_or_close():
    import inspect

    import websocket._http as http
    import instant_real_indexed_pilot as pilot

    # The pilot passes no sslopt, so a TCP FIN without TLS close_notify is
    # suppressed to b"" and reported with the same text as an orderly EOF.
    assert 'suppress_ragged_eofs=sslopt.get("suppress_ragged_eofs", True)' in (
        inspect.getsource(http)
    )
    assert "sslopt" not in inspect.getsource(pilot.main)
    eof, _ = reader_end(b"")
    reset, _ = reader_end(ConnectionResetError(10054, "reset"))
    assert eof["exception_chain"][0]["message"] == "Connection to remote host was lost."
    assert (
        reset["exception_chain"][0]["message"] != eof["exception_chain"][0]["message"]
    )
