"""Compare bars read from the reference video with Coinbase weekly candles.

The readings below were transcribed by Claude from frames of
`macro render.mp4` (5:23, extracted at 1 frame per second with ffmpeg). The
chart is TradingView "Render · 1W · CRYPTO" (an aggregated index, not a single
exchange), log price axis. While the narrator hovers a bar, the header shows
that bar's OHLC and the indicator legend shows values for that bar.

Recording time: the current weekly bar is the week of 2026-10-12, and its
countdown reads "5d 2h" throughout, so the video was recorded on
2026-10-13, roughly 21:00 to 22:00 UTC (before that week closed).

  python scripts/render_history/video_reference.py --data data/render-history
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

VIDEO = "macro render.mp4 (TradingView Render · 1W · CRYPTO)"

# week (Monday, UTC) -> (first second seen, O, H, L, C, date_shown)
# date_shown False = the date label was covered on screen and the week is inferred from the price match.
BARS = {
    "2023-09-04": (282, 1.3620, 1.5261, 1.3329, 1.4794, True),
    "2024-02-26": (225, 7.2138, 8.2878, 6.9486, 7.5636, True),
    "2024-03-04": (130, 7.5636, 12.7353, 5.8815, 11.3825, True),
    "2024-03-11": (223, 11.3823, 13.6271, 9.9340, 13.1381, True),
    "2024-03-25": (237, 10.9234, 12.0118, 10.4384, 10.6575, True),
    "2024-04-01": (3, 10.6575, 10.6882, 8.7737, 9.7663, True),
    "2024-04-08": (236, 9.7668, 10.5404, 6.2795, 8.9852, True),
    "2024-05-13": (1, 10.8176, 11.4738, 9.7685, 10.0515, True),
    "2024-05-27": (4, 9.9856, 10.6359, 9.7469, 9.9240, True),
    "2024-08-05": (240, 4.5267, 5.1221, 3.4261, 4.4820, True),
    "2024-08-12": (5, 4.4815, 4.9583, 4.3083, 4.4972, True),
    "2024-08-26": (38, 6.3179, 6.5810, 4.8046, 4.8245, True),
    "2024-09-02": (239, 4.8245, 5.2016, 4.4580, 4.8722, True),
    "2024-09-30": (238, 6.6736, 6.7828, 5.0323, 5.4336, True),
    "2024-11-04": (57, 4.4478, 5.9634, 4.1182, 5.6380, True),
    "2024-11-18": (155, 7.0863, 8.2962, 6.9773, 8.0520, True),
    "2025-02-17": (6, 4.4728, 4.6826, 3.9630, 4.1636, True),
    "2025-02-24": (232, 4.1638, 4.4700, 3.3499, 4.4242, True),
    "2025-03-24": (168, 3.4696, 4.2107, 3.3886, 3.4122, True),
    "2025-03-31": (171, 3.4125, 3.8221, 2.7181, 2.7823, True),
    "2025-04-14": (169, 3.7771, 4.4717, 3.5760, 4.3483, True),
    "2025-05-12": (8, 5.2075, 5.5111, 4.3706, 4.6812, True),
    "2025-07-28": (69, 4.3331, 4.4412, 3.3434, 3.5698, True),
    "2025-10-06": (173, 3.4844, 3.6706, 0.5454, 2.7328, False),
    "2025-10-13": (148, 2.7328, 3.0912, 2.3009, 2.5348, True),
    "2025-10-27": (2, 2.5771, 2.6264, 2.1573, 2.2915, True),
    "2025-11-03": (172, 2.2915, 2.9287, 1.7309, 2.4057, False),
    "2025-11-10": (39, 2.4056, 2.7652, 1.9606, 2.0128, True),
    "2025-12-08": (164, 1.5774, 1.7800, 1.4592, 1.4777, True),
    "2025-12-15": (7, 1.4777, 1.5291, 1.1790, 1.2719, True),
    "2025-12-29": (174, 1.3211, 2.0095, 1.2781, 1.9899, True),
    "2026-01-12": (166, 2.5801, 2.6464, 2.0703, 2.0744, True),
    "2026-01-19": (132, 2.0743, 2.1522, 1.8243, 1.8694, True),
    "2026-01-26": (165, 1.8694, 2.0054, 1.3940, 1.4958, True),
    "2026-02-02": (10, 1.4958, 1.6586, 1.1236, 1.3498, True),
    "2026-02-09": (275, 1.3495, 1.5475, 1.2335, 1.4326, True),
    "2026-02-16": (31, 1.4327, 1.5423, 1.3559, 1.4170, True),
    "2026-02-23": (40, 1.4172, 1.5517, 1.2982, 1.3387, True),
    "2026-03-02": (289, 1.3387, 1.4549, 1.3128, 1.3517, True),
    "2026-03-09": (0, 1.3517, 1.9490, 1.3507, 1.8971, True),
    "2026-03-16": (92, 1.8971, 1.9882, 1.5997, 1.6101, True),
    "2026-03-23": (152, 1.6099, 1.9105, 1.5719, 1.6512, True),
    "2026-03-30": (9, 1.6511, 1.9639, 1.6481, 1.9034, True),
    "2026-04-06": (288, 1.9034, 2.1204, 1.8463, 1.8856, True),
    "2026-04-20": (94, 1.7282, 1.8713, 1.7279, 1.8230, True),
    "2026-05-04": (147, 1.8251, 2.0839, 1.8075, 2.0152, True),
    "2026-05-11": (153, 2.0150, 2.0199, 1.7398, 1.7920, True),
    "2026-05-18": (67, 1.7919, 2.0993, 1.7316, 2.0170, True),
    "2026-05-25": (220, 2.0171, 2.4331, 1.9313, 2.0859, True),
    "2026-06-01": (46, 2.0859, 2.2661, 1.5487, 1.6798, True),
    "2026-06-22": (219, 1.6526, 1.7151, 1.4478, 1.5420, True),
    "2026-06-29": (45, 1.5416, 1.6374, 1.4692, 1.6172, True),
    "2026-08-03": (34, 1.3837, 1.3856, 1.2968, 1.2985, True),
    "2026-08-10": (113, 1.2985, 1.3106, 1.2262, 1.2547, True),
    "2026-08-17": (85, 1.2547, 1.6364, 1.2455, 1.5130, True),
    "2026-08-24": (36, 1.5130, 1.5843, 1.3828, 1.4002, True),
    "2026-09-07": (65, 1.5636, 1.6017, 1.3507, 1.3654, True),
    "2026-09-14": (41, 1.3655, 1.7561, 1.2849, 1.7320, True),
    "2026-09-21": (37, 1.7319, 2.0931, 1.6701, 2.0534, True),
    "2026-09-28": (35, 2.0534, 2.0896, 1.8602, 1.9751, True),
    "2026-10-05": (49, 1.9750, 2.1995, 1.7609, 1.9960, True),
}
# The live week of 2026-10-12, as shown at recording time (incomplete).
LIVE_BAR = {"week": "2026-10-12", "o": 1.9961, "h": 2.2258, "l": 1.9706, "c_range": [2.0322, 2.0355], "complete": False}

# Indicator legend, read off two frames (TradingView: MACD legend order is histogram, MACD, signal).
INDICATORS = {
    "2026-10-05": {"second": 86, "sma50": 1.7049, "sma100": 3.1838, "sma200": 3.6930, "stoch_k": 94.46, "stoch_d": 92.06,
                   "macd_hist": 0.0877, "macd": -0.0018, "macd_signal": -0.0895},
    "2026-10-12 (live, close 2.0322)": {"second": 104, "sma50": 1.6997, "sma100": 3.1332, "sma200": 3.7009, "stoch_k": 93.24,
                                         "stoch_d": 94.87, "macd_hist": 0.0906, "macd": 0.0238, "macd_signal": -0.0668},
}

# What the earlier Gemini review said, for the record.
GEMINI_SAID = {
    "current bar": "Mon 12 Oct '26 O1.9750 H2.1995 L1.7609 C1.9960: these are the 5 Oct bar's values",
    "macro peak": "Mon 11 Mar '24 O9.8118 H13.6352 L9.5931 C12.6952: video shows O11.3823 H13.6271 L9.9340 C13.1381",
    "wave A low": "Mon 05 Aug '24 O4.8265 H5.2071 L3.3982 C4.6800: video shows O4.5267 H5.1221 L3.4261 C4.4820",
    "Oct 2025 wick": "about 0.80 to 0.90: video shows L0.5454 (week of 2025-10-06)",
    "local wave (5) high 2.4395, 11 May '26": "the 2.43 high is the week of 2026-05-25 (H2.4331); 11 May '26 has H2.0199",
    "MACD at current bar -0.0018 / -0.0995 / hist 0.0977": "those are the 5 Oct values misread: hist 0.0877, MACD -0.0018, signal -0.0895",
}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", required=True)
    args = ap.parse_args()
    data = Path(args.data)
    weeks = {}
    for product in ("RENDER-USD", "RNDR-USD"):
        doc = json.loads((data / "weekly" / f"coinbase_{product}_1w.json").read_text(encoding="utf-8"))
        weeks[product] = {c["t"][:10]: c for c in doc["candles"]}

    rows = []
    for week, (sec, o, h, l, c, shown) in sorted(BARS.items()):
        product = "RENDER-USD" if week in weeks["RENDER-USD"] and weeks["RENDER-USD"][week]["complete"] else "RNDR-USD"
        cb = weeks[product].get(week)
        diff = None if cb is None else [round((cb[k] / v - 1) * 100, 2) for k, v in zip("ohlc", (o, h, l, c))]
        rows.append({"week": week, "video_second": sec, "date_shown_on_screen": shown, "video_ohlc": [o, h, l, c],
                     "coinbase_product": product if cb else None, "coinbase_ohlc": [cb[k] for k in "ohlc"] if cb else None,
                     "coinbase_vs_video_pct": diff})
    close_diffs = [abs(r["coinbase_vs_video_pct"][3]) for r in rows if r["coinbase_vs_video_pct"] and r["coinbase_product"] == "RENDER-USD"]
    out = {
        "source": VIDEO,
        "transcribed_by": "Claude, from 1 fps ffmpeg frames; seconds are approximate (±1 s)",
        "recorded": "2026-10-13, about 21:00 to 22:00 UTC (live week of 2026-10-12, countdown 5d 2h)",
        "chart": {"symbol": "RENDERUSD", "title": "Render · 1W · CRYPTO", "timeframe": "1W", "price_axis": "log",
                  "series_note": "TradingView's aggregated CRYPTO index; it shows bars from 2023 (RNDR era), so it joins RNDR history. Moonwalking does not."},
        "live_bar": LIVE_BAR,
        "indicators_on_screen": INDICATORS,
        "bars": rows,
        "summary": {
            "bars_read": len(rows),
            "render_usd_bars_compared": len(close_diffs),
            "median_abs_close_diff_pct": sorted(close_diffs)[len(close_diffs) // 2] if close_diffs else None,
            "max_abs_close_diff_pct": max(close_diffs) if close_diffs else None,
        },
        "gemini_review_corrections": GEMINI_SAID,
        "use": "Reference only. Not a test fixture for prices (different source); dates here are verified against the screen.",
    }
    (data / "video_reference_bars.json").write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8", newline="\n")
    for r in rows:
        print(r["week"], r["video_second"], r["coinbase_product"], r["coinbase_vs_video_pct"], "" if r["date_shown_on_screen"] else "(date inferred)")
    print(out["summary"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
