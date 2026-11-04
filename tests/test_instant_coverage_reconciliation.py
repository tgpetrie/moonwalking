"""Coverage contract amendment 1: bounded merged reconciliation. Synthetic only."""

import copy
import gzip
import json
import random
import subprocess
import sys
from pathlib import Path

import pytest

from test_instant_coverage import Feed, PID, check
import instant_coverage
from instant_coverage import MERGED_SCOPE, CoverageMonitor


def started(lag=0, first_id=10):
    feed = Feed(lag=lag)
    feed.ack(900)
    feed.hb(1000, first_id)
    return feed


def merged(feed):
    return [p for p in feed.monitor.proofs if p["scope"] == MERGED_SCOPE]


def intervals(feed):
    return [p for p in feed.monitor.proofs if p["scope"] != MERGED_SCOPE]


def overtaken():
    """A heartbeat names trade 11 before the match arrives; nothing is lost."""
    feed = started()
    feed.hb(2000, 11)
    feed.trade(2500, 11)
    feed.hb(3000, 11)
    return feed


def test_heartbeat_overtaking_its_match_reconciles_with_exact_ids():
    feed = overtaken()
    assert [p["reason"] for p in intervals(feed)] == [
        "missing_live_match_ids",
        "receipt_ids_outside_watermarks",
    ]
    proof = merged(feed)[0]
    assert (proof["start_ts_ms"], proof["end_ts_ms"]) == (1000, 3000)
    assert proof["lower_trade_id_exclusive"] == 10
    assert proof["upper_trade_id_inclusive"] == 11
    assert proof["observed_unique_trade_count"] == proof["expected_trade_count"] == 1
    assert proof["merged_proof_count"] == 2
    result = check(feed, 1000, 3000, 3001)
    assert result["receipt_id_check_passed"] is True
    assert result["receipt_id_check_merged_proofs"] == 1


def test_match_arriving_before_a_lagging_heartbeat_reconciles():
    feed = started()
    feed.trade(1500, 11)
    feed.hb(2000, 10)
    feed.hb(3000, 11)
    assert [p["reason"] for p in intervals(feed)] == [
        "receipt_ids_outside_watermarks",
        "missing_live_match_ids",
    ]
    assert check(feed, 1000, 3000, 3001)["receipt_id_check_passed"] is True


def test_truly_lost_id_still_fails_even_with_a_race_beside_it():
    feed = started()
    feed.hb(2000, 12)  # Names 11 and 12.
    feed.trade(2500, 12)  # 11 never arrives.
    feed.hb(3000, 12)
    assert merged(feed) == []
    result = check(feed, 1000, 3000, 3001)
    assert result["receipt_id_check_passed"] is False
    assert result["receipt_id_check_reason"] == "missing_live_match_ids"


def test_extra_unexpected_id_never_reconciles():
    feed = started()
    feed.hb(2000, 11)
    feed.trade(2400, 11)
    feed.trade(2500, 99)  # Outside every watermark in the run.
    feed.hb(3000, 11)
    assert merged(feed) == []
    assert not check(feed, 1000, 3000, 3001)["receipt_id_check_passed"]


def test_wrong_id_cannot_stand_in_for_a_lost_one_with_a_matching_count():
    feed = started()
    feed.hb(2000, 11)  # Names 11, which is lost.
    feed.trade(2500, 99)  # One ID arrives, so the counts agree but the sets do not.
    feed.hb(3000, 11)
    assert merged(feed) == []
    assert not check(feed, 1000, 3000, 3001)["receipt_id_check_passed"]


def test_merged_proof_is_known_only_after_the_closing_heartbeat_finishes():
    feed = started(lag=100)
    feed.hb(2000, 11)
    feed.trade(2500, 11)
    before_close = check(feed, 1000, 2000, 2100)
    assert before_close["receipt_id_check_reason"] == "missing_live_match_ids"
    feed.hb(3000, 11)
    # Later knowledge cannot change what was known earlier.
    assert check(feed, 1000, 2000, 2100) == before_close
    assert (
        check(feed, 1000, 2000, 3099)["receipt_id_check_reason"]
        == "missing_live_match_ids"
    )
    result = check(feed, 1000, 2000, 3100)
    assert result["receipt_id_check_passed"] is True
    assert result["receipt_id_check_available_ts_ms"] == 3100  # Not 2100.


def test_failed_records_stay_unmodified_and_trade_attribution_does_not_move():
    feed = started()
    feed.hb(2000, 11)
    feed.trade(2500, 11)
    failed = copy.deepcopy(intervals(feed))
    feed.hb(3000, 11)
    assert intervals(feed)[0] == failed[0]
    assert intervals(feed)[0]["verified"] is False
    assert feed.monitor.trades[PID] == [(2500, 11, 1)]
    assert feed.monitor.seen[(PID, 11)][1] == 2500


