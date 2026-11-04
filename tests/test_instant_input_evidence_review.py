"""Independent review probes for input-evidence stage 1 (Codex 8607a36).

Claude review at tip fee55a7. The tape helper here is written from the
recorder's contract, not copied from the implementation's own tests, and sets
watermarks, connections and processing clocks explicitly. Everything is
synthetic. Nothing here authenticates a feed, proves a healthy capture or
produces positive eligibility, and the last section says so executably.
"""

from dataclasses import FrozenInstanceError
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest

sys.path.insert(
    0, str(Path(__file__).resolve().parents[1] / "scripts/scoring_experiment")
)
import instant_input_evidence as evidence  # noqa: E402
from instant_input_evidence import InputEvidenceRecorder  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
COIN, BTC, ZZZ = "ALT-USD", "BTC-USD", "ZZZ-USD"
NOT_IMPLEMENTED = {
    "baseline_evidence_not_implemented",
    "feature_evidence_not_implemented",
    "publication_policy_unfrozen",
    "full_feed_evidence_not_verified",
}


class Tape:
    """Explicit watermarks, connections and a five-step per-packet clock."""

    def __init__(self, products=(COIN, BTC), first=30000, stop=40000, start_clock=0):
        self.now, self.steps, self.seq, self.events = start_clock, [], 0, []
        self.rec = InputEvidenceRecorder(
            list(products), first, stop, clock_ms=self._clock
        )

    def _clock(self):
        if self.steps:
            self.now = self.steps.pop(0)
        return self.now

    def send(self, ts, kind, pid=COIN, conn=1, source=None, steps=None, **fields):
        self.now = max(self.now, ts)
        self.steps = list(steps or [])
        self.seq += 1
        env = dict(
            receipt_seq=self.seq,
            receipt_ts_ms=ts,
            receipt_monotonic_ns=ts * 1000000,
            connection_id=conn,
            message=dict(type=kind, product_id=pid, **fields),
        )
        if source:
            env["source"] = source
        self.events.append(env)
        self.rec.ingest(env)
        return env

    def ack(self, ts=0, products=(COIN, BTC), conn=1):
        self.send(
            ts,
            "subscriptions",
            conn=conn,
            channels=[
                dict(name=c, product_ids=list(products))
                for c in ("matches", "heartbeat", "level2_batch")
            ],
        )

    def hb(self, ts, last, pid=COIN, conn=1, **kw):
        self.send(ts, "heartbeat", pid, conn=conn, last_trade_id=last, **kw)

    def snap(self, ts, pid=COIN, conn=1):
        self.send(
            ts, "snapshot", pid, conn=conn, bids=[["99", "2"]], asks=[["101", "1"]]
        )

    def trade(
        self, ts, tid, pid=COIN, conn=1, side="sell", price="100", size="2", **kw
    ):
        return self.send(
            ts,
            "match",
            pid,
            conn=conn,
            trade_id=tid,
            price=price,
            size=size,
            side=side,
            **kw,
        )

    def comp(self, cutoff, pid=COIN, asof=None):
        return self.rec.component_evidence(pid, cutoff, asof=asof)


def healthy(tape, through=30000, products=(COIN, BTC), watermark=10, snapshots=True):
    """Heartbeats every second with a fixed watermark; fresh snapshots every 5s."""
    tape.ack(0, products)
    for ts in range(0, through + 1, 1000):
        for p in products:
            tape.hb(ts, watermark, p)
        if snapshots and ts % 5000 == 0 and ts < through:
            for p in products:
                tape.snap(ts + 10, p)
    return tape


def rows_of(cohort, pid):
    return [r.to_dict() for r in cohort if r.product_id == pid]


# --- Inventory ----------------------------------------------------------------


