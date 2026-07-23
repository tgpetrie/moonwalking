import asyncio
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import derivatives_positioning as dp


def test_classify_funding_buckets():
    assert dp.classify_funding(None) == ("unknown", "Unknown")
    assert dp.classify_funding(0.0)[0] == "neutral"
    # ~44%/yr positive -> crowded longs
    assert dp.classify_funding(0.00005)[0] == "crowded_long"
    # small positive -> longs paying
    assert dp.classify_funding(0.000005)[0] == "long"
    # negative -> shorts paying
    assert dp.classify_funding(-0.00005)[0] == "crowded_short"


def test_oi_price_read_quadrants():
    # OI history present -> OI x price read
    assert dp.positioning_read(5.0, 1e-5, 18.0) == (
        "OI rising with price — new money, conviction",
        "favorable",
    )
    assert dp.positioning_read(5.0, 1e-5, -9.0)[1] == "caution"
    assert dp.positioning_read(-5.0, 1e-5, 12.0)[1] == "adverse"
    assert dp.positioning_read(-5.0, 1e-5, -12.0)[1] == "neutral"


def test_funding_price_read_fallback_when_no_oi_history():
    # Rally with crowded longs -> caution
    assert dp.positioning_read(5.0, 1e-4, None)[1] == "caution"
    # Dip with shorts paying -> squeeze fuel (favorable)
    assert dp.positioning_read(-5.0, -1e-4, None)[1] == "favorable"


def test_oi_change_needs_min_span():
    dp._OI_HISTORY.clear()
    now = datetime.now(timezone.utc)
    # two samples only 1 minute apart -> below min span -> no change reported
    dp._OI_HISTORY["FOO"] = [(now - timedelta(minutes=1), 100.0), (now, 130.0)]
    assert dp._oi_change("FOO") is None
    # spaced ≥ min span -> reports +30% over the span
    dp._OI_HISTORY["FOO"] = [(now - timedelta(hours=3), 100.0), (now, 130.0)]
    pct, span_hours = dp._oi_change("FOO")
    assert pct == 30.0
    assert span_hours == 3.0


def test_get_symbol_positioning_shape_and_missing(monkeypatch):
    dp._OI_HISTORY.clear()

    async def fake_ctxs():
        return {"SOL": {"funding": "0.00001", "openInterest": "1000", "markPx": "180"}}

    monkeypatch.setattr(dp, "_fetch_hyperliquid_ctxs", fake_ctxs)

    res = asyncio.run(dp.get_symbol_positioning("sol", price_change_pct=4.2))
    assert res["available"] is True
    assert res["base_asset"] == "SOL"
    assert res["venue"] == "hyperliquid"
    assert res["open_interest"] == 1000.0
    assert res["open_interest_usd"] == 180000.0
    assert res["read"]  # non-empty read string
    # first fetch has a single OI sample, so no OI change yet
    assert res["oi_change_pct"] is None

    # a coin with no Hyperliquid perp -> None
    assert asyncio.run(dp.get_symbol_positioning("ZZZ")) is None
