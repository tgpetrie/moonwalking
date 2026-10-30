# Instant radar: executable target labels - 2026-10-29

Status: **label definition implemented; study and fitting remain gated**.
This implements the next step of Gemini's existing prospective proposal.
It does not establish an early-warning edge or change a live score.

The versioned [machine contract](INSTANT_TARGET_CONTRACT_V1.json) and
[`instant_targets.py`](../../scripts/scoring_experiment/instant_targets.py)
make the missing onset choices explicit before any prospective outcome
analysis. [Synthetic tests](../../tests/test_instant_targets.py) exercise
the labeling rules. The frozen historical experiment is untouched.

## Inputs and causality

`TargetEvaluator` accepts one product's strictly ordered, unique receipt-time
snapshots on a 5s grid. Each snapshot has coin and BTC bid/ask, original quote
timestamps, availability time, price-source flags, verified coverage,
deduplicated match count and match-derived USD volume. Quote age must be at
most 10s; both books must be positive and non-crossed. Last-trade fallbacks,
future receipts, unknown coverage and missing grid points are unavailable.
An empty but verified healthy bucket is a known zero, not a collection outage.
The recorder will have to prove these fields; accepting an input object
does not certify its provenance.

Counts/volume at grid time `t` describe `[t-5s,t)`. Forward counts exclude
trades exactly at the anchor: the first forward bucket also needs its
`trade_count_at_bucket_start`. Unknown boundary count means unavailable.
Forward quote states are at times strictly after the anchor. The anchor
itself supplies the starting price, spread and causal baseline.

`Baseline` supplies sigma from the preceding 60 closed 1m log returns,
ending exactly at the anchor's last completed minute, with availability at
or before the anchor. Require at least 60 returns; apply and expose the
0.0015 per-minute floor. Beta is frozen at the anchor with availability
and fallback flags. No rolling future beta/sigma can change the outcome path.
The evaluator checks metadata; candle/beta calculation belongs to the
later recorder/feature implementation.

Pace baselines are medians of 120 prior non-overlapping 30s trade-count and
USD-volume windows, ending exactly 30s before the anchor, available by it.
The current 30s window cannot contribute to its own reference median.
Zero medians cannot produce infinite ratios; at least one positive median
is required. An unavailable pace baseline invalidates onset, while a complete
forward impulse label may still be retained.

## Two separate labels

For direction `d = +1` (up) or `-1` (down), define the favorable residual:

```text
u(t) = d * [log(mid(t)/mid(anchor))
            - beta(anchor) * log(BTC(t)/BTC(anchor))]
```

For each horizon `H = 300s` or `900s`, `verified_forward` requires all of:

- Terminal `u(anchor+H) >= max(3*sigma*sqrt(H/60), 0.015, 3*entry_spread_fraction)`.
- Terminal favorable residual retains at least 60% of the largest favorable
  residual over the horizon. Include zero at the anchor and choose the first
  timestamp when peak values tie. Opposite-direction excursions cannot count
  as favorable merely because their absolute magnitude is large.
- At least three distinct, deduplicated matches strictly after the anchor
  and before the terminal boundary. Valid observed/carried quote coverage is
  required throughout. This is book-presence evidence, not executable fills.

The `0.015` threshold is explicitly in log-return units, approximately 1.5%.
The evaluator also retains adverse residual excursion, terminal return,
retention, first peak time and observed count for failed complete labels.
Rows without a move remain in the output; board entry is not a prerequisite.

`verified_onset` adds the following rules to `verified_forward`:

1. Signed 30s residual velocity divided by `sigma/sqrt(2)` crosses from below
   1 at the previous 5s grid point to at least 1 now. Both use the same causal
   anchor beta/sigma, avoiding a future normalization during evaluation.
2. At least five matches occur in the current 30s window. Its trade-count
   ratio or USD-volume ratio must be **strictly greater than 2** relative to
   its own prior median.
3. Starting from this candidate timestamp, take the first subsequent point
   within 180s with favorable residual at least `1.5*sigma` as the breakout.
4. After the candidate, the favorable residual never falls below zero through
   the full horizon, allowing `1e-12` floating-point tolerance.