def test_inventory_is_the_full_cross_product_and_canonical_across_order():
    a = Tape((BTC, COIN))
    b = Tape((COIN, BTC))
    assert a.rec.inventory_sha256 == b.rec.inventory_sha256
    a.now = 40000
    report = a.rec.seal()
    keys = {
        (r["product_id"], r["direction"], r["cutoff_ts_ms"]) for r in report["rows"]
    }
    assert keys == {
        (p, d, t) for p in (COIN, BTC) for d in ("up", "down") for t in (30000, 35000)
    }
    assert report["expected_rows"] == report["recorded_rows"] == 8
    assert report["inventory"]["products"] == [COIN, BTC]  # sorted, order-independent


@pytest.mark.parametrize(
    "declared,precedes", [(29999, True), (30000, False), (10_000_000, False)]
)
def test_declaration_time_is_measured_separately_from_the_plan_hash(declared, precedes):
    reference = Tape().rec.inventory_sha256
    tape = Tape(start_clock=declared)
    assert tape.rec.inventory_sha256 == reference
    assert tape.rec.inventory_recorded_ts_ms == declared
    tape.now = max(declared, 40000)
    report = tape.rec.seal()
    assert report["inventory_precedes_first_cutoff"] is precedes
    flagged = all(
        "inventory_recorded_after_first_cutoff" in r["unavailable_reasons"]
        for r in report["rows"]
    )
    assert flagged is (not precedes)


def test_planned_product_with_no_packets_keeps_all_rows_with_explicit_reasons():
    tape = healthy(Tape((COIN, BTC, ZZZ)), products=(COIN, BTC))
    cohort = tape.rec.checkpoint(30000)
    zzz = rows_of(cohort, ZZZ)
    assert len(zzz) == 2 and {r["direction"] for r in zzz} == {"up", "down"}
    for row in zzz:
        assert row["components"]["coin"]["quote"]["available"] is False
        assert row["components"]["coin"]["trades_30s"]["verified_trade_count"] is None
        assert any(x.startswith("coin:quote:") for x in row["unavailable_reasons"])
        assert any(x.startswith("coin:trades:") for x in row["unavailable_reasons"])
        assert row["components"]["benchmark"]["quote"]["available"] is True


def test_completeness_is_relative_to_the_plan_not_the_tape():
    tape = healthy(
        Tape((COIN, BTC)), products=(COIN, BTC, ZZZ)
    )  # ZZZ on the wire, not in the plan.
    tape.now = 40000
    report = tape.rec.seal()
    assert report["expected_rows"] == report["recorded_rows"] == 8
    assert not any(r["product_id"] == ZZZ for r in report["rows"])
    assert "ZZZ" not in json.dumps(report)  # Nothing flags the unplanned product.


@pytest.mark.parametrize(
    "products,first,stop",
    [
        ((COIN, BTC), 30000, 30000 + 5000 * 2501),  # 10,004 rows
        ((COIN, BTC), 25000, 35000),
        ((COIN, BTC), 30000, 35001),
        ((COIN, BTC), 35000, 30000),
        ((COIN, ""), 30000, 35000),
        ((COIN, 1, BTC), 30000, 35000),
        (tuple(f"P{i}-USD" for i in range(32)) + (BTC,), 30000, 35000),
    ],
)
def test_inventory_bounds_and_identities_are_enforced(products, first, stop):
    with pytest.raises(ValueError):
        InputEvidenceRecorder(list(products), first, stop)


def test_inventory_row_cap_is_inclusive():
    rec = InputEvidenceRecorder(
        [COIN, BTC], 30000, 30000 + 5000 * 2500
    )  # exactly 10,000
    assert len(rec.cutoffs) * 2 * 2 == 10000


# --- Payload completion versus receipt, book and monitor completion -------------