def _race_of(size):
    """`size` adjacent failed proofs: IDs named one per second, all received last."""
    feed = started()
    last = 10 + size - 1
    for step, trade_id in enumerate(range(11, last + 1)):
        feed.hb(2000 + step * 1000, trade_id)
    close = 1000 + size * 1000
    for trade_id in range(11, last + 1):
        feed.trade(close - 500, trade_id)
    feed.hb(close, last)
    return feed, close


@pytest.mark.parametrize("size", [2, 3, 4])
def test_runs_up_to_the_proof_cap_reconcile(size):
    feed, close = _race_of(size)
    assert [p["merged_proof_count"] for p in merged(feed)] == [size]
    assert check(feed, 1000, close, close + 1)["receipt_id_check_passed"] is True


def test_run_beyond_the_proof_cap_stays_vetoed():
    assert instant_coverage.MAX_MERGED_PROOFS == 4
    feed, close = _race_of(5)
    assert merged(feed) == []
    assert len(intervals(feed)) == 5
    assert not any(p["verified"] for p in intervals(feed))
    assert not check(feed, 1000, close, close + 1)["receipt_id_check_passed"]


@pytest.mark.parametrize(
    "step, reconciled",
    [(3000, True), (5000, False)],
)
def test_span_limit_is_enforced_separately_from_the_proof_cap(step, reconciled):
    """Two 3s intervals span 6s (allowed); three 5s intervals span 15s (refused)."""
    assert instant_coverage.MAX_MERGED_SPAN_MS == 10000
    feed = started()
    count = 2 if reconciled else 3
    for index in range(count - 1):
        feed.hb(1000 + (index + 1) * step, 11 + index)
    close = 1000 + count * step
    for trade_id in range(11, 11 + count - 1):
        feed.trade(close - 100, trade_id)
    feed.hb(close, 11 + count - 2)
    assert bool(merged(feed)) is reconciled
    assert len(intervals(feed)) == count


def test_id_span_limit_applies_to_the_merged_span(monkeypatch):
    feed = started()
    monkeypatch.setattr(instant_coverage, "MAX_ID_SPAN", 3)
    feed.hb(2000, 13)  # Delta 3: within the per-pair bound, missing.
    for trade_id in (11, 12, 13, 14, 15):
        feed.trade(2500, trade_id)
    feed.hb(3000, 15)  # Merged delta 5 exceeds it.
    assert intervals(feed)[0]["reason"] == "missing_live_match_ids"
    assert merged(feed) == []


@pytest.mark.parametrize(
    "cause, reason",
    [
        ("gap", "heartbeat_gap"),
        ("regression", "watermark_regression"),
    ],
)
def test_structural_failures_never_join_a_run(cause, reason):
    feed = started()
    feed.hb(2000, 11)  # Missing.
    feed.trade(2500, 11)
    if cause == "gap":
        feed.hb(7001, 11)
    else:
        feed.hb(3000, 9)
    assert intervals(feed)[-1]["reason"] == reason
    assert merged(feed) == []
    # A later race next to the structural failure cannot reach across it.
    close = 8000 if cause == "gap" else 4000
    feed.hb(close, intervals(feed)[-1]["upper_trade_id_inclusive"])
    assert merged(feed) == []


def test_verified_interval_breaks_a_run():
    feed = started()
    feed.hb(2000, 11)  # Missing: trade 11 is lost.
    feed.hb(3000, 11)  # Verified empty interval.
    feed.hb(4000, 12)  # Missing.
    feed.trade(4500, 12)
    feed.trade(4600, 11)  # Too late: separated by a verified interval.
    feed.hb(5000, 12)
    assert all(
        p["start_ts_ms"] >= 3000 for p in merged(feed)
    ), "must not merge across the verified interval"
    assert not check(feed, 1000, 2000, 5001)["receipt_id_check_passed"]


def test_merging_never_crosses_a_connection():
    feed = started()
    feed.hb(2000, 11)  # Missing on connection 1.
    feed.ack(2100, connection=2)
    feed.hb(2200, 11, connection=2)
    feed.trade(2300, 11, connection=2)
    feed.hb(2400, 11, connection=2)  # Outside on connection 2.
    assert merged(feed) == []
    assert not check(feed, 1000, 2000, 2401)["receipt_id_check_passed"]


def test_merging_never_crosses_a_connection_even_at_a_shared_millisecond():
    feed = started()
    feed.hb(2000, 11)  # Missing on connection 1.
    feed.ack(2000, connection=2)
    feed.hb(2000, 11, connection=2)
    feed.trade(2500, 11, connection=2)
    feed.hb(3000, 11, connection=2)  # Outside on connection 2.
    assert [p["connection_id"] for p in intervals(feed)] == [1, 2]
    assert merged(feed) == []


