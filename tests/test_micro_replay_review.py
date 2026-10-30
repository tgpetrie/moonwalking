"""Independent Claude review probes for the offline replay/baseline prototype (8211262). Synthetic only."""

import math
from pathlib import Path
import sys

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts/scoring_experiment"))
from micro_replay import ReplayStore  # noqa: E402
from micro_baseline import build_baseline  # noqa: E402

PID, BTC = "TEST-USD", "BTC-USD"


def env(seq, ts, message, mono="auto", **extra):
    out = dict(receipt_seq=seq, receipt_ts_ms=ts, connection_id=1, message=message, **extra)
    if mono == "auto":
        out["receipt_monotonic_ns"] = ts * 1_000_000
    elif mono is not None:
        out["receipt_monotonic_ns"] = mono
    return out


def tick(pid, bid, ask):
    return {"type": "ticker", "product_id": pid, "best_bid": bid, "best_ask": ask, "best_bid_size": 1, "best_ask_size": 1}


def match(pid, trade_id, side="sell", price=100, size=1):
    return {"type": "match", "product_id": pid, "trade_id": trade_id, "price": price, "size": size, "side": side}


def health(store, pid, start, end, available=None, verified=True):
    store.add_health(product=pid, start=start, end=end, available=end if available is None else available,
                     verified=verified, evidence="synthetic review assertion")


@pytest.fixture
def store(tmp_path):
    s = ReplayStore(tmp_path / "r.sqlite", create=True)
    yield s
    s.close()


# ---- reproduced recorder defects ---------------------------------------------------------------------------------

def test_untagged_source_defaults_to_ws_but_rest_shaped_trades_still_never_count(store):
    """Not a defect: coinbase_feed_audit.envelope() writes no `source` field, so the default is required to read real
    WS captures. REST trades (separate file, no `type`) cannot become executions even when untagged. The pipeline doc's
    'source tags must be explicit' overstates this; only REST rows re-wrapped as WS `match` messages would be at risk."""
    store.ingest(env(1, 100001, tick(PID, 99, 101)))                                 # untagged WS ticker
    store.ingest(env(2, 101000, match(PID, 7)))                                       # untagged WS-shaped match: counted
    rest_shape = {"product_id": PID, "trade_id": 8, "price": "100", "size": "1", "side": "buy", "time": "x"}
    store.ingest(env(3, 102000, rest_shape))                                          # untagged REST-shaped trade
    store.ingest(env(4, 103000, match(PID, 9), source="rest_recovery"))               # tagged recovery
    with pytest.raises(ValueError):
        store.ingest(env(5, 104000, match(PID, 10), source="replay"))                 # unknown tag fails closed
    assert [r[0] for r in store.db.execute("SELECT trade_id FROM trades")] == [7]


def test_monotonic_regression_across_a_packet_without_monotonic_time_fails_closed(store):
    """Fixed: the monotonic check compared only with the immediately previous packet, so 100 -> None -> 50 passed."""
    store.ingest(env(1, 100000, tick(PID, 99, 101), mono=100_000_000_000, source="ws"))
    store.ingest(env(2, 100100, tick(PID, 99, 101), mono=None, source="ws"))
    with pytest.raises(ValueError):
        store.ingest(env(3, 100200, tick(PID, 99, 101), mono=50_000_000_000, source="ws"))
    assert store.db.execute("SELECT value FROM meta WHERE key='status'").fetchone()[0] == "failed"


# ---- later knowledge cannot change an earlier feature ------------------------------------------------------------

def test_later_conflict_negative_health_and_late_quote_leave_the_earlier_snapshot_unchanged(store):
    store.ingest(env(1, 100001, tick(PID, 99, 101), source="ws"))
    store.ingest(env(2, 101000, match(PID, 7, side="sell"), source="ws"))
    store.ingest(env(3, 112000, tick(PID, 50, 51), source="ws"))                     # late quote, after the cutoff
    store.ingest(env(4, 113000, match(PID, 7, side="buy", size=3), source="ws"))     # conflicting duplicate, known at 113000
    health(store, PID, 100000, 105000)
    health(store, PID, 100000, 105000, available=120000, verified=False)             # negative audit known later
    store.finalize()
    live = store.snapshot(PID, 105000)
    assert live["trade_count"] == 1 and live["mid"] == 100 and live["taker_buy_usd"] == 100
    assert store.snapshot(PID, 105000, asof=113000)["trade_count"] is None           # conflict now known
    assert store.snapshot(PID, 105000, asof=120000)["trade_count"] is None           # negative audit now known
    assert store.snapshot(PID, 105000) == live


