"""Synthetic checks for the fresh-replication driver: decision rule, windows and eligibility. No market data."""
import importlib.util
import json
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / f"scripts/scoring_experiment/{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


fresh = _load("live_movers_fresh_replication")
run = _load("live_movers_run")
freeze = _load("freeze_live_contract")
CFG = json.loads((ROOT / "docs/research/results/live_movers_contract_20261027/CONTRACT_PRODUCTION.json").read_text())


def rec(mean, iid, block, n=16):
    return {"mean": mean, "n_days": n, "iid_daily": {"lo": iid[0], "hi": iid[1]}, "moving_block_3d": {"lo": block[0], "hi": block[1]}}


@pytest.mark.parametrize("primary,b2,expected", [
    (rec(0.05, (0.02, 0.08), (0.01, 0.09)), 0.03, "keep"),
    (rec(0.02, (0.001, 0.04), (0.001, 0.04)), 0.001, "keep"),
    (rec(0.05, (0.02, 0.08), (0.01, 0.09)), -0.01, "inconclusive"),   # B1 worse, but B2 itself not positive
    (rec(0.05, (0.02, 0.08), (-0.001, 0.09)), 0.03, "inconclusive"),  # block interval reaches zero
    (rec(0.019, (0.01, 0.03), (0.01, 0.03)), 0.03, "inconclusive"),   # below the minimum effect, not ruled out
    (rec(0.0, (-0.02, 0.03), (-0.02, 0.03)), 0.03, "drop"),
    (rec(-0.03, (-0.06, 0.03), (-0.06, 0.03)), 0.03, "drop"),
    (rec(0.008, (0.001, 0.015), (0.0, 0.019)), 0.03, "drop"),         # minimum effect ruled out by both intervals
    (rec(0.008, (0.001, 0.015), (0.0, 0.021)), 0.03, "inconclusive"),
    (rec(0.05, (0.02, 0.08), (0.01, 0.09), n=11), 0.03, "insufficient"),
    (rec(0.05, (None, None), (None, None)), 0.03, "insufficient"),
])
def test_decision_rule(primary, b2, expected):
    assert fresh.decide(primary, {"mean": b2}) == expected


def test_windows_replace_only_dates():
    cfg = fresh.fresh_config(CFG)
    assert cfg["phases"] == fresh.PHASES and CFG["phases"] != fresh.PHASES
    assert {k: v for k, v in cfg.items() if k != "phases"} == {k: v for k, v in CFG.items() if k != "phases"}
    assert freeze.stamp(fresh.PHASES["test"][0]) >= freeze.stamp(CFG["decision_cutoff_exclusive_utc"])
    assert fresh.PHASES["secondary_gap"][0] == CFG["phases"]["test"][1]  # starts where locked validation ended


def _db(tmp_path, rows):
    db = tmp_path / "board_episodes.sqlite"
    con = sqlite3.connect(db)
    con.execute("create table episodes (id INTEGER, board TEXT, product_id TEXT, direction TEXT, entered_ts INTEGER, "
                "start_price REAL, start_change_pct REAL, gross_return_5m REAL, gross_return_15m REAL, "
                "feature_schema_version TEXT, feature_snapshot_json TEXT)")
    for i, (pid, ts, r5, extra) in enumerate(rows, 1):
        snap = {"model_version": "live-strength-v1", "captured_ts": ts - 5, "live_score": 60.0,
                "raw_inputs": {"pct_1m": 0.4, "pct_3m": 1.1, "volume_change_1h_pct": 20.0}}
        snap.update(extra)
        con.execute("insert into episodes values (?,?,?,?,?,?,?,?,?,?,?)",
                    (i, "confirmation_3m_up", pid, "up", ts, 1.0, 1.1, r5, 0.1, "live-strength-v1-snapshot-v2", json.dumps(snap)))
    con.commit()
    con.close()
    return db