def _lose_subscription(feed, ts):
    feed.ack(ts, channels=[dict(name="matches", product_ids=[])])
    feed.ack(ts)


def test_merging_never_spans_a_subscription_gap():
    """Same connection and continuous watermarks, but unobserved receipt time."""
    feed = started()
    feed.hb(2000, 11)  # Missing.
    _lose_subscription(feed, 2100)
    feed.hb(2300, 11)  # New baseline after the gap.
    feed.trade(2400, 11)
    feed.hb(2500, 11)  # Outside.
    first, second = intervals(feed)
    assert first["upper_trade_id_inclusive"] == second["lower_trade_id_exclusive"]
    assert first["end_ts_ms"] != second["start_ts_ms"]
    assert merged(feed) == []


def test_merging_requires_continuous_watermarks():
    """A same-ms baseline reset skips IDs, even when every ID was received."""
    feed = started()
    for trade_id in (11, 12, 13, 14, 16, 17, 18, 19, 20):
        feed.trade(1500, trade_id)
    feed.hb(2000, 11)  # Outside.
    _lose_subscription(feed, 2000)
    feed.hb(2000, 20)  # New baseline jumps past 12-20.
    feed.trade(2500, 15)
    feed.hb(3000, 20)  # Outside.
    first, second = intervals(feed)
    assert (first["end_ts_ms"], first["reason"]) == (2000, second["reason"])
    assert first["upper_trade_id_inclusive"] != second["lower_trade_id_exclusive"]
    assert merged(feed) == []


def test_known_conflicting_duplicate_still_vetoes_a_reconciled_span():
    feed = overtaken()
    assert check(feed, 1000, 3000, 3001)["receipt_id_check_passed"]
    feed.send(3100, "match", trade_id=11, price="100", size="3", side="sell")
    result = check(feed, 1000, 3000, 3101)
    assert result["receipt_id_check_reason"] == "conflicting_trade_id"
    assert check(feed, 1000, 3000, 3001)["receipt_id_check_passed"]


def test_two_consecutive_races_stay_separate_and_join_continuously():
    feed = overtaken()
    feed.hb(4000, 12)
    feed.trade(4500, 12)
    feed.hb(5000, 12)
    assert [
        (p["start_ts_ms"], p["end_ts_ms"], p["merged_proof_count"])
        for p in merged(feed)
    ] == [(1000, 3000, 2), (3000, 5000, 2)]
    result = check(feed, 1000, 5000, 5001)
    assert result["receipt_id_check_passed"] is True
    assert result["receipt_id_check_merged_proofs"] == 2


def test_a_failed_proof_cannot_be_claimed_by_two_merged_proofs():
    feed = overtaken()
    seen = [s for p in merged(feed) for s in p["supersedes_end_heartbeat_seqs"]]
    feed.hb(4000, 12)
    feed.hb(5000, 12)  # Fresh failures after the merged pair.
    claimed = [s for p in merged(feed) for s in p["supersedes_end_heartbeat_seqs"]]
    assert claimed == seen
    assert len(claimed) == len(set(claimed))


@pytest.mark.parametrize("seed", range(200))
def test_randomized_tape_never_certifies_a_session_with_a_lost_id(seed):
    """Safety property: a whole-session pass implies every named ID was received."""
    rng = random.Random(seed)
    feed = started()
    now, watermark = 1000, 10
    pending, delivered, lost = [], set(), set()
    for _ in range(rng.randint(6, 40)):
        for _ in range(rng.choice((0, 0, 1, 1, 2))):
            watermark += 1
            if rng.random() < 0.03:
                lost.add(watermark)
            else:
                pending.append(watermark)
        now += 1000
        late = [t for t in pending if rng.random() < 0.2]
        for offset, trade_id in enumerate(t for t in pending if t not in late):
            feed.trade(now - 500 + offset, trade_id)
            delivered.add(trade_id)
        pending = late
        feed.hb(now, watermark)
    for offset, trade_id in enumerate(pending):
        feed.trade(now + 100 + offset, trade_id)
        delivered.add(trade_id)
    now += 1000
    feed.hb(now, watermark)
    result = check(feed, 1000, now, now + 1)
    if result["receipt_id_check_passed"]:
        assert not lost
        assert delivered == set(range(11, watermark + 1))
    elif not lost:
        # Without a loss, only a limit or the disjoint-merge rule may veto, which
        # always leaves a failed interval on record. A clean tape must pass.
        assert any(not p["verified"] for p in intervals(feed))
    claimed = [s for p in merged(feed) for s in p["supersedes_end_heartbeat_seqs"]]
    assert len(claimed) == len(set(claimed))
    for proof in merged(feed):
        assert proof["merged_proof_count"] <= instant_coverage.MAX_MERGED_PROOFS
        span = proof["end_ts_ms"] - proof["start_ts_ms"]
        assert span <= instant_coverage.MAX_MERGED_SPAN_MS
        received = {
            tid
            for ts, tid, _ in feed.monitor.trades[PID]
            if proof["start_ts_ms"] <= ts < proof["end_ts_ms"]
        }
        expected = range(
            proof["lower_trade_id_exclusive"] + 1,
            proof["upper_trade_id_inclusive"] + 1,
        )
        assert received == set(expected)


