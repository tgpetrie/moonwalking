# Portfolio Risk Board audit work items

Source audit: Portfolio Risk Board read-only UX audit from September 8, 2026.

This file turns the audit into a shareable implementation queue for Codex,
Claude, and human developers. It is not a new calibration plan. Preserve the
existing math and truth boundaries unless a separate task explicitly changes
them.

## Operational prerequisite

Before judging or editing the UI, verify the local runtime is serving the
reviewed source. The audit found a runtime/source mismatch: the running backend
omitted newer fields and still returned older behavior in places.

## Phase 1: Risk validity and level direction

Goal: remove misleading or backwards reads first.

Work items:

- Make invalidated entry state dominant on the Portfolio Risk Board.
- Use signed invalidation distance copy, including broken support above current
  price and equality at current price.
- Suppress actionable entry ratio/zone rendering whenever the entry is
  invalidated, even if an older payload contains numeric values.
- Pass entry context into chart and popup risk views.
- Display the broken entry boundary separately from the protection fallback
  reference.
- Replace wide-risk sizing copy with distance-convention copy:
  "Wide stop distance - X% to the support-based stop."
- Distinguish approaching resistance from already cleared resistance.

Suggested validation:

- Broken support fixture.
- Signal-invalidated fixture.
- Boundary-equality fixture.
- Watchlist unknown-size fixture.

## Phase 2: References, ratios, and evidence

Goal: explain why values differ without changing the values.

Work items:

- Standardize stop reference wording across board, chart, and popup.
- Show structural and volatility references separately where available.
- Label entry ratio as "Entry R/R - to invalidation."
- Label protection ratio as a resistance/stop-distance reference.
- Add an "Evidence & method" detail area for remaining reasons, invalidation
  reason, zone reason, and methodology.
- Replace "N of 10 declared cues" with "Evidence score N/10."
- Move legacy sell-limit wording to "Legacy sell-limit reference -
  uncalibrated" and reduce visual weight.

Suggested validation:

- Shared presentation tests for stop source labels.
- Withheld and missing-data tests.
- Reference-source tests.

## Phase 3: Hierarchy and Chart Read context

Goal: make the first read faster without adding a new layout system.

Work items:

- Compact board summary text.
- Replace protection "clear" with "No protection signal."
- Emphasize validity and the primary action before secondary metrics.
- Group unavailable rows or make unavailable-state copy more compact.
- Distinguish quote unavailable, candle history loading, and refresh failure.
- Explain Chart Read source and timeframe:
  "Coinbase 1-hour read; chart above may use another interval/source."
- Clarify activity and confidence chips as descriptive scores.

Suggested validation:

- Desktop and mobile visual pass.
- Keyboard interaction check for chart choices.
- No new layout system or token drift.

## Do not change during this audit follow-up

- Do not retune thresholds.
- Do not reopen September 8 calibration.
- Do not force entry and protection ratio calculations to match.
- Do not invent missing portfolio position sizes.
- Do not present legacy sell-limit values as calibrated execution guidance.
- Do not convert recent-range location bands into empirical probability claims.
- Do not add order placement, cancellation, transfer, or withdrawal behavior.

## Agent workflow

The local Audit Triage Agent can ingest the full audit:

```powershell
.\scripts\test_backend.ps1 backend\tests\test_agents_audit_triage.py
python scripts\run_local_agents.py --audit-file "C:\Users\tgpet\.codex\visualizations\2026\09\08\01a0819a-2af3-7d61-bc9c-b98796ca41f3\risk-audit\AUDIT.md"
```

The agent writes P0/P1/P2 problems, recommended changes, and implementation
steps into `backend/data/agent_observations.sqlite`. Other local agents and
local models should use those observations as the audit-backed task trail.
