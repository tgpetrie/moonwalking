# Sentiment One Board

## Purpose
Define the single canonical dashboard “board” surface that combines:
- Coinbase board data (existing board backend output)
- Sentiment pipeline proxy (tiered sentiment + pipeline truth-state)

This doc is the operational spec for what exists now and how it must behave truthfully.

## Canonical layout rule
The one-board grid rule is defined in `FRONTEND_UI_RULES.md` (see the “one board grid” section).
This document binds sentiment modules to that canonical wrapper/grid and forbids introducing parallel wrappers.

## Backend contract (board backend → frontend)
### Required fields
- `sentiment`: object | null
- `sentiment_meta`: object
  - `ok`: boolean
  - `staleSeconds`: number
  - `lastOkTs`: ISO string | null
  - `lastTryTs`: ISO string | null
  - `error`: string | null
- `pipelineStatus`: object | null (if surfaced by the sentiment normalizer / tiered pipeline)

### Truth rules
- Never fabricate `sentiment_meta` on fetch failure.
- Validate payload: reject missing required keys, NaN/inf, and out-of-range values.
- On invalid payload: keep `last_good` and mark stale (`ok=false`, `error` populated).

## Frontend behavior
- If `sentiment_meta.ok=true`: show real values.
- If `sentiment_meta.ok=false`: show offline/stale state with `staleSeconds` + `lastOkTs` + `error`.
- Never show placeholders (e.g. “50%”) unless the value is real.

## References
- `SENTIMENT_INTEGRATION_PLAN.md`
- `SENTIMENT_UI_INTEGRATION.md`
- `FRONTEND_UI_RULES.md`
- `MW_SPEC.md` (truth rules)
