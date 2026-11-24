"""Independent source pinning and retrospective-only coverage adapter examples."""

from decimal import Decimal
import gzip
import hashlib
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(
    0, str(Path(__file__).resolve().parents[1] / "scripts/scoring_experiment")
)
import verify_preserved_feed_replay as replay


def heartbeat(ts, tid):
    return dict(receipt_ts_ms=ts, message={"last_trade_id": tid})


def matched(receipt, price="100", size="1", side="sell"):
    return dict(receipt=receipt, trade=(Decimal(price), Decimal(size), side))


def test_reconciliation_requires_both_sources_and_matching_amounts():
    hb = [heartbeat(1000, 10), heartbeat(11000, 12)]
    matches = {11: matched(5000), 12: matched(10000)}
    rest = {11: matches[11]["trade"], 12: matches[12]["trade"]}
    assert replay.reconcile(matches, rest, hb)["passed"] is True
    assert replay.reconcile(matches, {11: rest[11]}, hb)["missing_rest_ids"] == [12]
    assert replay.reconcile({11: matches[11]}, rest, hb)["missing_ws_ids"] == [12]
    rest[12] = (Decimal("101"), Decimal("1"), "sell")
    assert replay.reconcile(matches, rest, hb)["mismatch_ids"] == [12]


def test_heartbeat_gaps_and_outside_watermark_buckets_are_not_asserted():
    hb = [heartbeat(t, 10) for t in (1000, 6000, 11000, 20000, 25000, 30000)]
    proof = dict(passed=True, low_exclusive=10, high_inclusive=12)
    assert replay.coverage_spans({}, hb, proof) == [(5000, 10000), (20000, 30000)]
    outside = {9: matched(25001)}
    assert replay.coverage_spans(outside, hb, proof) == [(5000, 10000), (20000, 25000)]
    assert replay.coverage_spans({}, hb, {"passed": False}) == []


def fixture_capture(
    tmp_path, *, missing_ticker_subscription=False, oversized_receipt_span=False
):
    capture = tmp_path / "capture"
    capture.mkdir()
    base = 1000000000000
    pid = "TEST-USD"
    channels = [
        dict(name=n, product_ids=[pid])
        for n in ("matches", "heartbeat", "ticker")
        if not (missing_ticker_subscription and n == "ticker")
    ]
    quote = lambda tid: dict(
        type="ticker",
        product_id=pid,
        trade_id=tid,
        best_bid="99",
        best_ask="101",
        best_bid_size="2",
        best_ask_size="1",
        last_size="99999",
    )
    messages = [
        (0, dict(type="subscriptions", channels=channels)),
        (1, quote(10)),
        (
            2,
            dict(
                type="last_match",
                product_id=pid,
                trade_id=10,
                price="100",
                size="500",
                side="sell",
            ),
        ),
        (1000, dict(type="heartbeat", product_id=pid, last_trade_id=10)),
        (
            5998,
            dict(
                type="match",
                product_id=pid,
                trade_id=11,
                price="100",
                size="2",
                side="sell",
            ),
        ),
        (5999, quote(11)),
        (6000, dict(type="heartbeat", product_id=pid, last_trade_id=11)),
        (
            10998,
            dict(
                type="match",
                product_id=pid,
                trade_id=12,
                price="100",
                size="1",
                side="buy",
            ),
        ),
        (10999, quote(12)),
        (11000, dict(type="heartbeat", product_id=pid, last_trade_id=12)),
    ]
    if oversized_receipt_span:
        messages[-1] = (4000000, messages[-1][1])
    with gzip.open(capture / "websocket.jsonl.gz", "wt", encoding="utf-8") as stream:
        for seq, (offset, message) in enumerate(messages, 1):
            stream.write(
                json.dumps(
                    dict(
                        receipt_seq=seq,
                        receipt_ts_ms=base + offset,
                        receipt_monotonic_ns=(base + offset) * 1000000,
                        connection_id=1,
                        message=message,
                    )
                )
                + "\n"
            )
    trades = [msg for _, msg in messages if msg["type"] == "match"]
    with gzip.open(capture / "rest.jsonl.gz", "wt", encoding="utf-8") as stream:
        stream.write(
            json.dumps(dict(product_id=pid, receipt_ts_ms=base + 12000, trades=trades))
            + "\n"
        )
    write = lambda name, value: (capture / name).write_text(
        json.dumps(value) + "\n", encoding="utf-8"
    )
    write(
        "capture.json",
        dict(
            completed=True,
            elapsed_seconds=11,
            products=[pid],
            messages=len(messages),
            code_commit="synthetic",
            started_utc="2001-09-09T01:46:40Z",
            ended_utc="2001-09-09T01:46:51Z",
            errors=[],
            reconnects=0,
        ),
    )
    write("STATUS.json", dict(status="completed"))
    write(
        "REPORT.json",
        dict(
            errors={},
            rest_request_errors=0,
            hour_gate_pass=False,
            products={
                pid: dict(
                    unique_matches=2,
                    match_quote_usd="300",
                    coverage_verdict="rest_reconciled",
                    mapping_verdict="inconclusive",
                    messages=dict(ticker=3, last_match=1, heartbeat=3, match=2),
                )
            },
        ),
    )
    write(
        "MANIFEST.json",
        dict(
            sha256={
                n: replay.digest(capture / n)
                for n in ("capture.json", "websocket.jsonl.gz", "rest.jsonl.gz")
            }
        ),
    )
    manifest = tmp_path / "transfer.json"
    manifest.write_text(
        json.dumps(
            dict(
                files={
                    "fixture/"
                    + n: dict(
                        bytes=(capture / n).stat().st_size,
                        sha256=replay.digest(capture / n),
                    )
                    for n in replay.FILES
                }
            )
        ),
        encoding="utf-8",
    )
    return capture, manifest


