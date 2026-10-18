"""Compare the chart-methodology review's video readings with Coinbase weekly data.

The reference values come from "RENDER Chart Methodology Review" (a Gemini
review of macro render.mp4, Google Doc 10NPIyzl...). They are
transcriptions of a TradingView chart, not exchange data, and that review's
bar dates are not reliable. So each reference bar is matched to the closest
Coinbase week instead of trusting its stated date.

Also writes a weekly indicator fixture (SMA, MACD, Stoch RSI) computed on
the unstitched RENDER-USD closes, for Codex's indicator parity tests.

  python scripts/render_history/reference_parity.py --data data/render-history
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

REVIEW = "RENDER Chart Methodology Review (Gemini, Google Doc 10NPIyzlQW7y7uZtIFzR0MTg2yjnbOebk0fjBRCGfXUU)"

# (label, date the review gives, O, H, L, C); None where the review gave no number.
REFERENCE_BARS = [
    ("macro peak (0)", "2024-03-11", 9.8118, 13.6352, 9.5931, 12.6952),
    ("wave (A) low", "2024-08-05", 4.8265, 5.2071, 3.3982, 4.6800),
    ("wave (B) peak", "2024-12-02", 8.8678, 11.9056, 8.1182, 9.6080),
    ("wave (C)(2) high", "2025-05-12", 5.2075, 5.5111, 4.3706, 4.6812),
    ("wave (C)(5) low", "2026-02-02", 1.4958, 1.5698, 1.1238, 1.3498),
    ("local wave (2) low", "2026-08-17", 1.3567, 1.5198, 1.2455, 1.5130),
    ("bar open at recording", "2026-10-12", 1.9750, 2.1995, 1.7609, 1.9960),
]
# Values the review reports without a full OHLC; compared against the stated week only.
REFERENCE_POINTS = [
    ("wave (C)(1) low", "2025-04-07", "l", 2.50),
    ("wave (C)(3) liquidation wick", "2025-10-06", "l", 0.85),
    ("wave (C)(4) high", "2026-01-05", "h", 2.65),
    ("local wave (5) high", "2026-05-11", "h", 2.4395),
]
REFERENCE_INDICATORS = {
    "sma50": 1.6998, "sma100": 3.1332, "sma200": 3.7009,
    "macd": -0.0018, "macd_signal": -0.0995, "macd_hist": 0.0977,
    "stoch_k_range": [93.26, 94.46], "stoch_d_range": [90.06, 98.68],
    "note": "sma200 is 3.5251 in the review's first pass and 3.7009 in its second; Stoch RSI is given as ranges",
}


def load(data: Path, product: str) -> list[dict]:
    return json.loads((data / "weekly" / f"coinbase_{product}_1w.json").read_text(encoding="utf-8"))["candles"]


def rel(a: float, b: float) -> float:
    return round((a / b - 1) * 100, 3)


# ---- indicators (TradingView Pine v5 conventions as documented) ---------

def sma(x: list[float], n: int, i: int) -> float | None:
    return sum(x[i - n + 1 : i + 1]) / n if i >= n - 1 else None


def ema(x: list[float], n: int) -> list[float]:
    """Pine's documented ta.ema: alpha = 2/(n+1), seeded with the first value."""
    a, out = 2 / (n + 1), []
    for v in x:
        out.append(v if not out else a * v + (1 - a) * out[-1])
    return out


def rma(x: list[float], n: int) -> list[float | None]:
    """Pine's ta.rma (Wilder): seeded with the SMA of the first n values."""
    out: list[float | None] = []
    for i, v in enumerate(x):
        if i < n - 1:
            out.append(None)
        elif out[-1] is None:
            out.append(sum(x[: n]) / n)
        else:
            out.append((out[-1] * (n - 1) + v) / n)
    return out


