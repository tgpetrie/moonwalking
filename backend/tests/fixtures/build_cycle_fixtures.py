"""Rebuild the deterministic three-year cycle fixtures.

Run ``python backend/tests/fixtures/build_cycle_fixtures.py`` to rewrite the
JSON files next to this script. Nothing here is random: each series is a
piecewise log-linear path with a fixed sine texture, so the output is
byte-identical on every run.

The shapes are synthetic. They are named for the chart each one imitates and
do not contain market data.

- ``render_cycle_fixture.json``: a three-leg 5-3-5 decline that takes up the
  whole window, 18+ bearish months, and a daily MACD line kissing its signal
  from below on the last bar.
- ``fet_channel_fixture.json``: a five-leg A-B-C-D-E channel whose E low
  retests the C low with a small overthrow, then turns up.
- ``theta_wxy_confluence_fixture.json``: an advance off a base, then a
  W-X-Y decline back into it with one flash wick on the way down. The Wave X
  high is placed so its 1.618 extension lands on the 0.786 retracement.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path

DAY = 86400
BARS = 1096
LAST_TS = int(datetime(2026, 11, 15, tzinfo=timezone.utc).timestamp())
HERE = Path(__file__).resolve().parent


def path(start: float, legs: list[tuple[int, float]]) -> list[float]:
    """Daily closes along straight lines in log price. ``legs`` are (days, end)."""
    closes, price = [], start
    for days, end in legs:
        for step in range(1, days + 1):
            closes.append(price * (end / price) ** (step / days))
        price = end
    assert len(closes) == BARS, len(closes)
    return closes


def candles(
    closes: list[float],
    *,
    texture: float = 0.008,
    wick: float = 0.012,
    calm_tail: int = 0,
    calm: float = 0.25,
) -> list[list[float]]:
    """Coinbase-shaped bars ``[ts, low, high, open, close, volume]``, oldest first.

    The last ``calm_tail`` bars carry only ``calm`` of the texture, so the
    closing signal a fixture is built around rests on its path, not on the
    phase of the sine.
    """
    shaped = []
    for i, close in enumerate(closes):
        scale = calm if i >= len(closes) - calm_tail else 1.0
        wobble = texture * scale * (math.sin(i * 0.9) + 0.6 * math.sin(i * 0.23 + 1.0))
        shaped.append(close * (1.0 + wobble))
    out = []
    for i, close in enumerate(shaped):
        open_ = shaped[i - 1] if i else close / 1.002
        reach = wick * (1.0 + 0.4 * math.sin(i * 1.7))
        low = min(open_, close) * (1.0 - reach)
        high = max(open_, close) * (1.0 + reach)
        volume = 1_000_000.0 * (1.0 + 0.3 * math.sin(i * 0.11))
        ts = LAST_TS - (len(shaped) - 1 - i) * DAY
        out.append(
            [ts, round(low, 6), round(high, 6), round(open_, 6), round(close, 6), round(volume, 2)]
        )
    return out


def render(tail: int = 9, lift: float = 1.01, dip: float = 1.7) -> dict:
    stair = [
        (10, 3.45),  # a bounce, so the stair starts from a marked high
        (24, 2.45),
        (10, 2.8),
        (24, 2.0),
        (10, 2.32),
        (18, 1.62),  # the low
        (48, 1.86),  # a slow turn through two monthly closes
        (12, dip),  # a shallow pullback
        (tail, dip * lift),  # flattening
    ]
    used = 30 + 300 + 120 + sum(days for days, _ in stair)
    closes = path(
        11.0,
        [
            (30, 13.0),  # the cycle high, early in the window
            (300, 4.0),  # leg A
            (120, 6.4),  # leg B
            (BARS - used, 3.0),  # leg C, first part
            *stair,  # the last stretch of C, in a five-step stair
        ],
    )
    return {
        "name": "render_cycle_fixture",
        "product_id": "RENDER-USD",
        "shape": "5-3-5 decline, 18+ bearish months, daily MACD kiss",
        "candles": candles(closes, calm_tail=tail + 60),
    }


def fet(tail: int = 6, lift: float = 1.03) -> dict:
    late = [
        (150, 0.8),  # E, first part
        (14, 0.87),  # a bounce that leaves a swing high above price
        (70, 0.615),  # E speeds up into the C low
        (tail, 0.615 * lift),  # turning up
    ]
    used = 135 + 165 + 120 + 190 + 150 + sum(days for days, _ in late)
    closes = path(
        0.4,
        [
            (BARS - used + 135, 3.4),  # advance to the cycle high
            (165, 0.665),  # A
            (120, 1.6),  # B
            (190, 0.64),  # C
            (150, 1.15),  # D
            *late,
        ],
    )
    bars = candles(closes, calm_tail=tail + 20)
    # A brief dip through the channel line that closes back above it.
    dip = bars[-tail - 1]
    dip[1] = round(dip[1] * 0.975, 6)
    return {
        "name": "fet_channel_fixture",
        "product_id": "FET-USD",
        "shape": "A-B-C-D-E channel, double bottom at C and E, weekly StochRSI turn-up",
        "candles": bars,
    }


def theta(tail: int = 30) -> dict:
    late = [
        (290, 0.96),  # Y, first part
        (16, 1.05),  # a bounce that leaves a swing high above price
        (110, 0.76),  # Y, back into the base
        (tail, 0.8),  # turning up
    ]
    used = 90 + 120 + 240 + 150 + sum(days for days, _ in late)
    closes = path(
        0.92,
        [
            (90 + BARS - used, 0.9),  # the base
            (120, 3.7),  # advance to the cycle high
            (240, 1.06),  # W
            (150, 1.6),  # X
            *late,
        ],
    )
    bars = candles(closes, calm_tail=tail)
    # One flash wick on the way down: a single bar trades far below its body
    # and closes back where it opened.
    flash = bars[-140]
    flash[1] = round(min(flash[3], flash[4]) * 0.3, 6)
    return {
        "name": "theta_wxy_confluence_fixture",
        "product_id": "THETA-USD",
        "shape": "W-X-Y decline into the base, one flash wick, dual-grid confluence",
        "flash_wick_timestamp": flash[0],
        "candles": bars,
    }


def main() -> None:
    for build in (render, fet, theta):
        fixture = build()
        fixture["bars"] = len(fixture["candles"])
        fixture["order"] = "oldest first; [time, low, high, open, close, volume]"
        fixture["synthetic"] = True
        target = HERE / f"{fixture['name']}.json"
        target.write_text(json.dumps(fixture, separators=(",", ":")) + "\n", encoding="utf-8")
        print(target.name, fixture["bars"])


if __name__ == "__main__":
    main()
