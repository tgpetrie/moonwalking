from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import app


def test_price_snapshot_computes_returns_for_cached_symbols_outside_board_rows():
    now = 1_800_000_000
    snapshot = app.mw_build_price_snapshot(
        g1m_rows=[],
        g3m_rows=[],
        l3m_rows=[],
        banner_rows=[],
        cached_prices={"AAA": 102.0, "BBB": 50.0},
        snapshot_ts_s=now,
        history_1m={
            "AAA": [(now - 60, 100.0)],
            "BBB": [(now - 60, 50.5)],
        },
        history_3m={
            "AAA": [(now - 180, 99.0)],
            "BBB": [(now - 180, 51.0)],
        },
    )

    assert round(snapshot["AAA"]["pct_1m"], 4) == 2.0
    assert round(snapshot["AAA"]["pct_3m"], 4) == round((102.0 - 99.0) / 99.0 * 100, 4)
    assert snapshot["BBB"]["pct_1m"] is not None
    assert snapshot["BBB"]["pct_3m"] is not None
    assert snapshot["AAA"]["sample_ts"] == now