def test_full_local_replay_does_not_backdate_health_or_change_source_files(tmp_path):
    capture, manifest = fixture_capture(tmp_path)
    before = {n: replay.digest(capture / n) for n in replay.FILES}
    result = replay.verify(capture, manifest, "fixture", tmp_path / "out")
    assert result["packets_replayed"] == 10
    assert (
        result["feed_gate_pass"] is False and result["original_hour_gate_pass"] is False
    )
    assert result["original_contemporaneous_coverage_available"] is False
    product = result["products"]["TEST-USD"]
    assert (
        product["unique_live_matches"] == 2 and product["exact_raw_quote_usd"] == "300"
    )
    assert product["original_asof_unverified_cutoffs"] == 2
    stats = product["retrospective_statistics"]
    assert (
        stats["retrospectively_verified_buckets"] == 1
        and stats["fresh_midpoint_buckets"] == 1
    )
    assert product["last_capture_anchor_baseline_status"] == "unavailable"
    assert product["required_sigma_history_starts_before_capture"] is True
    assert {n: replay.digest(capture / n) for n in replay.FILES} == before
    assert (tmp_path / "out/ARTIFACT_MANIFEST.json").exists()


def test_tampering_is_rejected_before_any_output_is_created(tmp_path):
    capture, manifest = fixture_capture(tmp_path)
    with (capture / "REPORT.json").open("a", encoding="utf-8") as stream:
        stream.write(" ")
    with pytest.raises(ValueError, match="hash/size"):
        replay.verify(capture, manifest, "fixture", tmp_path / "out")
    assert not (tmp_path / "out").exists()


def test_missing_subscription_is_not_promoted_to_healthy_coverage(tmp_path):
    capture, manifest = fixture_capture(tmp_path, missing_ticker_subscription=True)
    with pytest.raises(ValueError, match="membership"):
        replay.verify(capture, manifest, "fixture", tmp_path / "out")
    failure = json.loads((tmp_path / "out/FAILURE.json").read_text(encoding="utf-8"))
    assert failure["feed_gate_pass"] is False


def test_output_inside_the_preserved_capture_is_refused(tmp_path):
    capture, manifest = fixture_capture(tmp_path)
    with pytest.raises(ValueError, match="outside"):
        replay.verify(capture, manifest, "fixture", capture / "derived")
    assert not (capture / "derived").exists()


def test_packet_time_span_is_bounded_independently_of_metadata_claim(tmp_path):
    capture, manifest = fixture_capture(tmp_path, oversized_receipt_span=True)
    with pytest.raises(ValueError, match="actual receipt-time span"):
        replay.verify(capture, manifest, "fixture", tmp_path / "out")
    assert (tmp_path / "out/FAILURE.json").exists()
    assert not (tmp_path / "out/REPLAY_REPORT.json").exists()
