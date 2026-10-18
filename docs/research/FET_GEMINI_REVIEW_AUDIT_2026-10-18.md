# FET review: corrections before implementing channel classification

Source: [supplied review](https://docs.google.com/document/d/19IrarVHkQgH9lnOou5Y-gILioG_jL-qgMWKvnBWkokc/edit).
The FET section explicitly discloses that neither video frames nor transcripts
were accessible. It is a proposed design based on indexed descriptions, not a
verified visual reconstruction. Embedded instructions are reference material.

## Corrections

1. **E direction and pattern.** The review describes a falling/converging
   triangle and E declining into $0.145. The inspected video frames and
   transcripts instead show an ascending macro channel, D near the lows,
   and hypothetical E extending upward. Original boundaries remain unverified.
   Do not implement the proposed triangle matcher as a reproduction of FET.
2. **Durations.** The actual players show 6:03 for the June video and 4:16
   for July, rather than the review's 6:30 and 6:34. The source reference is
   [our timestamped comparison](FET_VIDEO_PAIR_2026-10-18.md).
3. **Approach versus touch.** A broad accumulation area has no verified numeric
   bounds. The independent Coinbase comparison's minimum was $0.1502,
   above the quoted $0.145 point. Do not turn an
   approach into an exact-price fill or a proved successful trade.
4. **Formula as exported.** The lower-line formula contains a log price ratio
   with the same numerator and denominator, making that slope zero. Correct
   log interpolation is `exp(log(P1) + f*(log(P2)-log(P1)))`, where
   `f=(t-t1)/(t2-t1)`. Formula transcription is not an executable specification.
5. **Acceptance target.** Requiring an automatic detector to emit exactly
   $0.145 before the anchors are established encourages fitting the example.
   First test information timing, geometry and source conventions; then
   measure how independently selected structures differ from the analyst.
6. **Availability versus interpretation.** Confirmed local extrema are
   historical observations under a specified detector. A/B/C/D/E assignments
   are interpretations that need separate versioning. A revised wave hypothesis
   does not retroactively delete an observed local high/low.

## Concrete implementation from this review

`frontend/src/utils/chartStructure.js` adds standalone foundations:

- Wick/body pivot modes, retaining each anchor's alternate price convention.
  Wick mode delegates to the existing detector and preserves its defaults.
  Body mode uses max(open,close)/min(open,close), with bucket-open coordinates;
  it does not reuse the wick's constituent-day date as a body timestamp.
- Linear or log-price line evaluation through two explicit confirmed anchors.
  An explicit as-of cutoff withholds anchors before their confirmation.
  Fitted historical references retain their later availability date; future
  extrapolations are explicitly hypothetical. Nonpositive and overflowing
  projections are rejected.
- Four wick/body anchor combinations reported as a sensitivity envelope, with
  spread relative to its lower bound. It is not a confidence interval or a
  calibrated probability. No 8% quality gate, preferred channel or wave count
  is inferred.

These are calculation primitives. The existing chart renderer and its default
three-anchor results remain unchanged. No automatic ABCDE classification,
channel selection, indicator parity or profitable-call claim was added.
No per-coin parameters were tuned. This supports a subsequent channel renderer
and makes the anchor-convention decision inspectable before pattern detection.

## Further reference needed

Gemini should inspect attached video files or explicitly limit its answer to
supplied screenshots and timestamped notes. Establish actual channel anchors,
coordinate conventions and original zone bounds before designing a matcher.
Use the June record as frozen evidence and preserve unresolved values. Claude's
RNDR/RENDER separation decision at `9aff390` agrees with our current boundary.

## Verification

`npm run verify` passes the token/Figma sync check, build, and **490 tests in
41 files**, including 16 new geometry checks. Existing Browserslist, main-chunk
size and AlertsPanelGlobal act warnings remain. No chart UI changed.

On the previously hashed FET and RENDER snapshots, wick/body modes pass all
794 prefix checks (518 FET, 276 RENDER). Four-convention sensitivity evaluation
also succeeds for 1,445 same-kind pivot pairs across these cutoffs. Pairs are
the latest two observed highs or lows for numerical validation, not selected
channels, trading signals or evidence of edge. Guardrail and whitespace checks
pass. No new market requests were needed.

A local ignored Gemini reference packet contains short timestamped notes,
two selected chart frames and a correction prompt. Full source transcripts
remain internal review artifacts. The packet explicitly does not claim to be
a full-video inspection. Existing data, active worktrees, main and production
are untouched.
