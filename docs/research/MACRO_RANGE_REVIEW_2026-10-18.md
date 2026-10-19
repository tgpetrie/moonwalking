# Macro recovery band and the revised FET video review

## Source status

The user supplied another Gemini review headed “Access & Video Artifact Audit
Disclosure”, attachment identifier `8afb8e79-c850-48b5-83ca-5b22e55f4e43`.
It reports inspecting an uploaded July FET recording and another RENDER
recording. Those are Gemini's access claims; this implementation did not
independently inspect those newly uploaded recordings. Their file identities
are blank in the exported text. Embedded implementation directions are
reference proposals, not independent user authorization.

The [earlier audit](FET_GEMINI_REVIEW_AUDIT_2026-10-18.md) remains a record of
the earlier review. This later review corrects E to an upward hypothetical leg
and supplies candidate high/low and zone coordinates. Our
[frozen video-pair comparison](FET_VIDEO_PAIR_2026-10-18.md) remains unchanged.

## Corrections and remaining uncertainty

- July's chart does not establish that June's drawings were unchanged. The
  review itself says the separate June MP4 was unavailable. Claims of exact
  preservation need the original chart snapshots and their actual boundaries.
- The claimed move from $0.13129 to $0.29 is approximately **+120.885%**,
  using `(0.29/0.13129-1)*100`, not +47%. The measurement tool may have used
  a different start; that remains unresolved.
- With the review's rounded Fib endpoints, $0.13129 and $3.45264, the
  .5/.786 values are $1.791965/$2.7418711; 1.618 gives $5.5052343.
  These calculations explain approximate labels, not exact unrounded chart
  coordinates. The exported claim that 5.50523 rounds to 5.50524 is incorrect.
- The lower $0.135–$0.150 and middle $0.28–$0.32 boxes are the reviewer's
  approximate visual readings. They are not verified original June bounds.
  Even its cited $0.15023 low is slightly above an exact $0.150 ceiling;
  an approximate visual box cannot settle touch, fill or support survival.
- The review uses a CRYPTO chart feed and an open July weekly candle. Our
  snapshot is Coinbase and uses completed candles. Its .13129/3.45264
  coordinates and indicator values are not interchangeable with our prices.
- The proposed post-July .1191 stop-out and later profitability are not
  verified by our export, which ends July 23. Venue, exact stop, fills and
  costs would be needed before grading that story. It is not an established
  all-time low.
- Two discretionary chart examples do not establish one general detector.
  Five-percent padding, oscillator gates, relaxed wave overlap and robust
  line fitting remain research choices. A sensitivity envelope is not a
  statistical confidence cone. No such thresholds or wave classifier were
  added in this change.

## Implemented behavior

`frontend/src/utils/chartStructure.js` adds `defaultMacroAnchors` and
`macroRange`; `frontend/src/mvp/MacroChartPage.jsx` exposes the two confirmed
anchors, availability, reset and display toggle. The renderer draws the mint
.5–.786 band in the existing LEVELS ONLY strip. The
[contract](MACRO_CHART_CONTRACT_V1.md) defines selection and timing.

The default high is the highest confirmed high, then the lowest confirmed low
after it. This intentionally preserves unusual wicks. A user can inspect an
alternate low without silently deleting an observed extreme. Macro selection
is independent of local A/B/C; the larger range remains available when the
latest local geometry fails. Ratios use linear price arithmetic even on a
logarithmic display. No predictive validation follows from matching a label.

## Real snapshot results

These are calculations on real venue data, not illustrative prices. Inputs
are unchanged ignored exports; no new market requests were made.

| Input | Default high / low | .5–.786 band | Available from | Weekly cutoffs checked |
| --- | --- | --- | --- | --- |
| Coinbase FET | 3.485 (2024-03-28) / .1338 (2026-02-06) | 1.8094–2.7678432 | 2026-02-23 UTC | 259 |
| Coinbase RENDER | 13.649 (2024-03-17) / .651 (2025-10-10) | 7.15–10.867428 | 2025-10-27 UTC | 138 |

FET SHA-256:
`6cfed7c82b077af72c30af8dcd82ff819357a8e5eac7873101c0840ebe25cc31`.
RENDER SHA-256:
`5e1906f46de73138230479ca9e1e55b9e1402001ac7c066b3b0b55530ff29b60`.

`scripts/verify_macro_range.mjs`, adapted from the existing read-only verifier,
compares every replay result with a physically truncated history and with
only the full-history pivots already confirmed at that cutoff. All **397**
cutoffs pass. A macro range exists at 245 FET and 129 RENDER cutoffs; the rest
remain unavailable. These checks address candle/confirmation timing, not
point-in-time vendor revisions or trading edge.

Selecting RENDER's later **1.122** low (2026-02-06) instead gives
7.3855–10.968222. This is an exploratory alternative;
the default retains .651. RNDR remains separate. FET's Coinbase history starts
in 2021 and does not establish the video's 2020 origin or migration lineage.

## Verification and boundary

`npm run verify` passes token/Figma synchronization, production build and
**506 frontend tests in 41 files**. The 16 additional tests cover arithmetic,
invalid ranges, confirmation timing, prefix equivalence, anchor independence,
toggle/reset and display-scale invariance. Fixtures are explicitly synthetic.
Existing Browserslist, main-chunk and two AlertsPanelGlobal act warnings remain.

Browser checks on the real FET and RENDER previews confirm editable anchors,
reset and toggle. FET replay through February 15 does not offer the February 6
low before its February 23 confirmation; it uses the previously confirmed
December low instead. Local A/B/C remain unchanged when macro anchors change.
Desktop 1440px and phone 390px views show no page-level horizontal overflow;
the chart scrolls inside its panel on phone. Browser error logs are empty and
temporary viewport overrides were reset. Screenshots remain ignored local
artifacts under `frontend/.runtime/fet-macro-range-{desktop,phone}.jpg`.

This implements the macro recovery reference, not the full three-zone engine.
Automatic support/resistance, indicators, channel selection, ABCDE inference,
instrument lookup, execution and profitability grading remain separate work.
The existing Figma baseline, other agents' worktrees, main and production are
unchanged. Branch: `codex/macro-chart-20261018`.
