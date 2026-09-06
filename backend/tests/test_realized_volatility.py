"""Volatility must not overstate sparsely-sampled coins.

A pair of closes three minutes apart is a three-minute return. Treating it as
a one-minute return and scaling the series by sqrt(60) inflates exactly the
coins with gappy tapes — which would then be matched as peers against
densely-sampled coins of genuinely different volatility.
"""

from __future__ import annotations

import importlib
import math

import pytest


@pytest.fixture()
def price_db(tmp_path, monkeypatch):
    monkeypatch.setenv("MOONWALKING_PRICE_DB", str(tmp_path / "prices.db"))
    import price_db as module

    importlib.reload(module)
    module.ensure_price_db()
    return module


def _fill(module, symbol, start_ts, prices, *, step=60):
    for i, price in enumerate(prices):
        module.insert_price_snapshot(start_ts + i * step, [(symbol, price)])


def test_gap_pairs_are_excluded_from_returns(price_db):
    now = 1_700_003_600
    start = now - 3600
    # 60 consecutive minutes of a steadily oscillating series.
    prices = [100.0 + (1.0 if i % 2 else -1.0) for i in range(60)]
    _fill(price_db, "DENSE", start, prices)

    result = price_db.realized_volatility_by_product(now)["DENSE"]
    assert result["volatility_pct_hour"] is not None
    assert result["skipped_gap_pairs"] == 0
    assert result["consecutive_returns"] == 58


def test_sparse_series_is_refused_rather_than_scaled(price_db):
    now = 1_700_003_600
    start = now - 3600
    # 50 observations but every one 3 minutes apart: enough raw observations to
    # pass the old count check, no consecutive pairs at all.
    for i in range(50):
        price_db.insert_price_snapshot(
            start + i * 180, [("SPARSE", 100.0 + (2.0 if i % 2 else -2.0))]
        )

    result = price_db.realized_volatility_by_product(now)["SPARSE"]
    assert result["volatility_pct_hour"] is None
    assert result["reason"] in (
        "insufficient_observations",
        "insufficient_consecutive_returns",
        "gap_exceeded",
    )
    assert result["consecutive_returns"] == 0


def test_unavailable_is_distinguishable_from_low_volatility(price_db):
    now = 1_700_003_600
    start = now - 3600
    _fill(price_db, "FLAT", start, [100.0] * 60)
    price_db.insert_price_snapshot(start + 60, [("THIN", 100.0)])

    results = price_db.realized_volatility_by_product(now)
    # A genuinely flat coin has zero volatility and no reason.
    assert results["FLAT"]["volatility_pct_hour"] == 0.0
    assert results["FLAT"]["reason"] is None
    # A coin without data has no volatility and a reason saying why.
    assert results["THIN"]["volatility_pct_hour"] is None
    assert results["THIN"]["reason"] == "insufficient_observations"


def test_duplicate_key_forms_do_not_split_a_symbol(price_db):
    """The tape carries both "AAVE" and "AAVE-USD"; keep the denser series."""
    now = 1_700_003_600
    start = now - 3600
    _fill(price_db, "AAVE", start, [100.0 + (i % 3) for i in range(60)])
    price_db.insert_price_snapshot(start, [("AAVE-USD", 100.0)])

    results = price_db.realized_volatility_by_product(now)
    assert "AAVE-USD" not in results
    assert results["AAVE"]["volatility_pct_hour"] is not None
    assert results["AAVE"]["observations"] == 59