def test_late_merged_proof_is_known_at_producer_completion_and_never_backdated():
    tape = healthy(Tape(), through=29000)
    tape.hb(29500, 11)  # Overtakes match 11: interval [29000,29500) fails.
    tape.trade(29600, 11)
    # Closing heartbeat: producer 30000, monitor 30001-30002, book 30003, producer done 30500.
    tape.hb(30000, 11, steps=[30000, 30001, 30002, 30003, 30500])
    tape.hb(30000, 10, BTC)
    frozen = rows_of(tape.rec.checkpoint(30000), COIN)[0]["components"]["coin"][
        "trades_30s"
    ]
    assert (
        frozen["reason"] == "missing_live_match_ids"
        and frozen["verified_trade_count"] is None
    )
    assert frozen["known_unique_match_count"] == 1
    monitor_only = tape.comp(30000, asof=30100)["trades_30s"]
    assert (
        monitor_only["proof_available_ts_ms"] == 30002
    )  # Monitor has the merged proof.
    assert monitor_only["reason"] == "trade_row_processing_incomplete"
    assert monitor_only["verified_trade_count"] is None
    done = tape.comp(30000, asof=30500)["trades_30s"]
    assert done["receipt_id_check_passed"] and done["verified_trade_count"] == 1
    assert done["quote_volume_usd"] == "200" and done["taker_buy_usd"] == "200"
    assert (
        rows_of(tape.rec.checkpoint(30000), COIN)[0]["components"]["coin"]["trades_30s"]
        == frozen
    )


def test_trade_row_completion_always_precedes_its_closing_proof():
    """Sequential ingest: a row's payload completes before the proof closing it.

    So the producer's len(known) == len(rows) guard is defensive; the reachable
    gate is the closing heartbeat's own producer completion (probe above).
    """
    tape = healthy(Tape(), through=29000)
    tape.trade(29500, 11, steps=[29500, 29501, 29502, 29503, 30200])
    tape.hb(30000, 11, steps=[30200, 30200, 30200, 30200, 30201])
    tape.hb(30000, 10, BTC)
    tape.now = 30201
    trade, closing = tape.rec.trades[-1], tape.rec.packets[-2]
    assert trade.available_ts_ms == 30200 <= closing.available_ts_ms
    early = tape.comp(30000, asof=30150)["trades_30s"]
    assert early["known_unique_match_count"] == 0
    assert early["verified_trade_count"] is None
    assert early["reason"] == "trade_coverage_not_yet_proven"  # Proof unknown first.
    late = tape.comp(30000, asof=30201)["trades_30s"]
    assert late["known_unique_match_count"] == 1 and late["verified_trade_count"] == 1


def test_heartbeat_payload_completion_gates_the_quote_even_when_book_is_done():
    tape = healthy(Tape(), through=29000)
    # Book and monitor finish within the cutoff; the producer finishes after it.
    tape.hb(29999, 10, steps=[29999, 29999, 29999, 29999, 30001])
    tape.hb(29999, 10, BTC, steps=[30001, 30001, 30001, 30001, 30001])
    assert tape.rec.book.view(COIN, 30000).book_state_available
    at_cutoff = tape.comp(30000)["quote"]
    assert at_cutoff["available"] is False and at_cutoff["bid"] is None
    assert at_cutoff["reason"] == "quote_row_processing_incomplete"
    later = tape.comp(30000, asof=30001)["quote"]
    assert later["available"] is True and later["bid"] == "99"
    assert later["book_processing_available_ts_ms"] == 25011  # the snapshot state


def test_receipt_time_never_stands_in_for_completion():
    tape = Tape()
    tape.ack()
    tape.trade(100, 11, steps=[100, 100, 100, 100, 100])
    packet, trade = tape.rec.packets[-1], tape.rec.trades[-1]
    assert packet.processing_completed_ts_ms == 100
    assert packet.available_ts_ms == trade.available_ts_ms == 101  # receipt + 1 floor
    assert (
        packet.envelope_sha256
        == hashlib.sha256(evidence._json(tape.events[-1]).encode()).hexdigest()
    )


# --- Deduplication, sides, epochs ------------------------------------------------