def test_race_nested_around_a_merged_pair_stays_vetoed_by_design():
    """All IDs arrive, but merges stay disjoint: a deliberate fail-closed veto."""
    feed = started()
    feed.trade(1500, 11)
    feed.hb(2000, 12)  # Names 11, 12; 12 is late until the last interval.
    feed.trade(2500, 13)
    feed.hb(3000, 14)  # Names 13, 14; 14 is late by one interval.
    feed.trade(3500, 14)
    feed.hb(4000, 14)  # Closes the inner pair.
    assert [p["merged_proof_count"] for p in merged(feed)] == [2]
    feed.trade(4500, 12)
    feed.hb(5000, 14)  # Only the whole four-proof span reconciles now.
    assert len(intervals(feed)) == 4
    assert [p["merged_proof_count"] for p in merged(feed)] == [2]
    assert not check(feed, 1000, 5000, 5001)["receipt_id_check_passed"]
    # The inner pair remains proven on its own.
    assert check(feed, 2000, 4000, 5001)["receipt_id_check_passed"]


def test_products_reconcile_independently():
    other = "OTHER-USD"
    feed = Feed(products=(PID, other))
    feed.ack(900)
    feed.hb(1000, 10)
    feed.hb(1000, 50, pid=other)
    feed.hb(2000, 11)
    feed.hb(2000, 51, pid=other)  # 51 is lost.
    feed.trade(2500, 11)
    feed.hb(3000, 11)
    feed.hb(3000, 51, pid=other)
    assert feed.monitor.assess(PID, 1000, 3000, asof=3001)["receipt_id_check_passed"]
    assert not feed.monitor.assess(other, 1000, 3000, asof=3001)[
        "receipt_id_check_passed"
    ]


@pytest.mark.parametrize(
    "constant, value",
    [
        ("MAX_MERGED_PROOFS", 5),
        ("MAX_MERGED_SPAN_MS", 20000),
        ("MERGEABLE_REASONS", ("missing_live_match_ids",)),
    ],
)
def test_implementation_refuses_limits_that_differ_from_the_contract(
    monkeypatch, constant, value
):
    monkeypatch.setattr(instant_coverage, constant, value)
    with pytest.raises(ValueError, match="contract and implementation differ"):
        CoverageMonitor((PID,))


def test_contract_states_the_limits_and_stays_gated():
    cfg = json.loads(instant_coverage.CONTRACT.read_text(encoding="utf-8"))
    merge = cfg["reconciliation"]
    assert merge["max_merged_proofs"] == 4
    assert merge["max_merged_span_ms"] == 10000
    assert "heartbeat_gap" in merge["never_merges"]
    assert cfg["version"].endswith("amendment-1")
    assert cfg["feed_gate_pass"] is False
    assert cfg["fitting_allowed"] is False
    assert cfg["live_integration"] is False


def test_cli_report_separates_interval_merged_and_unreconciled_counts(tmp_path):
    feed = overtaken()
    feed.hb(4000, 12)  # 12 is lost: this failure stays unreconciled.
    source = tmp_path / "in" / "packets.jsonl.gz"
    source.parent.mkdir()
    with gzip.open(source, "wt", encoding="utf-8") as stream:
        for event in feed.events:
            stream.write(json.dumps(event) + "\n")
    output = tmp_path / "out"
    script = Path(instant_coverage.__file__)
    subprocess.run(
        [sys.executable, "-B", str(script), str(source)]
        + ["--products", PID, "--out-dir", str(output)],
        check=True,
        capture_output=True,
    )
    report = json.loads((output / "REPORT.json").read_text(encoding="utf-8"))
    assert report["proof_count"] == 3
    assert report["verified_proofs"] == 0
    assert report["merged_proofs"] == 1
    assert report["failed_proofs_reconciled"] == 2
    assert report["failed_proofs_unreconciled"] == 1
    assert report["feed_gate_pass"] is False
