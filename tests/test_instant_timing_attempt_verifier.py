import json

import pytest

from test_instant_stream_journal import BTC, COIN, Clock, send
from instant_delayed_decision import prepare_decision
from instant_input_evidence import _file_sha
from instant_stream_journal import StreamJournal, read_segment
from verify_instant_timing_attempt import verify


def test_timing_verifier_keeps_missed_slots_and_checks_consumer_receipts(tmp_path):
    channels = ["matches", "heartbeat", "level2_batch", "ticker"]
    plan = dict(
        products=[BTC, COIN],
        channels=channels,
        warmup_ms=0,
        cohort_count=2,
        cohort_step_ms=5000,
        cohort_evidence_offsets_ms=[1500, 5000],
        diagnostic_deadlines_ms={"1500": 2500, "5000": 6000},
    )
    path = tmp_path / "capture.sqlite"
    clock = Clock()
    with StreamJournal(
        path,
        [BTC, COIN],
        30000,
        40000,
        clock_ms=clock,
        monotonic_ns=clock.mono,
        indexed=True,
    ) as journal:
        connection = journal.open_connection()
        clock.now = 30000
        send(
            journal,
            connection,
            type="subscriptions",
            channels=[dict(name=c, product_ids=[BTC, COIN]) for c in channels],
        )
        clock.now = 31500
        decision = prepare_decision(journal.evidence, COIN, 30000, "up", asof=31500)
        receipt = journal.append_publication("fast", decision)
        clock.now = 41000
        journal.end_connection(connection)
        journal.finish()

    (tmp_path / "PLAN.json").write_text(json.dumps(plan), encoding="utf-8")
    observation = dict(
        publication_id="fast",
        decision_sha256=receipt.decision_sha256,
        commit_observed_ts_ms=receipt.local_commit_observed_ts_ms,
        consumer_seen_ts_ms=32500,
    )
    reported = dict(
        observation,
        cutoff_ts_ms=30000,
        knowledge_asof_ts_ms=31500,
        decision_completed_ts_ms=31500,
        product_id=COIN,
        direction="up",
    )
    report = dict(
        plan,
        stop="transport_error",
        segment=read_segment(path),
        journal_sha256=_file_sha(path),
        first_ack_ts_ms=30000,
        recovered_pending_ingress_frames=0,
        diagnostic_rows=[reported],
    )
    (tmp_path / "REPORT.json").write_text(json.dumps(report), encoding="utf-8")
    receipt_path = tmp_path / "observed.jsonl"
    receipt_path.write_text(json.dumps(observation) + "\n", encoding="utf-8")

    result = verify(tmp_path, plan_sha256=_file_sha(tmp_path / "PLAN.json"))
    assert result["publication_prefixes_verified"] == 1
    assert result["schedule_results"]["1500"]["products"][COIN] == dict(
        planned=2,
        journaled=1,
        complete_inputs=0,
        observed=1,
        within_bound=1,
        complete_and_within_bound=0,
    )
    missing = result["schedule_results"]["5000"]["products"][COIN]
    assert (missing["planned"], missing["journaled"], missing["observed"]) == (2, 0, 0)

    observation["consumer_seen_ts_ms"] = 31499
    receipt_path.write_text(json.dumps(observation) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="consumer observation differs"):
        verify(tmp_path)