def test_first_receipt_wins_across_connections_and_a_conflict_vetoes():
    tape = Tape()
    tape.ack()
    tape.hb(0, 10)
    tape.trade(1000, 11, conn=1, steps=[1000, 1000, 1000, 1000, 1000])
    tape.ack(1000, conn=2)
    tape.trade(1000, 11, conn=2)  # Same signature on a new connection.
    tape.trade(
        1500, 11, conn=2, price="100.00", size="2.0"
    )  # Same amounts, new spelling.
    assert len(tape.rec.trades) == 1
    first = tape.rec.trades[0]
    assert (first.connection_id, first.receipt_ts_ms, first.available_ts_ms) == (
        1,
        1000,
        1001,
    )
    tape.trade(2000, 11, conn=2, price="101")  # Conflicting duplicate.
    assert len(tape.rec.trades) == 1
    tape.now = 30000
    view = tape.comp(30000)["trades_30s"]
    assert (
        view["reason"] == "conflicting_trade_id"
        and view["verified_trade_count"] is None
    )


def test_mixed_known_and_unknown_sides_keep_amounts_separate_and_block_flow():
    tape = healthy(Tape(), through=29000)
    tape.trade(29100, 11, side="sell")  # taker buy
    tape.trade(29200, 12, side="weird")
    tape.hb(30000, 12)
    tape.hb(30000, 10, BTC)
    tape.now = 30001
    view = tape.comp(30000, asof=30001)["trades_30s"]
    assert view["verified_trade_count"] == 2
    assert (
        view["taker_buy_usd"],
        view["taker_sell_usd"],
        view["unknown_side_usd"],
    ) == ("200", "0", "200")
    assert view["quote_volume_usd"] == "400" and view["flow_available"] is False


def test_shared_millisecond_connection_change_cannot_certify_the_old_receipt():
    tape = Tape()
    tape.ack(0, conn=1)
    tape.hb(0, 10, conn=1)
    tape.trade(0, 11, conn=1)  # First receipt at 0 on connection 1.
    tape.ack(0, conn=2)
    for p in (COIN, BTC):
        tape.hb(0, 11 if p == COIN else 10, p, conn=2)
    for ts in range(1000, 30001, 1000):
        for p in (COIN, BTC):
            tape.hb(ts, 11 if p == COIN else 10, p, conn=2)
    tape.now = 30001
    view = tape.comp(30000, asof=30001)["trades_30s"]
    assert view["known_unique_match_count"] == 1
    assert tape.rec.trades[0].connection_id == 1  # Receipt attribution unchanged.
    assert (
        view["reason"] == "trade_row_continuity_mismatch"
        and view["verified_trade_count"] is None
    )


def test_proof_in_one_epoch_and_trade_in_another_at_a_shared_millisecond_fails():
    tape = Tape()
    tape.ack(0)
    tape.hb(0, 10)
    tape.trade(0, 11)  # Receipt 0, epoch 0, exactly at the window start.
    tape.send(0, "queue_overflow", pid=None)
    tape.ack(0)
    tape.hb(0, 11)
    tape.hb(0, 10, BTC)
    for ts in range(1000, 30001, 1000):
        tape.hb(ts, 11)
        tape.hb(ts, 10, BTC)
    tape.now = 30001
    view = tape.comp(30000, asof=30001)["trades_30s"]
    assert (
        view["known_unique_match_count"] == 1 and view["verified_trade_count"] is None
    )
    assert view["reason"] == "trade_row_continuity_mismatch"


# --- Verified zeros, quotes, benchmark ---------------------------------------------


def test_verified_zero_needs_a_proof_and_quote_is_an_independent_component():
    tape = healthy(Tape(), snapshots=False)  # Heartbeats only: no book ever.
    tape.now = 30001
    comp = tape.comp(30000, asof=30001)
    assert comp["trades_30s"]["verified_trade_count"] == 0
    assert comp["trades_30s"]["quote_volume_usd"] == "0"
    assert comp["quote"]["available"] is False and comp["quote"]["bid"] is None
    at_cutoff = tape.comp(30000)["trades_30s"]
    assert at_cutoff["verified_trade_count"] is None  # Closing beat known at 30001.
    assert at_cutoff["reason"] == "trade_coverage_not_yet_proven"


