"""Synthetic packet/replay tests; no network or live backend required."""

import gzip
import importlib.util
import json
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/coinbase_feed_audit.py"
spec = importlib.util.spec_from_file_location("feed_audit", SCRIPT)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


def packet(message, index):
    return {
        "message": message,
        "receipt_ts_ms": index * 1000,
        "receipt_monotonic_ns": index * 1_000_000_000,
        "receipt_seq": index,
        "connection_id": 1,
    }


def fixture_capture(
    tmp_path,
    ticker_taker=True,
    omit=None,
    products=("BTC-USD",),
    gap=False,
    seconds=3600,
):
    rows = [
        packet(
            {
                "type": "subscriptions",
                "channels": [
                    {"name": c, "product_ids": list(products)} for c in audit.CHANNELS
                ],
            },
            0,
        )
    ]
    rest = []
    for p in products:
        rows += [
            packet(
                {
                    "type": "last_match",
                    "product_id": p,
                    "trade_id": 100,
                    "price": "10",
                    "size": "2",
                    "side": "buy",
                },
                0,
            ),
            packet({"type": "heartbeat", "product_id": p, "last_trade_id": 100}, 0),
        ]
        trades = [{"trade_id": 100, "price": "10", "size": "2", "side": "buy"}]
        for i in range(1, 13):
            side = "sell" if i % 2 else "buy"
            match = {
                "type": "match",
                "product_id": p,
                "trade_id": 100 + i,
                "price": "10",
                "size": "2",
                "side": side,
            }
            ticker = {
                **match,
                "type": "ticker",
                "last_size": "2",
                "side": ("buy" if side == "sell" else "sell") if ticker_taker else side,
            }
            ticker.pop("size")
            if i != omit:
                rows.append(packet(match, i))
            rows.append(packet(ticker, i))
            rows.append(
                packet(
                    {"type": "heartbeat", "product_id": p, "last_trade_id": 100 + i}, i
                )
            )
            trades.append(
                {k: v for k, v in match.items() if k not in ("type", "product_id")}
            )
        # Keep transport heartbeats healthy to the requested endpoint.
        for i in range(13, int(seconds) + 1):
            if not gap or not 20 <= i <= 40:
                rows.append(
                    packet(
                        {"type": "heartbeat", "product_id": p, "last_trade_id": 112}, i
                    )
                )
        rest.append({"product_id": p, "trades": trades})
    rows.sort(key=lambda r: r["receipt_monotonic_ns"])
    save(tmp_path, rows, rest, products, seconds)
    return rows, rest


def save(path, rows, rest, products=("BTC-USD",), seconds=3600):
    audit.write_json(
        path / "capture.json",
        {
            "products": list(products),
            "start_monotonic_ns": 0,
            "end_monotonic_ns": seconds * 1_000_000_000,
            "elapsed_seconds": seconds,
            "completed": True,
            "errors": [],
        },
    )
    for name, values in [("websocket.jsonl.gz", rows), ("rest.jsonl.gz", rest)]:
        with gzip.open(path / name, "wt", encoding="utf-8") as stream:
            for row in values:
                audit.append_json(stream, row)
    audit.write_json(
        path / "MANIFEST.json",
        {
            "sha256": {
                name: audit.digest(path / name)
                for name in ["capture.json", "websocket.jsonl.gz", "rest.jsonl.gz"]
            }
        },
    )


@pytest.mark.parametrize("taker", [True, False])
def test_mapping_both_sides_and_reconciled_hour(tmp_path, taker):
    fixture_capture(tmp_path, ticker_taker=taker)
    report = audit.analyze(tmp_path)
    p = report["products"]["BTC-USD"]
    assert p["mapping_verdict"] == (
        "ticker_taker_side_supported" if taker else "ticker_maker_side_supported"
    )
    assert p["unique_matches"] == 12  # last_match is excluded
    assert p["match_quote_usd"] == "240"
    assert p["coverage_verdict"] == "rest_reconciled" and report["hour_gate_pass"]


def test_missing_match_is_not_hidden_by_rest_recovery(tmp_path):
    fixture_capture(tmp_path, omit=6)
    report = audit.analyze(tmp_path)
    p = report["products"]["BTC-USD"]
    assert p["match_id_gap_candidates"] == [[106, 106]]
    assert p["rest_id_gap_candidates"] == []
    assert p["coverage_verdict"] == "incomplete_or_unverified"
    assert not report["hour_gate_pass"]


def test_product_identity_reorder_duplicate_and_ticker_batching(tmp_path):
    rows, rest = fixture_capture(tmp_path, products=("BTC-USD", "SOL-USD"))
    # A duplicate arriving late does not add volume; a batched-out ticker doesn't remove a match.
    duplicate = next(r.copy() for r in rows if r["message"].get("type") == "match")
    duplicate["receipt_monotonic_ns"] = 15_000_000_000
    duplicate["receipt_ts_ms"] = 15000
    rows.append(duplicate)
    rows = [
        r
        for r in rows
        if not (
            r["message"].get("type") == "ticker" and r["message"].get("trade_id") == 102
        )
    ]
    rows.sort(key=lambda r: r["receipt_monotonic_ns"])
    save(tmp_path, rows, rest, products=("BTC-USD", "SOL-USD"))
    report = audit.analyze(tmp_path)
    btc, sol = report["products"].values()
    assert btc["unique_matches"] == sol["unique_matches"] == 12
    assert btc["match_quote_usd"] == sol["match_quote_usd"] == "240"
    assert btc["duplicates"]["match"] == 1 and btc["reordered"]["match"] == 1
    assert (
        btc["ticker_trade_count_coverage"]
        == sol["ticker_trade_count_coverage"]
        == 11 / 12
    )


def test_conflicting_sides_and_payload_mismatch_are_inconclusive(tmp_path):
    rows, rest = fixture_capture(tmp_path)
    ticker = next(r for r in rows if r["message"].get("type") == "ticker")
    ticker["message"]["last_size"] = "999"
    save(tmp_path, rows, rest)
    assert (
        audit.analyze(tmp_path)["products"]["BTC-USD"]["mapping_verdict"]
        == "inconclusive"
    )


def test_heartbeat_outage_and_short_smoke_cannot_pass_hour(tmp_path):
    fixture_capture(tmp_path, gap=True)
    assert not audit.analyze(tmp_path)["hour_gate_pass"]
    fixture_capture(tmp_path, seconds=60)
    report = audit.analyze(tmp_path)
    assert report["products"]["BTC-USD"]["coverage_verdict"] == "rest_reconciled"
    assert not report["hour_gate_pass"]


def test_hash_tamper_rejected_and_replay_is_deterministic(tmp_path):
    fixture_capture(tmp_path)
    first = audit.analyze(tmp_path)
    assert audit.analyze(tmp_path) == first
    with (tmp_path / "rest.jsonl.gz").open("ab") as stream:
        stream.write(b"tampered")
    with pytest.raises(ValueError, match="hash mismatch"):
        audit.analyze(tmp_path)
