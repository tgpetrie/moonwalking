# Ask Bhabit (frontend MVP)

Position-aware analysis, not a generic chatbot. Validates the core loop:
sample value → manual position → optional thesis → structured answer → what changed.

Self-contained feature area. Nothing here mutates global styles or backend files.
Fixture-backed until Codex freezes the backend contract — swap one function
(`defaultResolveAnalysis`) for a real fetch and the UI is unchanged.

## Files

| File | Role |
| --- | --- |
| `AskBhabitExperience.jsx` | Orchestrator / state machine (entry point). |
| `askBhabitContract.js` | Enums + presentation maps (change kinds, thesis, confidence, missing statuses, tags, feedback). |
| `askBhabitAdapter.js` | `buildAnalysisView` (raw → view model) and `validatePositionDraft`. |
| `defaultResolver.js` | Fixture resolver; the seam to replace with the backend call. |
| `useBetaAllowance.js` | Founder-funded trial counter (localStorage-persisted). |
| `analytics.js` | Lightweight instrumentation wrapper (no dependency). |
| `components/` | Presentational pieces (samples, forms, guided questions, answer, feedback, allowance meter). |
| `fixtures/` | Sample positions + backend-shaped analysis payloads. |
| `styles/ask-bhabit.css` | Scoped `.abx-*` styles. No global selectors. |
| `__tests__/` | Adapter, hook, and experience tests (30 tests). |
| `demo.jsx` + `../../../askBhabit.html` | Dev-only preview harness (`/askBhabit.html`), visibly fixture-backed. |

## Integrated Mount

The real application mounts this feature through
`frontend/src/components/AskBhabitPanel.jsx`, which is rendered from
`frontend/src/components/DashboardShell.jsx`. The shell uses `mode="live"`:
manual positions call `/api/ask-bhabit/*`, while sample positions remain
explicit demo fixtures.

Live mode preserves backend truth states. `analysis.status: not_configured` is
shown as model-not-configured copy, not a successful generated answer. Missing
provider states such as `not_configured`, `provider_error`, `stale`,
`conflicting`, and `unsupported` stay visible in Missing & uncertain data.

## Mounting

```jsx
import { AskBhabitExperience } from "./features/askBhabit";
// backend later: <AskBhabitExperience resolveAnalysis={fetchAnalysis} />
<AskBhabitExperience />
```

## Fixture schema — sample position

```
{ id, isSample, coverage: "rich"|"sparse", asset, name, quantity,
  entryPrice, costBasis, acquiredAt, note,
  thesis: { reason, invalidation, horizon, tags: [] } }
```

## Expected backend contract — analysis payload

`resolveAnalysis({ position, question, isSample }) -> Promise<payload>`

Success payload (snake_case; the adapter is the only reader):

```
{
  request:    { asset, question_id, question_text, has_thesis },
  generated_at: ISO8601,
  direct_read:  { headline, tone, detail },
  what_changed: { kind, since: ISO|null, items: [{ label, detail, tone }] },
  position:     { quantity, entry_price, cost_basis, market_price,
                  unrealized_pnl, unrealized_pnl_pct, allocation_pct },
  thesis_check: { state, reasons: [] } | null,
  evidence:     [{ claim, detail, tone }],
  missing:      [{ metric, status, detail }],
  confidence:   { level, reasons: [] },
  sources:      [{ provider, claim, retrieved_at: ISO, freshness, url|null }],
  meta:         { mode, model }
}
```

Failure envelopes (never render a partial answer):

```
{ error: "provider_error", message }
{ error: "model_failure",  message }
```

### Enumerations (must match exactly)

- `what_changed.kind`: `price_only` · `market_structure` · `evidence_quality` · `thesis_evidence` · `insufficient_history`
- `thesis_check.state`: `strengthened` · `unchanged` · `weakened` · `cannot_determine`
- `confidence.level`: `high` · `medium` · `low` · `insufficient`
- `missing[].status`: `unavailable` · `unsupported` · `not_configured` · `stale` · `provider_error` · `conflicting`
- `tone` (any): `positive` · `info` · `warning` · `danger` · `muted`
- `freshness`: `fresh` · `stale` · `error` (others render as `warning`)

Unknown enum values degrade to a safe, **non-neutral** default in the adapter
rather than rendering blank — verified by test.

## Instrumentation events (`analytics.js`)

`sample_portfolio_opened`, `sample_analysis_viewed`, `position_added_manually`,
`cost_basis_entered`, `thesis_added`, `first_question_asked`, `answer_completed`,
`answer_failed`, `answer_rated`, `citation_opened`, `unsupported_data_warning_shown`,
`repeat_asset_query`, `different_asset_query`, `return_session`, `seven_day_return`.

`seven_day_return` is defined but must be fired by a session-boot check with a
persisted first-seen timestamp (not wired to a component event).

## Accessibility & responsive

- Semantic `<form>`/`<label>`/`<section>`; every input has an associated label.
- Toggle buttons expose `aria-pressed`; loading/error/allowance use `role=status`/`role=alert` with `aria-live`.
- Invalid inputs set `aria-invalid` and render an inline error string.
- Tone is never conveyed by color alone — each state carries a text label (pill/badge).
- Grids collapse to single column ≤ 560px (`abx-samples`, `abx-row`, `abx-posgrid`).
- Spinner respects `prefers-reduced-motion`.
- Sources use native `<details>` for keyboard-friendly progressive disclosure.

## Integration assumptions

- Renders inside the existing dark dashboard; relies on `--bh-font-sans` if present, else falls back.
- Beta allowance is client-side only (localStorage) for the trial — the backend is the source of truth once wired; the sample path never consumes allowance.
- External source links open with `rel="noopener noreferrer"`.
- No new runtime dependency added (uses existing `react` + `prop-types`).

## Tests

`npx vitest run src/features/askBhabit` — 30 tests (adapter classification &
validation, beta allowance, and the full experience across sample, manual,
thesis, missing-data, stale, unsupported, confidence, no-prior-snapshot,
feedback, provider/model failure, and trial-exhausted states).