def test_stale_quote_keeps_original_observation_and_is_not_zero_volume():
    tape = Tape()
    tape.ack()
    for p in (COIN, BTC):
        tape.hb(0, 10, p)
    for p in (COIN, BTC):
        tape.snap(10, p)
    for ts in range(1000, 30001, 1000):
        for p in (COIN, BTC):
            tape.hb(ts, 10, p)
    tape.now = 30001
    comp = tape.comp(30000, asof=30001)
    assert comp["quote"]["reason"] == "stale_book_observation"
    assert comp["quote"]["observation_ts_ms"] == 10
    assert comp["quote"]["observation_age_ms"] == 29990
    assert comp["trades_30s"]["verified_trade_count"] == 0  # Trades proven; quote not.


def test_missing_benchmark_marks_every_row_including_btc_own_rows():
    tape = healthy(Tape(), products=(COIN,))
    cohort = tape.rec.checkpoint(30000)
    for row in (r.to_dict() for r in cohort):
        assert any(x.startswith("benchmark:quote:") for x in row["unavailable_reasons"])
        assert any(
            x.startswith("benchmark:trades:") for x in row["unavailable_reasons"]
        )
    coin = rows_of(cohort, COIN)[0]["components"]
    assert coin["coin"]["quote"]["available"] is True
    assert coin["benchmark"]["quote"]["available"] is False
    btc = rows_of(cohort, BTC)[0]["components"]
    assert btc["coin"] == btc["benchmark"]


# --- Cohort immutability and timing -------------------------------------------------


def test_cohort_is_frozen_identical_after_seal_and_decoded_copies_are_independent():
    tape = healthy(Tape())
    cohort = tape.rec.checkpoint(30000)
    before = [r.to_dict() for r in cohort]
    with pytest.raises(FrozenInstanceError):
        cohort[0].unavailable_reasons = ()
    copy = cohort[0].to_dict()
    copy["components"]["coin"]["trades_30s"]["verified_trade_count"] = 99
    assert [r.to_dict() for r in cohort] == before
    tape.trade(31000, 11)
    tape.send(31500, "audit_transport_error", pid=None)
    tape.now = 40000
    report = tape.rec.seal()
    assert tape.rec.checkpoint(30000) is cohort
    assert report["rows"][: len(before)] == before


def test_late_checkpoint_never_adds_evidence_beyond_cutoff_knowledge():
    prompt = healthy(Tape())
    prompt.now = 30001
    early = [r.to_dict()["components"] for r in prompt.rec.checkpoint(30000)]
    late = healthy(Tape())
    late.trade(31000, 11)
    for ts in range(31000, 36001, 1000):
        late.hb(ts, 11)
        late.hb(ts, 10, BTC)
    late.now = 36001
    later = [r.to_dict()["components"] for r in late.rec.checkpoint(30000)]
    assert early == later
    assert early[0]["coin"]["trades_30s"]["reason"] == "trade_coverage_not_yet_proven"


def test_assessment_time_is_measured_and_separate_from_knowledge():
    tape = healthy(Tape())
    tape.steps = [30000, 30007]
    cohort = tape.rec.checkpoint(30000)
    assert {r.assessment_completed_ts_ms for r in cohort} == {30007}
    row = cohort[0].to_dict()
    assert row["components"]["coin"]["knowledge_asof_ts_ms"] == 30000
    assert "assessment_completed_after_cutoff" in row["unavailable_reasons"]


