# Local chart evidence contract

The first local workflow is a deterministic, offline evidence producer. It does
not install a model, run an autonomous agent, call a service or trade. No API
keys are needed. Optional explanation agents can subsequently consume its JSON.

```powershell
node scripts/chart_evidence_packet.mjs PATH_TO_READ_ONLY_HISTORY.json --as-of 2026-07-23 --interval 1w --confirmation 2
node --test scripts/chart_evidence_packet.test.mjs
```

`--as-of` includes that entire UTC day, just like the chart replay control.
Without it the export's capture cutoff is used. The effective cutoff is capped
at the export's capture time. `--interval` is `1w` (default) or `1d`;
`--confirmation` is 1–4 completed bars on each side, default 2. stdout contains
JSON. `--output NEW.json` optionally creates a new file exclusively; an existing
file, including the input, is never overwritten. The caller must choose their
own scratch output path. The program does not discover or access data stores.

`moonwalking.chart-evidence/v1` carries the raw input SHA-256, original source
metadata, product identity, requested/effective cutoff, dated analysis close,
confirmed anchor IDs with bucket/actual-extreme/confirmation dates, historical
legs, recent reference reactions and macro recovery/extension levels. Distances
are signed percentages from the **same analysis close**, not probability or
profit. Weekly and daily reference closes can differ. Source metadata describes
the supplied export; its coverage is not claimed to be point-in-time knowledge.

The same frontend parsing, completed-candle aggregation, confirmation, geometry
and reaction functions produce the packet. Numerical evidence uses only candles
closed by the effective cutoff. No missing prices are filled and no RNDR/RENDER
stitching occurs. Missing-day counts cover internal intervals between retained
daily candles, not unseen pre-listing history. Insufficient history produces null
reference/empty levels plus an explicit unavailable reason.

## Bounded explanation/review job

Input: one immutable evidence JSON packet. Output: a plain-language explanation
whose numerical claims cite its anchor/level IDs and identify their calculation
or observation. A reviewer checks those references and distinguishes historical
observations from conditional geometry. No agent may invent or modify evidence.
Unknown values remain unavailable. An agent must not reinterpret source metadata
as independent validation, estimate arrival dates, claim calibrated probability,
profitable fills, all-time extrema or a validated Elliott wave count. These are
explicitly blocked in the packet. Reaction counts overlap and are not independent
trades. A future local model or task runner is a separate integration step.

Tests use **illustrative synthetic prices**, not financial observations. They
check dates/settings, provenance and arithmetic, insufficient history, create-only
output, and numerical-evidence invariance to a physical prefix and poisoned future
prices. These are correctness tests, not predictive validation.
