# FET: preserve the call, then evaluate its development

## Finding

The opportunity level was identified in advance and retained in the update.
This is a useful reference for the product behavior Tom wants: map a potential
area first, then recognize when price approaches it. A successful rebound or
completed trade is not established by the reviewed material.

| Source | Evidence |
|---|---|
| [June 26 video, 3:21-3:28](https://www.youtube.com/watch?v=M2yA9fJ_5j8&t=201s) | Opportunity/support at $0.145, with a weekly ascending-channel interpretation. |
| [July 23 video, 0:14-0:49](https://www.youtube.com/watch?v=LS93M0qDZ4I&t=14s) | Repeats $0.145 and describes price near $0.15 approaching the area. |
| [July frame at 0:31](https://www.youtube.com/watch?v=LS93M0qDZ4I&t=31s) | Displayed quote about $0.15351, roughly 5.9% above the stated point. The roughly $0.14446 label is the cursor coordinate, not evidence of a trade there. |

Upload dates displayed by YouTube are 27 calendar days apart. Publication and
recording timestamps are unknown. Review used both automatic transcripts and
selected chart frames (June 3:27; July 0:31), not a complete visual audit.

## What stays consistent, and what changes

Both frames identify weekly FET/USD with a `CRYPTO` provider label. The analyst
retains the broad channel/ABCDE interpretation and the opportunity level.
Exact channel endpoints and green-box bounds remain unverified; similar-looking
drawings do not establish unchanged mathematical trendlines.

June's resistance is spoken approximately as $0.30-$0.305, followed by a
conditional $0.80 level ([3:45-4:05](https://www.youtube.com/watch?v=M2yA9fJ_5j8&t=225s)).
July describes conditional ranges of $1.80-$2.75 and $5.50-$6.50
([1:58-2:13](https://www.youtube.com/watch?v=LS93M0qDZ4I&t=118s)); June's
headline macro projection is about $7. The ambiguous upper bound in June's
automatic caption near 5:18 is preserved as unknown. July adds optional stop
placement below an indicated low, without a verified numeric stop.
These are the analyst's scenarios, not measured probabilities.

## Fixed reference for implementation

[FET_VIDEO_PAIR_V1.json](references/FET_VIDEO_PAIR_V1.json) stores the original
and follow-up separately, with timestamps, uncertainty and null outcomes.
Later details must not fill gaps in the original call. The file is analyst
evidence, not a candle fixture, an engine prediction or an executable order.

Calculation baseline remains `e1b7e53`. No parameters or chart code were changed.
The engine supports daily-to-weekly aggregation, confirmed wick pivots,
three-anchor geometry, logarithmic/linear display and replay. It does not yet
derive this analyst's macro ABCDE channel or the $0.145 level automatically.
At the initial reference freeze (`d2d055a`), no FET candle replay had been run.
The frozen JSON's `engine_comparison` describes that first pass. The subsequent
independent venue check below does not alter its original call or fill unknowns.

The next implementation requires a verified FET instrument/history export and
explicit channel-anchor conventions. Claude owns that acquisition; Gemini is
reviewing those conventions. Codex can then replay each date using closed bars
and the existing settings, reporting matches and disagreements. Date-only uploads
cannot establish intraday ordering: use full prior UTC days or document the
publication-time assumption.

Future records should distinguish: identified area, approaching area, observed
touch, support response, invalidation and measured outcome. A point level is
not a numeric entry range; a cursor coordinate is not a fill. Targets and risk
remain ungraded until source-matched prices and evaluation rules are available.

## Initial reference checks and scope

Reference JSON syntax, source IDs, chronological ordering, repeated-level
consistency and the 27-day/5.9% calculations were checked locally. No frontend
change required a test-suite rerun. Browser frames and complete transcripts stay
in local temporary/ignored output; only the structured reference and this report
are committed. No market requests, account access, database access, production
changes, branch consolidation or deployment were performed in that first pass.

## Independent Coinbase replay, added after freezing the reference

`snapshot_coinbase_daily.py` obtained a separate FET-USD snapshot with eight
unauthenticated public GET requests, at least 1.05 seconds apart. Requested
interval: 2021-01-01 through 2026-07-24 exclusive. Actual observed coverage:
2021-07-27 through 2026-07-23, 1,823 daily candles, no gaps inside that span.
No 2020 coverage or token migration lineage was established. Prices, raw
responses and request hashes are retained only in ignored local output.

Source behavior and bucket fields follow Coinbase's
[candle endpoint documentation](https://docs.cdp.coinbase.com/api-reference/exchange-api/rest-api/products/get-product-candles).
Requests use an explicit product validated against
[product metadata](https://docs.cdp.coinbase.com/api-reference/exchange-api/rest-api/products/get-single-product),
bounded 299-day windows, boundary deduplication and strict OHLCV validation.
HTTP failures abort instead of masquerading as empty periods. Missing bars are
never interpolated. This is a Coinbase venue product, not verified parity with
the video's `CRYPTO` series.

Run the unchanged `e1b7e53` calculation engine with two completed weekly bars
on either side and latest alternating anchors:

| Exclusive UTC cutoff | Completed weeks | Last completed weekly close | Default scenario |
|---|---:|---:|---|
| 2026-06-26 | 255 | $0.1793 | Withheld: latest triple fails correction geometry |
| 2026-07-23 | 259 | $0.1567 | Withheld: same triple fails correction geometry |

Both default triples are March 25 high $0.2693, May 17 low $0.1843 and June 1
high $0.2884. The rebound exceeds A, so the three-anchor decline/rebound rule
does not qualify. Searching older triples or changing thresholds to fit the
video was not performed. The engine is missing the analyst's multi-scale
channel/ABCDE interpretation, rather than independently confirming $0.145.

All 259 completed weekly cutoffs passed prefix candle/pivot consistency checks.
For the explicitly assumed date-only UTC comparison window June 27 through
July 22 inclusive, all 26 daily bars are present. Lowest low: $0.1502; no daily
range contains the exact $0.145 point. These dates are calendar conventions,
not verified publication timestamps. This supports approach toward the point
on this venue; it does not grade an unspecified-width accumulation area,
an intraday fill, subsequent rebound or profitable trade.

Snapshot SHA-256:
`6cfed7c82b077af72c30af8dcd82ff819357a8e5eac7873101c0840ebe25cc31`.
Reproduce the replay without further network requests:

```powershell
node scripts/replay_video_reference.mjs docs/research/references/FET_VIDEO_PAIR_V1.json <history.json>
python scripts/preview_macro_chart.py --input <history.json>
```

The second-coin preview uses the existing UI and calculations. The preview
helper now titles the tab from its actual coin and uses versioned filenames
to preserve existing preview artifacts. This remains a research snapshot,
not a live coin-search service or reproduction of the full analyst method.

Six offline Python checks pass (snapshot boundaries/conflicts/OHLCV/gaps,
preview symbol/title escaping/inert JSON and overwrite protection). The real
snapshot passes all 259 prefix checks; response hashes were rechecked against
their saved bytes. Repository guardrails and diff whitespace checks pass.
Browser checks confirm both replay dates, the withheld-scenario state, no
page overflow and an empty browser error log. Frontend calculation/UI files
remain unchanged from `e1b7e53`; their previously passing 474 tests were not
rerun for these research scripts. Main and production remain unchanged.
