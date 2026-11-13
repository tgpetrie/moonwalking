"""Synthetic checks for the runner signal screen. No market data."""
import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("screen", ROOT / "scripts/scoring_experiment/screen_runner_signals.py")
screen = importlib.util.module_from_spec(spec)
spec.loader.exec_module(screen)


def frame(rows):
    base = {"id": 0, "board": "confirmation_3m_up", "product_id": "AAA-USD", "direction": "up", "entered_ts": 0,
            "phase": "test", "start_change_pct": 1.0, "pct_1m": 0.4, "pct_3m": 1.0, "vol": 10.0, "liquidity": "normal",
            "trend_streak": 2.0, "bull": 0.0, "bear": 0.0, "r5": 0.0, "r15": 0.0, "r30": 0.0, "fav15": 0.0, "adv15": 0.0}
    return pd.DataFrame([{**base, **r} for r in rows])


def test_runner_and_crasher_definitions():
    df = frame([
        {"id": 1, "r5": 0.6, "r15": 1.2, "fav15": 1.7, "r30": 1.4},     # staircase runner
        {"id": 2, "r5": 0.4, "r15": 1.15, "fav15": 1.15, "r30": 1.65},  # rescued by 30m
        {"id": 3, "r5": -0.5, "r15": -1.5, "fav15": 2.5, "r30": -1.8},  # wick then dump: crasher, not runner
        {"id": 4, "r5": -6.0, "r15": 1.6, "fav15": 1.6, "r30": 1.1},    # early collapse: neither
        {"id": 5, "r5": 0.5, "r15": -1.2, "adv15": -1.6, "r30": -1.0},  # 5m at +0.5 blocks crasher
    ])
    out = screen.add_signals(df, df[["id", "board", "product_id", "direction", "entered_ts"]])
    assert out["runner"].tolist() == [1, 1, 0, 0, 0]
    assert out["crasher"].tolist() == [0, 0, 1, 0, 0]


def test_history_windows():
    rows = [
        {"id": 1, "board": "confirmation_3m_up", "entered_ts": 10_000},
        {"id": 2, "board": "ignition_1m", "entered_ts": 10_150},          # other board within 180s
        {"id": 3, "board": "confirmation_3m_up", "entered_ts": 10_000 + 21_000},
        {"id": 4, "board": "confirmation_3m_up", "product_id": "BBB-USD", "entered_ts": 10_030},
    ]
    df = frame(rows)
    out = screen.add_signals(df, df[["id", "board", "product_id", "direction", "entered_ts"]])
    by = out.set_index("id")
    assert by.loc[1, "simultaneous"] == 1 and by.loc[2, "simultaneous"] == 1 and by.loc[3, "simultaneous"] == 0
    assert by.loc[1, "repeat_6h"] == 0 and by.loc[2, "repeat_6h"] == 1 and by.loc[3, "repeat_6h"] == 2
    assert by.loc[4, "W60"] == 2 and by.loc[1, "W60"] == 1   # same board+direction in [t-60, t], self included


def test_flag_ties_break_by_b0_then_id():
    g = pd.DataFrame({"id": [3, 1, 2, 4], "sig": [1.0, 1.0, 1.0, 0.0], "B0": [0.5, 0.5, 0.9, 2.0]})
    assert list(g.loc[screen.flagged(g, "sig", 2), "id"]) == [2, 1]


def test_daily_requires_rows_and_runners():
    n = 40
    df = frame([{"id": i, "entered_ts": i, "start_change_pct": float(i), "r5": 0.1, "r15": 1.2 if i % 10 == 0 else 0.0,
                 "fav15": 1.6 if i % 10 == 0 else 0.0, "r30": 1.6 if i % 10 == 0 else 0.0} for i in range(n)])
    out = screen.add_signals(df, df[["id", "board", "product_id", "direction", "entered_ts"]])
    days = screen.daily(out)
    assert len(days) == 1 and days.loc[0, "k"] == 10 and np.isclose(days.loc[0, "X"], 4 / 40)
    assert np.isclose(days.loc[0, "Y_B0"], 1 / 10)   # top 10 by B0 are ids 30..39; only id 30 runs