@pytest.mark.parametrize(
    "cutoff,asof",
    [
        (30000.0, None),
        (True, None),
        (32500, None),
        (30000, 29999),
        (30000, 30000.0),
        (30000, True),
    ],
)
def test_component_queries_need_a_planned_int_cutoff_and_causal_int_asof(cutoff, asof):
    tape = healthy(Tape())
    with pytest.raises(ValueError):
        tape.rec.component_evidence(COIN, cutoff, asof=asof)


# --- Clock, sequence, cap failures --------------------------------------------------


@pytest.mark.parametrize("bad", [1.5, True, -1, "30000"])
def test_non_integer_or_negative_clock_fails_closed(bad):
    tape = Tape()
    tape.ack()
    with pytest.raises(ValueError):
        tape.hb(1000, 10, steps=[bad])
    assert tape.rec.failed
    for call in (lambda: tape.rec.checkpoint(30000), tape.rec.seal, tape.rec.report):
        with pytest.raises(ValueError):
            call()


def test_tape_must_start_at_sequence_one_and_stay_contiguous():
    tape = Tape()
    tape.seq = 1  # First packet would be seq 2.
    with pytest.raises(ValueError, match="sequence 1"):
        tape.ack()
    assert tape.rec.failed
    tape = Tape()
    tape.ack()
    tape.seq += 1
    with pytest.raises(ValueError):
        tape.hb(1000, 10)
    assert tape.rec.failed and len(tape.rec.packets) == 1


def test_packet_cap_is_inherited_from_the_monitor(monkeypatch):
    import instant_coverage

    tape = Tape()  # Construct first: the cap is checked against the contract.
    monkeypatch.setattr(instant_coverage, "MAX_PACKETS", 2)
    tape.ack()
    tape.hb(0, 10)
    with pytest.raises(ValueError, match="packet bound"):
        tape.hb(1000, 10)
    assert tape.rec.failed


# --- CLI -----------------------------------------------------------------------------


def _cli(source, plan, output):
    return subprocess.run(
        [
            sys.executable,
            str(Path(evidence.__file__)),
            str(source),
            "--inventory",
            str(plan),
            "--out-dir",
            str(output),
        ],
        capture_output=True,
        text=True,
    )


def _write_tape(path, events):
    with gzip.open(path, "wt", encoding="utf-8") as stream:
        for event in events:
            stream.write(json.dumps(event) + "\n")


