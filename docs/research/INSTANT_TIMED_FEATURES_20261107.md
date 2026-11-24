# Timed instant-radar feature draft

The offline builder computes the five candidate inputs for one declared
product, 5-second feature cutoff `b`, and direction. The sign is +1 for up
and −1 for down. Each component has its own value or missingness reason.
The formulas use the candidate's fixed 30s and 180s windows. Sigma uses
the declared 0.0015 one-minute floor. The accompanying diagnostics retain
velocity, unsigned activity, cutoff spread, expansion, and raw signed
180s return for comparisons.

| Input | Computation |
| --- | --- |
| F1 acceleration | Direction times (30s midpoint log return minus one fifth of the preceding 150s log return) divided by floored sigma. Endpoints are `b-180s`, `b-30s`, and `b`. |
| F2 signed participation | Signed taker USD imbalance times log1p of 30s USD pace relative to the timed 120-bin median. Use at least five distinct first-receipt matches in `[b-30s,b)`, known maker sides inverted to taker sides, positive USD, and a positive baseline median. |
| F3 sampled pressure | Signed time-weighted mean of `(bid_size-ask_size)/(bid_size+ask_size)` over `[b-30s,b)`. |
| F4 active compression and expansion | Directional positive 30s velocity divided by `1 + log(max(high)/min(low))/(sigma*sqrt(15))`. |
| F5 market-relative movement | Signed `(coin_180s - beta * BTC_180s) / sigma` from synchronized midpoint endpoints. Retain the beta fallback flag. |

## F3 boundaries

Use fully processed book and transport events known by the evidence as-of,
ordered by local receipt and then sequence. Carry the last known state into
the window. At a receipt timestamp the final state in that millisecond applies
to the following segment. Events at `b` are excluded. Integrate only across
segments with a valid BBO, a matching active heartbeat, a quote no older than
10s, and a heartbeat no older than 5s. Age is measured from the original
receipt. Reaching an age limit at a segment's right edge is allowed. Any
positive-duration gap makes F3 unavailable. The denominator is 30 seconds.
The result measures sampled book pressure at logger receipts.

## F4 boundaries

Build high and low from actual first-receipt matches in 15 half-open,
UTC-aligned one-minute bins. The last bin ends at
`floor((b-30s)/60000)*60000` so its trades precede the expansion window.
One receipt-ID proof chain within a single continuity epoch must cover the
15-minute window. Count certified empty minutes separately and leave their
high and low absent. Require at least ten traded minutes. An incomplete
proof makes F4 unavailable. These are receipt-time trade candles.

## Timing and scope

A result carries the observation cutoff, explicit evidence as-of, each
ready component's evidence-availability time, actual baseline and feature
computation completion, and the timed baseline's evidence-prefix provenance.
Post-cutoff receipts cannot enter the formulas. A proof that becomes known
later can verify pre-cutoff observations at an explicitly later as-of. The
result identifies computation after the cutoff as diagnostic. An input
evidence timestamp does not include the subsequent baseline or feature
calculation. A consumer must use the recorded computation completion times.
This API produces offline evidence for the separately versioned decision
and grading design. A data-only pilot still needs to measure real
coverage and latency before a decision age limit or study freeze.

The detailed candidate and its comparison plan are recorded in the
[study draft](INSTANT_STUDY_FREEZE_CANDIDATE_20261030.md) and
[methodology triage](INSTANT_METHOD_REVIEW_TRIAGE_20261106.md).