def indicators(closes: list[float]) -> list[dict]:
    fast, slow = ema(closes, 12), ema(closes, 26)
    macd = [f - s for f, s in zip(fast, slow)]
    signal = ema(macd, 9)
    ch = [0.0] + [closes[i] - closes[i - 1] for i in range(1, len(closes))]
    up = rma([max(c, 0) for c in ch[1:]], 14)
    dn = rma([max(-c, 0) for c in ch[1:]], 14)
    rsi: list[float | None] = [None] + [
        None if u is None else (100.0 if d == 0 else 100 - 100 / (1 + u / d)) for u, d in zip(up, dn)
    ]
    stoch: list[float | None] = []
    for i in range(len(closes)):
        win = rsi[i - 13 : i + 1] if i >= 13 else []
        if len(win) < 14 or any(v is None for v in win):
            stoch.append(None)
            continue
        lo, hi = min(win), max(win)
        stoch.append(100 * (rsi[i] - lo) / (hi - lo) if hi > lo else 0.0)

    def sma_opt(x: list[float | None], n: int, i: int) -> float | None:
        w = x[i - n + 1 : i + 1] if i >= n - 1 else []
        return sum(w) / n if len(w) == n and all(v is not None for v in w) else None

    k = [sma_opt(stoch, 3, i) for i in range(len(closes))]
    d = [sma_opt(k, 3, i) for i in range(len(closes))]
    rows = []
    for i in range(len(closes)):
        rows.append(
            {
                "close": closes[i],
                "sma50": sma(closes, 50, i), "sma100": sma(closes, 100, i), "sma200": sma(closes, 200, i),
                "macd": macd[i], "macd_signal": signal[i], "macd_hist": macd[i] - signal[i],
                "rsi14": rsi[i], "stoch_k": k[i], "stoch_d": d[i],
            }
        )
    return rows


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", required=True)
    args = ap.parse_args()
    data = Path(args.data)
    render, rndr = load(data, "RENDER-USD"), load(data, "RNDR-USD")
    by_week = {c["t"][:10]: c for c in render}

    bars = []
    for label, stated, o, h, l, c in REFERENCE_BARS:
        best = min(render, key=lambda w: sum(abs(a / b - 1) for a, b in zip((w["o"], w["h"], w["l"], w["c"]), (o, h, l, c))))
        stated_bar = by_week.get(stated)
        bars.append(
            {
                "label": label,
                "review_date": stated,
                "review_ohlc": [o, h, l, c],
                "closest_coinbase_week": best["t"][:10],
                "closest_week_matches_review_date": best["t"][:10] == stated,
                "coinbase_ohlc": [best["o"], best["h"], best["l"], best["c"]],
                "diff_pct_ohlc": [rel(best[k], v) for k, v in zip("ohlc", (o, h, l, c))],
                "coinbase_week_complete": best["complete"],
                "stated_week_diff_pct_ohlc": [rel(stated_bar[k], v) for k, v in zip("ohlc", (o, h, l, c))] if stated_bar else None,
            }
        )
    points = []
    for label, stated, field, value in REFERENCE_POINTS:
        w = by_week.get(stated)
        points.append({"label": label, "review_date": stated, "field": field, "review_value": value,
                       "coinbase_value": w[field] if w else None, "diff_pct": rel(w[field], value) if w else None})

    # Indicators on the bar the review read them from: its "current bar" is
    # the closest Coinbase week to the reference bar open at recording.
    rec_week = bars[-1]["closest_coinbase_week"]
    closes = [c["c"] for c in render if c["complete"] and c["t"][:10] <= rec_week]
    ind_render = indicators(closes)[-1]
    # Comparison only, never published as data: what a RNDR->RENDER join would give.
    first_full = next(c["t"][:10] for c in render if c["complete"])
    joined = [c["c"] for c in rndr if c["t"][:10] < first_full] + closes
    ind_joined = indicators(joined)[-1]

    closed = [c for c in render if c["complete"]]
    fixture_rows = indicators([c["c"] for c in closed])
    fixture = [{"t": c["t"], **r} for c, r in zip(closed, fixture_rows)][-100:]

    out = {
        "source_of_reference": REVIEW,
        "reference_is": "values a reviewer read off a TradingView chart in the video; unverified, venue unknown",
        "bars": bars,
        "points": points,
        "indicators_at_recording_bar": {
            "bar": rec_week,
            "bar_note": "the week whose OHLC matches the review's 'current bar'; the review dated it a week later",
            "reference": REFERENCE_INDICATORS,
            "coinbase_render_usd_only": {**ind_render, "weeks_available": len(closes)},
            "comparison_only_rndr_then_render": {
                **ind_joined, "weeks_available": len(joined),
                "warning": "RNDR-USD closes before the first full RENDER-USD week, then RENDER-USD. Not published as a series; shown only to explain the reference SMA200.",
            },
        },
        "indicator_fixture": {
            "series_id": "coinbase-exchange:RENDER-USD:1w",
            "conventions": {
                "input": "weekly close of complete weeks only (the partial first week and the open current week are excluded)",
                "sma": "arithmetic mean of last N closes; null until N bars exist",
                "ema": "alpha 2/(N+1), seeded with the first value (Pine v5 ta.ema reference example); TradingView's built-in warm-up may differ in the first ~N bars",
                "macd": "EMA12 - EMA26, signal EMA9 of MACD, hist = MACD - signal",
                "rsi": "Wilder RMA, seeded with SMA of first 14 changes",
                "stoch_rsi": "Stoch of RSI14 over 14 bars, %K = SMA3, %D = SMA3 of %K",
            },
            "rows": fixture,
        },
    }
    (data / "reference_parity.json").write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8", newline="\n")
    for b in bars:
        print(b["label"], b["review_date"], "->", b["closest_coinbase_week"], b["diff_pct_ohlc"])
    for p in points:
        print(p["label"], p["review_date"], p["field"], p["review_value"], "->", p["coinbase_value"], p["diff_pct"])
    print("render-only", {k: (round(v, 4) if isinstance(v, float) else v) for k, v in ind_render.items()})
    print("joined", {k: (round(v, 4) if isinstance(v, float) else v) for k, v in ind_joined.items() if k != "warning"})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