def test_cli_reports_plan_hash_all_rows_unavailable_and_refuses_bad_layouts(tmp_path):
    inputs = tmp_path / "in"
    inputs.mkdir()
    tape = healthy(Tape(stop=35000))
    source, plan = inputs / "tape.jsonl.gz", inputs / "plan.json"
    _write_tape(source, tape.events)
    plan.write_text(
        json.dumps(dict(products=[BTC, COIN], first_cutoff=30000, stop_cutoff=35000)),
        encoding="utf-8",
    )
    assert _cli(source, plan, inputs / "nested").returncode != 0
    assert not (inputs / "nested").exists()
    out = tmp_path / "out"
    run = _cli(source, plan, out)
    assert run.returncode == 0, run.stderr
    report = json.loads((out / "REPORT.json").read_text(encoding="utf-8"))
    assert (
        report["inventory_file_sha256"] == hashlib.sha256(plan.read_bytes()).hexdigest()
    )
    assert report["input_sha256"] == hashlib.sha256(source.read_bytes()).hexdigest()
    assert report["recorded_rows"] == report["expected_rows"] == 4
    assert report["inventory_precedes_first_cutoff"] is False
    assert all(r["eligibility_status"] == "unavailable" for r in report["rows"])
    assert all(not r["study_eligible"] for r in report["rows"])
    assert not (out / "FAILURE.json").exists()
    packets = (out / "packet_processing.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(packets) == len(tape.events)


def test_cli_leaves_a_failure_record_and_no_report_for_a_broken_tape(tmp_path):
    inputs = tmp_path / "in"
    inputs.mkdir()
    tape = healthy(Tape(stop=35000))
    events = tape.events[:5] + tape.events[6:]  # Sequence gap.
    source, plan = inputs / "tape.jsonl.gz", inputs / "plan.json"
    _write_tape(source, events)
    plan.write_text(
        json.dumps(dict(products=[COIN, BTC], first_cutoff=30000, stop_cutoff=35000)),
        encoding="utf-8",
    )
    out = tmp_path / "out"
    assert _cli(source, plan, out).returncode != 0
    failure = json.loads((out / "FAILURE.json").read_text(encoding="utf-8"))
    assert failure["status"] == "failed" and "sequence" in failure["reason"]
    assert not (out / "REPORT.json").exists()


# --- Scope, stated executably ----------------------------------------------------------


def test_a_fully_healthy_tape_still_has_no_positive_eligibility_path():
    tape = healthy(Tape())
    tape.now = 40000
    for ts in range(31000, 40001, 1000):
        for p in (COIN, BTC):
            tape.hb(ts, 10, p)
        if ts % 5000 == 0 and ts < 40000:
            for p in (COIN, BTC):
                tape.snap(ts + 10, p)
    report = tape.rec.seal()
    for row in report["rows"]:
        assert (
            row["eligibility_status"] == "unavailable"
            and row["study_eligible"] is False
        )
        assert NOT_IMPLEMENTED <= set(row["unavailable_reasons"])
    for flag in (
        "full_feed_verified",
        "positive_eligibility_supported",
        "directional_report_adapter_supported",
        "durable_publication_verified",
        "study_frozen",
        "feed_gate_pass",
        "fitting_allowed",
        "live_integration",
    ):
        assert report[flag] is False
    text = json.dumps(report)
    assert 'eligible": true' not in text.lower()


def test_empty_tape_accounts_for_every_row_but_every_component_is_unavailable():
    tape = Tape()
    tape.now = 40000
    report = tape.rec.seal()
    assert report["packet_count"] == 0 and report["recorded_rows"] == 8
    for row in report["rows"]:
        reasons = row["unavailable_reasons"]
        assert any(x.startswith("coin:quote:") for x in reasons)
        assert any(x.startswith("coin:trades:") for x in reasons)
        assert row["components"]["coin"]["trades_30s"]["verified_trade_count"] is None


def test_module_imports_offline_and_touches_no_report_or_target_code():
    code = (
        "import sys; sys.path.insert(0, sys.argv[1]); import instant_input_evidence;"
        "bad = {'instant_directional_exposure','instant_association','instant_targets',"
        " 'instant_diagnostics','micro_replay','socket','ssl','http','urllib.request',"
        " 'requests','websocket','websockets','backend'} & set(sys.modules);"
        "print(sorted(bad)); sys.exit(1 if bad else 0)"
    )
    run = subprocess.run(
        [sys.executable, "-I", "-c", code, str(ROOT / "scripts/scoring_experiment")],
        capture_output=True,
        text=True,
    )
    assert run.returncode == 0, run.stdout + run.stderr


def test_contract_and_sources_are_hashed_into_every_report():
    tape = Tape()
    tape.now = 40000
    report = tape.rec.seal()
    src = (ROOT / "scripts/scoring_experiment/instant_input_evidence.py").read_text(
        "utf-8"
    )
    con = (
        ROOT / "docs/research/INSTANT_INPUT_EVIDENCE_CONTRACT_V1_DRAFT.json"
    ).read_text("utf-8")
    assert report["implementation_sha256"] == hashlib.sha256(src.encode()).hexdigest()
    assert report["contract_sha256"] == hashlib.sha256(con.encode()).hexdigest()
    assert report["book_implementation_sha256"] == tape.rec.book.source_sha256
    assert (
        report["monitor_implementation_sha256"] == tape.rec.book.monitor.source_sha256
    )
    assert (
        report["inventory_sha256"]
        == hashlib.sha256(tape.rec.inventory.encode()).hexdigest()
    )