def test_span_known_only_after_the_anchor_does_not_cover_the_live_query(store):
    store.ingest(env(1, 100001, tick(PID, 99, 101), source="ws"))
    health(store, PID, 100000, 105000, available=130000)
    store.finalize()
    assert store.snapshot(PID, 105000)["reason"] == "unverified_coverage"
    assert store.snapshot(PID, 105000, asof=130000)["reason"] is None


# ---- independent baseline check -----------------------------------------------------------------------------------

ANCHOR = 7_215_000                       # 120 min + 15 s
SIGMA_END = (ANCHOR - 35000) // 60000 * 60000
SIGMA_START = SIGMA_END - 3_600_000
PACE_END = ANCHOR - 30000
PACE_START = PACE_END - 120 * 30000


def build_history(tmp_path, btc_flat=False, seed=3):
    rng = np.random.default_rng(seed)
    s = ReplayStore(tmp_path / f"b{seed}{btc_flat}.sqlite", create=True)
    closes = list(range(SIGMA_START, SIGMA_END + 1, 60000))
    coin = 100 * np.exp(np.cumsum(rng.normal(0, 0.002, len(closes))))
    btc = np.full(len(closes), 50000.0) if btc_flat else 50000 * np.exp(np.cumsum(rng.normal(0, 0.001, len(closes))))
    events = []
    for t, c, b in zip(closes, coin, btc):
        events.append((t - 1000, tick(PID, c * 0.9999, c * 1.0001)))
        events.append((t - 1000, tick(BTC, b * 0.9999, b * 1.0001)))
    counts = rng.integers(0, 6, 120)
    tid = 1
    for k, n in enumerate(counts):
        w0 = PACE_START + k * 30000
        for j in range(int(n)):
            events.append((w0 + 1000 + j, match(PID, tid, size=1 + j)))
            tid += 1
    events.append((PACE_END, match(PID, tid)))         # receipt exactly at pace_end belongs to the next window
    events.append((ANCHOR + 5000, tick(PID, 1, 2)))    # later quote must not matter
    for seq, (ts, msg) in enumerate(sorted(events, key=lambda e: e[0]), start=1):
        s.ingest(env(seq, ts, msg, source="ws"))
    for pid in (PID, BTC):
        health(s, pid, SIGMA_START - 70000, PACE_END, available=PACE_END)
    s.finalize()
    mids_coin = (coin * 0.9999 + coin * 1.0001) / 2
    mids_btc = (btc * 0.9999 + btc * 1.0001) / 2
    usd = [sum(100 * (1 + j) for j in range(int(n))) for n in counts]
    return s, np.diff(np.log(mids_coin)), np.diff(np.log(mids_btc)), counts, usd


def test_baseline_matches_an_independent_computation(tmp_path):
    s, rc, rb, counts, usd = build_history(tmp_path)
    out = build_baseline(s, PID, ANCHOR)
    assert out["status"] == "ready", out
    b = out["baseline"]
    assert (out["sigma_end_ts_ms"], out["pace_end_ts_ms"]) == (SIGMA_END, PACE_END) == (7_140_000, 7_185_000)
    assert b.return_count == len(rc) == 60 and b.pace_window_count == 120
    assert math.isclose(b.sigma_1m, float(np.std(rc, ddof=1)), rel_tol=1e-9)
    assert math.isclose(b.beta, float(np.polyfit(rb, rc, 1)[0]), rel_tol=1e-9) and b.beta_fallback is False
    assert b.pace_trade_median_30s == float(np.median(counts))
    assert math.isclose(b.pace_quote_usd_median_30s, float(np.median(usd)))
    assert (b.available_ts_ms, b.beta_available_ts_ms, b.pace_available_ts_ms) == (ANCHOR,) * 3
    s.close()


def test_flat_btc_uses_flagged_fallback(tmp_path):
    s, rc, *_ = build_history(tmp_path, btc_flat=True)
    b = build_baseline(s, PID, ANCHOR)["baseline"]
    assert b.beta == 1.0 and b.beta_fallback is True
    assert math.isclose(b.sigma_1m, float(np.std(rc, ddof=1)), rel_tol=1e-9)
    s.close()


def test_missing_benchmark_history_is_unavailable_not_fallback(tmp_path):
    s = ReplayStore(tmp_path / "nb.sqlite", create=True)
    s.ingest(env(1, SIGMA_START - 1000, tick(PID, 99, 101), source="ws"))
    health(s, PID, SIGMA_START - 70000, PACE_END, available=PACE_END)
    s.finalize()
    out = build_baseline(s, PID, ANCHOR)
    assert (out["status"], out["reason"], out["product"]) == ("unavailable", "baseline_coverage", BTC)
    s.close()
