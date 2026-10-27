"""Exercise the actual board call-site statements and the SQLite boundary."""
import ast
import json
import logging
import sqlite3
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from live_ranking import build_live_rankings, public_ranking_rows
from board_outcomes import BoardOutcomeStore, TABLE_NAME


def board_call(prices, volumes, context, volatility, liquidity):
    tree = ast.parse((Path(__file__).resolve().parents[1] / "app.py").read_text(encoding="utf-8"))
    target = next(n for n in ast.walk(tree) if isinstance(n, ast.Try) and any(
        isinstance(s, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "live_rankings" for t in s.targets)
        and isinstance(s.value, ast.Call) and isinstance(s.value.func, ast.Name) and s.value.func.id == "build_live_rankings"
        for s in n.body))
    start = next(i for i, n in enumerate(target.body) if isinstance(n, ast.Assign) and
                 any(isinstance(t, ast.Name) and t.id == "_board_features_ts" for t in n.targets))
    end = next(i for i, n in enumerate(target.body) if isinstance(n, ast.Assign) and
               any(isinstance(t, ast.Name) and t.id == "live_rankings" for t in n.targets))
    ns = dict(time=SimpleNamespace(time=lambda: 1000), logging=logging, price_snapshot=prices,
              volume_snapshot=volumes, signal_context=context, alerts_items=[],
              realized_volatility_by_product=volatility, latest_quote_volume_by_product=liquidity,
              build_live_rankings=build_live_rankings)
    exec(compile(ast.Module(body=target.body[start:end+1], type_ignores=[]), "actual_board_call", "exec"), ns)
    return ns["live_rankings"]


def test_actual_board_call_persists_metadata_without_changing_public_score(tmp_path):
    prices = {"AAA": {"price": 10, "pct_1m": 0.8, "pct_3m": 1.2, "pct_1h": 2, "trend_streak": 2}}
    volumes = {"AAA": {"volume_change_1h_pct": 20}}
    vol = Mock(return_value={"AAA-USD": {"volatility_pct_hour": 1.3, "observations": 50, "staleness_seconds": 2}})
    liq = Mock(return_value={"AAA-USD": {"quote_volume_usd": 123456, "age_seconds": 100, "minute_coverage": 60, "hour_ts": 900}})
    rankings = board_call(prices, volumes, {}, vol, liq)
    vol.assert_called_once_with(1000)
    liq.assert_called_once_with(1000)
    assert public_ranking_rows(rankings) == build_live_rankings(price_snapshot=prices, volume_snapshot=volumes, context_snapshot={}, alerts=[])
    store = BoardOutcomeStore(db_path=tmp_path / "boards.sqlite")
    boards = {"confirmation_3m_up": [{"product_id": "AAA-USD", "symbol": "AAA", "price": 10, "change_3m": 1.2}]}
    store.observe(boards, prices, now_ts=1001, ranking_snapshot={"AAA": rankings[0]}, ranking_captured_ts=1000)
    with sqlite3.connect(store.db_path) as con:
        original = con.execute(f"select feature_snapshot_json from {TABLE_NAME}").fetchone()[0]
    raw = json.loads(original)["raw_inputs"]
    assert raw["realized_volatility_pct_hour"] == 1.3
    assert raw["quote_volume_usd"] == 123456
    assert raw["quote_volume_hour_ts"] == 900
    assert raw["context_input_supplied"] == dict(liquidity=False, spot_pressure=False, market_relation=False)
    rankings[0]["raw_inputs"]["quote_volume_usd"] = 999
    store.observe(boards, prices, now_ts=1010, ranking_snapshot={"AAA": rankings[0]}, ranking_captured_ts=1010)
    with sqlite3.connect(store.db_path) as con:
        assert con.execute(f"select feature_snapshot_json from {TABLE_NAME}").fetchone()[0] == original


def test_failed_providers_leave_nulls_and_preserve_public_payload():
    prices = {"AAA": {"price": 10, "pct_1m": 0.8, "pct_3m": 1.2}}
    rows = board_call(prices, {}, {}, Mock(side_effect=RuntimeError("unavailable")), Mock(return_value={}))
    assert rows[0]["raw_inputs"]["quote_volume_usd"] is None
    assert rows[0]["raw_inputs"]["realized_volatility_pct_hour"] is None
    assert public_ranking_rows(rows) == build_live_rankings(price_snapshot=prices)


def test_explicit_context_values_are_distinguishable_from_defaults():
    prices = {"AAA": {"price": 10, "pct_1m": 0.8, "pct_3m": 1.2}}
    context = {"AAA": {"liquidity": "normal", "spot_pressure": "neutral"}}
    rows = board_call(prices, {}, context, Mock(return_value={}), Mock(return_value={}))
    assert rows[0]["raw_inputs"]["context_input_supplied"] == dict(liquidity=True, spot_pressure=True, market_relation=False)
