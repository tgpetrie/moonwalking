# UI Design System — BHABIT / Moonwalking

**This is the canonical UI reference.** It replaces `DESIGN_SYSTEM.md`,
`FRONTEND_UI_RULES.md` and `UI_CONTRACT.md`. Those files stay for history only.
Where they disagree with this file, this file wins.

It records the design direction agreed on **2026-08-09** and the board polish
shipped on **2026-11-24** (PR #37, `0356603`), checked against the code on
`main`. The rules marked *enforced* are checked on every frontend PR by
`scripts/validate_ui_rules.sh` (the *UI Rules Validation* check).

## 1. Direction

Moonwalking is a **tactical market-intelligence terminal**, not a consumer SaaS
app. In practice:

- Sharp, restrained, compact. No bubbly controls, no decorative containers.
- Strong hierarchy: the number or event first, the explanation second, detail
  behind a disclosure.
- Accent colour is purposeful: gain/loss, state, focus. It isn't decoration.
- Visual changes and intelligence-engine changes ship separately, so a styling
  pass can never change what gets detected.

## 2. Corners

One scale drives every corner, defined in `frontend/src/styles/design-tokens.css`.

| Token | Value | Use |
|---|---|---|
| `--r-1` | 2px | chips, swatches, bars |
| `--r-2` | **3px** | buttons, CTAs, inputs, table rows *(enforced)* |
| `--r-3` | **4px** | panels, large surfaces *(enforced)* |
| `--r-4` | **4px** | cards that sit on a panel *(enforced)* |

- Nothing is rounder than 4px, except **status indicators, avatars and dots**,
  which may be pills (`999px`) or circles (`50%`).
- **No pill-shaped buttons** *(enforced: any button, CTA or `btn` rule at 12px or
  more fails; above 4px warns. Round icons and badges inside a button are allowed)*.
- Use the tokens, not literal pixel values.

## 3. Controls vs. indicators

Actions look like controls; statuses look like indicators.

**Controls** (CTAs, buttons, toggles, inputs):

- `border-radius: var(--r-2)` (3px), thin 1px border, no shadow.
- Uppercase, tracked (`letter-spacing: 0.12em`), Raleway.
- The canonical primary CTA is **ASK BHABIT**
  (`.bh-ask-btn`, `frontend/src/styles/ask-codex.css`): **34px** tall,
  `0 16px` padding, 3px corners, Raleway 700, 0.68rem, uppercase, 0.12em.
- Segmented filters use the **underline tab** pattern (`.bh-utabs`): no box, a
  2px bottom rule on the active tab.

**Indicators** (LIVE, STEALTH, DUMP, MOONSHOT, severity, state):

- May be rounded pills. They are never clickable on their own.

## 4. Type

- **Raleway** is the UI face: headings, labels, controls, body
  *(enforced: Raleway is loaded and leads `--bh-font-sans`)*.
- A **monospace** face (JetBrains Mono / Fragment Mono, `--font-mono-numeric`)
  is for **data only**: prices, percentages, scores, timestamps, tickers in
  tables. Never for CTAs.
- Typography contract classes: `.bh-pct`, `.bh-price-current`, `.bh-price-prev`
  *(enforced)*.

## 5. Header and brand

- The **header carries the brand**. There's no centered hero on the board.
- Brand lockup *(enforced)* in `DashboardShell.jsx`:
  ```
  .bh-brand
    img.bh-brand__mark           moon-rabbit mark, 28×28
    span.bh-brand__lockup        column
      img.bh-brand__wordmark     BHABIT
      span.bh-brand__tagline     "Profit Buying Impulse"
  ```
- The tagline (PBI) is stacked **under** the wordmark, not beside it: Raleway 600,
  8.5px, uppercase, `letter-spacing: 0.2em`, ~50% opacity, inside the 73px header.
- The tagline is hidden at **≤480px** and at **781–1180px**, where the
  navigation row has no room for it.

## 6. Board rows and panels

- Rows use the canonical grid `.bh-row-grid` / `--bh-cols` *(enforced)*.
- Every row keeps its permanent bottom rail, `.bh-row::after` *(enforced)*.
- Panel borders are thin and quiet. Don't add a frame where spacing will do.
- **Rabbit stencil:** the background rabbit is invisible at rest. A hovered row
  reveals only the slice of the stencil behind it.
- **Hover glass:** a diagonal clear glass from the row's inner edge outward,
  **orange for gainers, violet for losers**.
- Banners use `.bh-banner-track` and `.bh-banner-chip` *(enforced)*.
- Retired labels must not come back: "3 Min Gainers/Losers", "1 hour price %"
  *(enforced)*.

## 7. Intelligence Log (`AnomalyStream.jsx`)

- **Compact stream:** one line per event: `[time] CHIP SYMBOL message`, plus
  any confluence call and badges.
- **The Ask action lives outside the stream** (the floating ASK BHABIT dock), so
  controls never mix with events.
- **Detection belongs to the backend.** On Aug 9 the browser-side fallback that
  invented `SPIKE`, `RAPID DROP` and `VOLUME SHOCK` rows was removed. The log
  shows typed backend events, plus one gap-filler: a 1h volume jump of 80% or
  more shows as `VOLUME` while the backend's whale baseline warms up.
- **Dedup:** semantic key `type | symbol | window | direction` with a 5-minute
  TTL (`utils/intelligenceDedup.js`).
- **Ranking:** desk-tape severity, then event time
  (`utils/deskTape.js`). Contradictory moves within 60s keep the stronger one.
- **Evidence-first copy:** the measured move (%, volume, price, divergence)
  leads; interpretation follows.

## 8. Alerts tab (`AlertsTab.jsx`)

- **HOT RIGHT NOW** has a two-line header: the title line, then
  `Tape: <state> · Fresh n · Leaders n · Weakening n`. No large controls, no pills.
- **Three sections**, each independently collapsible with `aria-expanded` and
  `aria-controls`: HOT RIGHT NOW, Evolving Events and Watchlist Attention.
- **Order is decided once**, when the first alerts payload arrives: EVOLVING goes
  above an empty WATCHLIST, and WATCHLIST goes first when it has attention. The
  order is then **frozen** for the life of the tab, so later polls never make
  sections jump.
- **Loading is not empty.** Before the first payload, each section shows one
  quiet loading line ("Loading live tape…", "Loading signals…"). Empty copy
  ("No dominant live setup right now.") appears only once data has arrived.
- **Rows are simple:** type, ticker, one message line, time. WHY reasons map
  from context badges to plain words (e.g. "SPOT BUYING" → "buyers stepping in").
- **Progressive disclosure:** *Why this read?*, *Event analysis* and
  *Signal details* are native `<details>`.
  - Clicks inside them stop propagation, so the row's click doesn't fire.
  - The row's Enter/Space handler only acts when the row itself has focus, so
    keyboard users can open every expander.

## 9. Alert taxonomy

- Event types are normalized at one boundary, `normalizeEventType()` in
  `utils/alerts_normalize.js`, which has its own tests. New display mappings
  key off its canonical `SCREAMING_SNAKE_CASE` IDs.
- **Known debt:** `AlertsTab.jsx` still has its own lowercase type checks
  (`isHeatingAlert`, `isWhaleAlert`, `TYPE_LABEL`), and the Intelligence Log uses
  `alertClassifier.js`. Move them behind the boundary in a separate taxonomy
  commit, never mixed with visual changes.

## 10. Chart Reader

- The Chart Reader **interprets** events; it doesn't detect them.
- `/api/chart-read/<symbol>` accepts optional event context (`event_type`,
  evidence). Context only adds a note and a reference price. It never changes
  confidence or the Elliott-wave read, and without it the output is unchanged.

## 11. Enforcement

| Check | What it guards |
|---|---|
| **UI Rules Validation** (`scripts/validate_ui_rules.sh`) | Radius tokens, Raleway, brand lockup, board structure, retired labels, no pill buttons. Reports every failure, not just the first. |
| **pre-commit** (`detect-secrets` workflow) | End-of-file, whitespace, black, eslint (`eslint.config.mjs`, core bug rules) and detect-secrets, run on the PR's changed files only. |
| **check-legacy-css** | Legacy selectors. |

When a rule changes, change this file, the validator and the code in the same PR.

## Changelog

- **2026-08-09:**
  - Squared controls, the controls-vs-indicators split and the PBI tagline.
  - Intelligence Log compaction, with the Ask action outside the stream.
  - Alerts tab hierarchy and disclosures (`568be781`), taxonomy boundary
    (`8d456c8f`), Chart Reader event context.
- **2026-11-24:**
  - #37: header lockup, rabbit reveal, hover glass, radius tokens.
  - #39: CI and validator rewrite.
  - #41: keyboard-safe expanders, loading states, frozen-order test,
    ASK BHABIT to spec.