def test_fresh_eligibility_windows_cooldown_and_labels(tmp_path):
    t = freeze.stamp
    start, gap_end = t("2026-10-28T00:00:00+00:00"), t("2026-10-28T00:00:00+00:00")
    rows = [
        ("AAA-USD", t("2026-10-17T23:59:00+00:00"), 0.1, {}),          # locked validation era: outside
        ("AAA-USD", t("2026-10-18T00:10:00+00:00"), 0.1, {}),          # within 3600s of the row above: cooldown
        ("BBB-USD", t("2026-10-20T00:00:00+00:00"), 0.1, {}),          # secondary window
        ("CCC-USD", gap_end - 900, 0.1, {}),                           # purged before the primary window
        ("DDD-USD", start, 0.1, {}),                                   # first primary second
        ("DDD-USD", start + 3599, 0.1, {}),                            # cooldown
        ("DDD-USD", start + 3600, 0.1, {}),                            # eligible again
        ("EEE-USD", start + 10, None, {}),                             # label unavailable
        ("FFF-USD", start + 20, 0.1, {"model_version": "other"}),      # different live model
        ("GGG-USD", t("2026-11-12T23:59:59+00:00"), 0.1, {}),          # last primary second
        ("HHH-USD", t("2026-11-13T00:00:00+00:00"), 0.1, {}),          # after the window
    ]
    df, rejects = fresh.load_fresh(_db(tmp_path, rows), fresh.fresh_config(CFG), freeze, run)
    assert list(zip(df["product_id"], df["phase"])) == [("BBB-USD", "secondary_gap"), ("DDD-USD", "test"),
                                                        ("DDD-USD", "test"), ("GGG-USD", "test")]
    assert rejects == {"outside_phases_or_purged": 3, "rolling_cooldown": 2, "label_unavailable": 1, "snapshot_or_model_version": 1}
    cov = fresh.coverage(df)
    assert cov["test"]["rows"] == 3 and cov["secondary_gap"]["rows"] == 1


def test_score_cell_recovers_a_known_ordering():
    """A ranker built to follow the outcome scores positive, its inverse negative, and the paired sign follows."""
    rng = np.random.default_rng(7)
    n, days = 60, 14
    frames = []
    for d in range(days):
        y = rng.normal(size=n)
        frames.append(pd.DataFrame({"day": f"2026-10-{28 + d - (31 if d > 3 else 0):02d}" if d <= 3 else f"2026-11-{d - 3:02d}",
                                    "product_id": [f"P{i}-USD" for i in range(n)], "direction": "up",
                                    "pct_1m": y + rng.normal(scale=2.0, size=n), "pct_3m": rng.normal(size=n),
                                    "vol": rng.normal(size=n), "live_score": 50 - 5 * y + rng.normal(scale=10, size=n),
                                    "start_change_pct": rng.normal(size=n), "gross_return_5m": y}))
    rows = pd.concat(frames, ignore_index=True)
    model = run.fit_ridge(rows, "gross_return_5m", 1.0, False)
    cell = fresh.score_cell(rows, "gross_return_5m", model, run.fit_ridge(rows, "gross_return_5m", 1.0, True), [0.2], run)
    assert cell["days_scored"] == days and cell["rows_on_scored_days"] == n * days
    assert cell["ic"]["B2"]["mean"] > 0 > cell["ic"]["B1"]["mean"]
    paired = cell["paired"]["B2-B1"]
    assert paired["mean"] == pytest.approx(cell["ic"]["B2"]["mean"] - cell["ic"]["B1"]["mean"])
    assert paired["iid_daily"]["lo"] < paired["mean"] < paired["iid_daily"]["hi"]
    assert fresh.decide(paired, cell["ic"]["B2"]) == "keep"
    assert cell["bands"]["B2"]["top_minus_bottom_gross_pct"] > 0 > cell["bands"]["B1"]["top_minus_bottom_gross_pct"]