The original proposal did not specify the cumulative breakout origin,
no-retrace endpoint or conflict resolution. This v1 fixes those choices:
each activity/velocity crossing supplies the breakout origin, and no-retrace
ends at `onset+H`. These are pilot definitions, not empirically optimal choices.
Onset means an **activity-confirmed threshold crossing**; it is not a claim
to identify the physical first tick of a move. A forward impulse can be real
while this stricter onset definition fails. Report that attrition explicitly.
The same numeric tolerance applies at inclusive/strict comparison boundaries.

## Maturity, event catalog and alert timing

`evaluate(anchor, baseline, direction, H, asof_ts_ms)` returns `pending`
until `anchor+H`, even if a partial path already looks successful. After
maturity, missing or invalid evidence gives `unavailable` and null labels.
`ready` means a complete label; the boolean can still be false. Future rows
after the horizon cannot change it. Endpoint slack is zero; the evaluator
does not interpolate, bridge gaps or select a favorable nearby observation.

`event_catalog` selects the earliest verified onset for each product,
direction and horizon; it suppresses further onsets in `[onset,onset+H)`.
The next onset exactly at the boundary is allowed. This is retrospective
event deduplication, separate from the prospective 15m per-coin alert cooldown
shared across boards. Up/down and 5m/15m catalogs stay separate. They can be
dependent and are not independent statistical observations.

`alert_timing` grades an actual publication timestamp against a verified
event. It uses the preceding grid snapshot only, with quote ages measured
at actual publication, including unaligned publication times:

- `[onset-180s,onset)`: `pre_onset_prediction`.
- At/after onset, at/before peak, with less than half the favorable residual
  peak consumed: `early_detection`.
- Remaining publications through the event end: `late_detection`.
- Outside that association interval: `outside_event_window`.

Detection delay is publication minus onset; lead time is peak minus
publication. Consumed fraction is the signed residual at publication divided
by event peak. It is deliberately not clipped: negative values before onset
and late values remain visible. These are evaluation classes, never live
stages. The future peak is required to calculate them. Alert assignment
across multiple events and operational false-alert/missed-move denominators
still need the frozen universe/alert protocol before fitting.

## Cost scenarios and remaining gates

Report raw coin midpoint simple return separately from market-relative
residuals. Directional gross coin bps are `d*(end_mid/start_mid-1)*10000`.
Illustrative net bps subtract half entry spread, half exit spread and twice
the per-side fee scenario (0, 10 or 25 bps). These newly declared scenarios
are sensitivity checks, not measured account fees, slippage or fills.
No stored net return is accepted, so costs cannot be deducted twice.

Every label carries the LF-normalized UTF-8 contract-file SHA-256 and
`evaluation_only`. The hash remains portable across Windows/Unix line endings.
Nothing here is imported by the backend. This implementation does not freeze
F1-F5 formulas, live-stage thresholds, scoring weights, readiness counts or
the full collection schema; the contract explicitly disables fitting until
those remaining gates are resolved. No discovery/validation was rerun.

The [completed audit report](results/feed_audit_20261028_completed/REPORT.json)
records 3,600.156 uninterrupted seconds with REST-reconciled sampled intervals
for all four products. BTC/SOL support ticker taker semantics; ALCX/AURORA
have only four/three paired trades, so the all-product gate remains false.
The controller stopped on the first complete sample as intended. Recorder
integration remains gated; label development does not depend on passing it.

Checkpoint verification: 104 targeted tests across labels, feed audit/campaign,
historical contract/driver/review, evidence restore and legacy WS handling
passed. All 11 frozen historical hashes, formatting, documentation links and
repository guardrails passed. The local 14B reviewer raised two suggestions;
the explicit missing-boundary rejection and bounded peak path already cover
them, so neither was accepted as a confirmed defect. Independent Claude and
Gemini reviews are still pending.

Run the bounded checks from this checkout:

```powershell
& 'C:\Users\tgpet\Projects\Moonwalking\.venv\Scripts\python.exe' -m pytest -o addopts= -q tests/test_instant_targets.py tests/test_feed_audit_campaign.py tests/test_coinbase_feed_audit.py
```
