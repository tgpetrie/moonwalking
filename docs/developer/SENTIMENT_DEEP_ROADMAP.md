# Deep Sentiment Roadmap

## Purpose
Define future sentiment versions beyond the current pipeline proxy:
- stronger validation and truth-state
- richer metrics and symbol-aware analysis
- integration into alerts/watchlist without contaminating core board truth

## Current state (v1)
- Tiered sentiment pipeline is proxied into the board backend and displayed in the UI.
- `pipelineStatus` and `sentiment_meta` determine truth-state (healthy vs stale/offline).

Authoritative integration details live in:
- `SENTIMENT_UI_INTEGRATION.md`
- `SENTIMENT_INTEGRATION_PLAN.md`

## v2: Harden truth-state + validation
Goals
- Strict schema validation (required keys per payload)
- Range checks and units
- Staleness policy (cache `last_good`, track staleSeconds)
- Explicit error reporting (no silent failures)

Deliverables
- Per-metric contract + valid ranges
- Tests ensuring invalid payloads do not overwrite `last_good`

## v3: Symbol-aware deep sentiment
Goals
- Divergence analysis per symbol (institutional vs retail where available)
- Market-structure inputs (where available)
- Tie into alerts using existing alert taxonomy (MOONSHOT/CRATER/etc) without injecting generic “trend scores”

Deliverables
- Symbol sentiment schema
- Alert mapping rules (type labels, cooldowns, severity windows)
- UI surface definition (sentiment modal/popup, intelligence panel, etc.)

## Future candidate inputs (only when approved/added)
- Fear & Greed index
- Funding / open interest / liquidation metrics
- Social volume / sentiment splits

## Non-goals
- Do not replace the board’s primary price/volume truth.
- Do not pollute alerts with generic trend feeds.

## References
- `SENTIMENT_UI_INTEGRATION.md`
- `SENTIMENT_INTEGRATION_PLAN.md`
- `MW_SPEC.md`
