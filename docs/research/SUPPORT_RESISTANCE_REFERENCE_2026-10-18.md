# Support/resistance layer: reference and implementation boundary

Reference: [Pro Trading School, The Simple Support and Resistance Strategy That
Actually Works](https://www.youtube.com/watch?v=0-t3iy2rZFk), player length 15:01.
Reviewed its automatic English transcript and the zone illustration at 6:16.
The inspected frame is GBP/JPY, 1h, FXCM; the lesson also discusses intraday
FX examples. It is a methodological reference, not crypto performance evidence.

## Concepts established by this reference

| Video time | Concept |
|---|---|
| [1:04-2:57](https://www.youtube.com/watch?v=0-t3iy2rZFk&t=64s) | Prior swings, repeated rejection, reaction size, visibility, recency and role reversal guide level selection. |
| [5:38-6:38](https://www.youtube.com/watch?v=0-t3iy2rZFk&t=338s) | Group nearby reaction prices into an area instead of requiring identical-price touches. |
| [6:40-8:10](https://www.youtube.com/watch?v=0-t3iy2rZFk&t=400s) | Broken support may later act as resistance, and vice versa. |
| [8:13-11:30](https://www.youtube.com/watch?v=0-t3iy2rZFk&t=493s) | Break/retest examples use a closed rejection candle and higher-timeframe context. |
| [11:30-14:46](https://www.youtube.com/watch?v=0-t3iy2rZFk&t=690s) | Wick excursions followed by a close back across a level are described as sweeps. |

The narrator's sufficiency rule for criteria is a heuristic. The examples do
not establish calibrated probabilities, actual order flow or crypto returns.

## Proposed visible feature

Add a small set of horizontal support/resistance bands alongside the existing
chart map. A zone explains its source anchors, constituent confirmed reactions,
first availability, last test and current relationship to price. Reactions,
historical touches and later outcomes are distinct evidence. A future agent
can explain this record without inventing a wave count or a success rate.

Use the existing wick/body pivot and trendline foundations from `5d79177`.
The following decisions need an explicit versioned specification before a
detector is connected to the UI:

- Define the reaction endpoints and price grouping tolerance; repeated
  neighbouring candles must not count as independent rejections. Major/minor
  degree and zone width are exposed research parameters, not earned constants.
- Freeze a zone when it first becomes available. Later widening or merging
  produces a new version; it must not retroactively rescue an earlier setup.
- Count a closed break separately from a wick excursion. Require a later
  completed bar for a retest; do not infer break-before-retest ordering inside
  a single OHLC candle.
- A change from support to resistance needs observed break/retest evidence;
  two similarly priced pivots alone are insufficient.
- Describe a sweep-shaped wick/reclaim as an OHLC pattern. Actual stop orders,
  liquidation or trader intent are not observable from these candles alone.
- Align context using only higher-timeframe bars closed by the analysis cutoff.
  Do not copy an intraday FX signal onto daily/weekly crypto data without a
  separate definition and evaluation.

Acceptance checks: prefix replay and future-price poisoning; availability after
pivot confirmation; repeat-touch independence; gap and ambiguous intrabar
handling; fixed bounds and revision history; wick-only versus closed breaks;
later-bar retest confirmation; and context-bar alignment. Predictive claims
would additionally require independent historical evaluation and costs.

## Relationship to FET and the latest pasted review

An announced point such as FET $0.145 can be retained as a reference while an
accumulation area has different, explicitly defined bounds. The video supports
this distinction. It does not supply the missing bounds of the FET box, so the
software must not silently broaden that box after seeing July's prices.

The pasted Gemini response still discloses that it could not inspect either
FET source video or transcript. It repeats the previously corrected E-direction
and duration errors; see [the earlier audit](FET_GEMINI_REVIEW_AUDIT_2026-10-18.md).
Its new $0.1191/October stop-out discussion lacks a source-matched timestamp,
entry and stop definition and is not part of the verified FET outcome record.
Its revised reversal thresholds and breach tolerances remain proposals.

No detector, UI, wave classifier, threshold or production behavior changed in
this source-review checkpoint. The existing 490-test verification remains the
last code check; no suite rerun was needed for this Markdown-only addition.
Raw transcript and screenshot remain local review artifacts.
