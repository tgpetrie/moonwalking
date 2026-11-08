# Design System — BHABIT + Moonwalking

This is the cross-system reference: what the tokens mean, where they live,
what each visual system's real conventions are, where they already agree,
where they genuinely disagree (and haven't been unified yet, on purpose),
and how to style something new so it stays consistent — for a human or an
AI agent picking this up cold.

**Token values live in code, not here.** The source of truth is
[`frontend/src/design-system/tokens.json`](../frontend/src/design-system/tokens.json).
This document explains *why* those values are what they are and *how* to
use them. Generate CSS and the Figma adapter manifest with `npm run tokens:build`.
Verification rejects stale generated files and invalid aliases.

The token types follow the [DTCG 2025.10 format](https://www.designtokens.org/tr/2025.10/format/).
The local generator validates the token types used in this repository; it is
not intended to accept every possible DTCG extension or reference syntax.

**This document does not replace the existing home-board specs.** It sits
above them:

| Doc | Scope | Status |
|---|---|---|
| `docs/FRONTEND_UI_RULES.md` | Home board (`/`) — grid, spacing, motion, the BHABIT bunny layer | Authoritative for the home board, unchanged by this doc |
| `docs/UI_CONTRACT.md` | Home board — row/rail layout contract for token-like rows (tables, the *legacy* watchlist widget, intelligence log) | Authoritative for those components, unchanged by this doc. See the gap noted in §4 below — it predates the Moonwalking `/app/*` watchlist and does not govern it |
| **This document** | Shared tokens + hierarchy across **both** systems; the Moonwalking `/app/*` shell's own conventions, which had no written spec before this | Canonical |

Read `docs/ai/AI_INDEX.md` first, as always, for which files are active
vs. legacy before touching anything.

---

## 1. The two systems, in one sentence each

- **BHABIT board** (`frontend/src/index.css`, root route `/`): dense,
  tabular, high-information-density. Fixed-width columns
  (rank/symbol/price/change/actions), tight row height, uppercase tracked
  labels, numbers doing most of the visual work.
- **Moonwalking app shell** (`frontend/src/styles/mvp-shell.css` and
  siblings, everything under `/app/*`): roomier panels and cards, softer
  gradients, prose-length copy and disclaimers (risk board, portfolio),
  built for reading, not just scanning.

**The difference is density and layout, not palette or typeface.** Both
already use Raleway as the UI font (`--font-sans`), and Moonwalking's
color tokens already partially alias BHABIT's
(`--mw-bg: var(--bh-bg, #050308)`, etc. in `mvp-shell.css`). Don't reach
for a new font or a new color family to make something feel like "the
other system" — reach for the density and layout tokens in §3.

---

## 2. Token reference

All of these live in `frontend/src/styles/design-tokens.css`, defined once
on `:root`, loaded globally via `frontend/src/index.css` (imported from
`frontend/src/main.jsx`, so every route has them — root board and `/app/*`
alike).

### Color

| Token | Value | Meaning |
|---|---|---|
| `--color-bg-void` | `#050308` | The app's base background |
| `--color-mint` | `#10ae9b` | BHABIT's canonical price color (`--bh-mint`/`--bh-price`) |
| `--color-amber` | `#ffb347` | **Positive** signal (gains) — yes, amber, not green; that's the real, already-live convention (`--bh-gain`) |
| `--color-violet` | `#c084fc` | Brand/accent **and** negative signal (price/P&L down) — see the decision below |
| `--color-violet-strong` | `#a855f7` | Darker accent, e.g. button hover states |
| `--color-rose` | `#ff9fb4` | **Danger** only — destructive actions, form errors, risk warnings. Not price direction |
| `--color-ink` | `rgba(236,231,223,.92)` | BHABIT's primary text color (`--bh-ink`) |
| `--white-92` / `--white-58` / `--white-35` | opacity ladder on white | Both systems build "muted text" as white-at-lower-opacity rather than a gray hex. Use one of these three rather than inventing a new opacity |

Semantic aliases — **prefer these over the primitives above** in new CSS,
so the *meaning* is what's shared:

```
--surface-void         → --color-bg-void
--text-primary         → --color-ink
--text-muted           → --white-58
--text-faint           → --white-35
--accent-primary       → --color-violet
--accent-primary-strong→ --color-violet-strong
--signal-positive      → --color-amber
--signal-negative      → --color-violet   (price/P&L down)
--danger               → --color-rose     (destructive, errors, risk warnings)
```

**Decided (2026-09-23): violet means "down" everywhere, matching the
board.** Violet does double duty — brand/accent (buttons, links, eyebrows)
and price/P&L down — which is fine because they show up in different
shapes: filled or outlined controls vs. numbers. Rose is now only
`--danger`.

Rule of thumb: **a number going down is `--signal-negative`; something
that can hurt you or failed is `--danger`.** A Delete button, a form
error, and a "Protect now" risk chip are danger. A −3.2% change and a
negative unrealized P&L are signal-negative. If a violet number ever sits
right next to a violet button and they genuinely read as the same thing,
fix it with shape or weight on the control, not by changing the signal
color.

### Radius

Migrated surfaces use `--r-1` through `--r-4` at 2, 4, 6, and 8px.
The active `/app` shell aliases `--mw-radius` to `--r-3`,
so panels and cards share the same 6px corner treatment. Command controls
(buttons, inputs, and navigation links) use `--r-2` at 4px. Reserve full
pill radii for compact semantic elements such as status chips, tags,
filters, and toggles; CTAs and containers must remain rectangular. Older
CSS still contains raw radius values; migrate those when the component is
actively edited instead of performing a blind global replacement. If a new
`var(--r-N)` reference has no matching definition in
`design-tokens.css`, treat that as a real bug.

### Shape and spacing hierarchy

- Commands use 4px corners; cards, panels, headers, and other containers use
  6px corners. A container must not look like a giant pill.
- Full pill corners are semantic: status chips, tags, filters, toggles, and
  compact state labels only.
- Outer page gutters use `--space-7` on wide public pages and `--space-4`
  on phones. Panels use `--layout-panel-pad`; card grids use
  `--layout-grid-gap`; stacked page sections use `--layout-section-gap`.
- Do not introduce a one-off gap when the nearest 4px spacing token expresses
  the same hierarchy. Larger space belongs between sections, medium space
  inside containers, and small space between a label and its value.

### Type

- `--font-sans` — Raleway, the UI/body font for both systems.
- `--font-numeric` aliases `--font-sans`: Raleway is the chosen numeric
  font as well. Numeric columns keep right alignment and
  `font-variant-numeric: tabular-nums`. JetBrains Mono and Fragment Mono
  are not loaded or selected in active styles. `--font-mono-numeric` remains
  only as a compatibility alias to Raleway for older consumers.
- `--text-2xs` through `--text-3xl` — a rationalized 9-step size scale.
  **This did not exist before this file.** Auditing `mvp-shell.css` alone
  turned up 25+ distinct `font-size` values with no consistent ladder
  (0.68rem, 0.7rem, 0.72rem, 0.74rem, 0.75rem, 0.78rem, 0.8rem, 0.82rem...).
  Each rung below is placed at the closest real cluster of existing
  values, so adopting it is a consolidation, not a visual break:

  | Token | Value | Use |
  |---|---|---|
  | `--text-2xs` | 0.68rem | eyebrow labels, chip text |
  | `--text-xs` | 0.75rem | secondary meta, timestamps |
  | `--text-sm` | 0.82rem | body-small, table cells |
  | `--text-base` | 0.9rem | default body text |
  | `--text-md` | 0.98rem | emphasized body — matches BHABIT's `.bh-price-current` / `.bh-change` |
  | `--text-lg` | 1.08rem | card/list price, subheads |
  | `--text-xl` | 1.3rem | section headings |
  | `--text-2xl` | 1.55rem | page subheads |
  | `--text-3xl` | `2.1rem` | page h1 |

  **Existing declarations still use their own literal `rem` values and are
  unaffected** — this scale is for new or actively-migrated CSS, not a
  retroactive rewrite of everything. See §5 for migration guidance.

### Spacing

`--space-1` (4px) through `--space-8` (32px), mostly base-4, same
consolidation approach as the type scale — real recurring values (8, 12,
14, 16, 18, 24, 28px...) placed at the nearest clean rung.

### Density — the actual system difference

```
--space-compact-x: var(--space-3)   /* 12px */
--space-compact-y: 8px
--space-comfortable: var(--space-4) /* 16px */
--label-tracking-compact: 0.08em
--label-tracking-comfortable: 0.14em
```

This is the real difference between the two systems' *feel*. BHABIT's
tables run tight (`--bh-row-px`/`--bh-row-py` in `index.css`,
`.bh-row--tight` at `padding: 4px 0`). Moonwalking's panels run roomier
(16px is the prevailing card padding in `mvp-shell.css`). These are two
named presets, not one replacing the other — pick per component. A dense
leaderboard row and a readable settings panel should not use the same
rhythm just because they share a token file.

### Layout — the `/app` workspace grid

```
--layout-sidebar-w: 248px            /* member sidebar column */
--layout-gutter: var(--space-6)      /* workspace outer padding (24px) */
--layout-section-gap: var(--space-5) /* between stacked sections/panels (20px) */
--layout-panel-pad: var(--space-5)   /* inside a .mw-panel (20px) */
--layout-grid-gap: var(--space-4)    /* between cards in a grid (16px) */
```

Every `/app` page sits in the same shell (`.mw-member-shell` →
`.mw-sidebar` + `.mw-workspace`), so these apply everywhere at once.
Before them, each was its own literal (sidebar 290px, workspace 28px,
sidebar padding 28/22px, sections and panels 24px).

**Shared component patterns** (all in `mvp-shell.css`, all tokenized):

| Pattern | Class | Hierarchy |
|---|---|---|
| KPI tile | `.mw-stat-card` | `span` = tracked uppercase `--text-2xs` label; `strong` = `--text-2xl` tabular mono number |
| Panel title | `.mw-panel__header` | `h3` = tracked uppercase `--text-xs` label (like the board's column headers); `span` = muted `--text-xs` note |
| List row | `.mw-list__row` (also `.mw-mini-list__row`, `.mw-session-row`) | left `div` stacks name (`strong`) over detail (`span`, `--text-xs`); trailing `span` = tabular mono `--text-xs` |
| Eyebrow | `.mw-eyebrow` | `--text-2xs`, 800 weight, `--label-tracking-comfortable`, accent color |

**Responsive data surfaces:** the current `/app/watchlists` route uses a
table inside `.mw-table-shell`, not the card/compact/list modes that lived
on the unmerged portfolio-risk branch. Preserve the table's horizontal
scroll behavior at narrow widths. If asset cards are introduced later,
use comfortable density for cards and compact density for full-width rows;
do not copy selectors from an old branch without the matching live JSX.

### Z-index

```
--z-base: 0        /* default stacking */
--z-raised: 10      /* a card/row lifted above siblings, e.g. an expanded chart */
--z-sticky: 50       /* sticky headers/nav */
--z-overlay: 900     /* a persistent floating panel — sentiment popup, ask-codex widget */
--z-modal: 9999      /* must sit above everything — dialogs, toasts */
```

Auditing every `z-index` in the app found values from `0` to `99999` with
no real tiers — mostly small numbers for local stacking, then a jump
straight to four/five-digit numbers for anything that has to win. This
names the tiers actually in use. One outlier,
`z-index: 99999 !important` (`index.css:2373`), is a last-resort override,
not a real tier — a smell to clean up if you're ever in that code, not a
rung to standardize on. **Never reach for a number bigger than
`--z-modal`; fix the stacking-context problem instead.**

### Breakpoints — documented, not enforceable

Raw CSS cannot use a custom property inside `@media (max-width: ...)` —
that needs a PostCSS plugin (`postcss-custom-media`) this project doesn't
have installed. So these are values to type literally, not live tokens:

```
480px   one narrow phone column
640px   compact phone layouts and narrow card grids
900px   two-column layouts collapse to one
1120px  desktop-wide app-shell layouts
```

Auditing every `@media max-width` in the app found 30+ distinct values
within a few px of each other (600, 620, 639, 640, 650, 700, 720, 760,
768, 780, 820, 900, 920, 980, 1023, 1050, 1080, 1100, 1120, 1180...). New
CSS should snap to the nearest of the four above instead of picking a new
number. If breakpoint drift becomes a real recurring problem, adding
`postcss-custom-media` to make these live tokens is a reasonable follow-up
— it hasn't been done here since it's a new build dependency, which is
its own decision.

---

## 3. How to style something new

1. **Reach for a semantic color token first** (`--text-primary`,
   `--signal-positive`, `--accent-primary`...), a primitive
   (`--color-amber`...) second, and a raw hex only if you're certain
   nothing existing fits — check §2 before adding one.
2. **Pick a density preset, don't invent padding.** Tight/tabular →
   `--space-compact-x/y` + `--label-tracking-compact` + uppercase labels
   (BHABIT's convention). Roomy/readable → `--space-comfortable` +
   `--label-tracking-comfortable`.
3. **Numbers that should line up in a column** (prices, percentages,
   scores, timestamps) get `--font-numeric` and
   `font-variant-numeric: tabular-nums`. This is already the convention in
   both systems' price displays; it's just not centralized before this.
4. **Use the type scale**, not a new `rem` value, unless you've checked
   the existing 25+ ad hoc sizes really don't cover the case.
5. **New floating/overlay UI** picks a z-index tier from §2's z-index
   table, not a guessed number.
6. **A new breakpoint** snaps to one of the four in §2, not a new pixel
   value picked to make one component look right.

---

## 4. Component source of truth

The v1 component layer lives in
`frontend/src/components/ui/DesignSystem.jsx`, with its visual contract in
`frontend/src/styles/ui-system.css`. The executable specimen is available at
`/design-system`.

| Component | Variants and states |
|---|---|
| `UiButton` | primary, secondary, ghost, danger; small, medium, large; disabled and loading |
| `UiCard` | default, subtle, raised; none, small, medium, large padding |
| `UiField` | input or textarea; hint, error, disabled, focus |
| `UiCheckbox` | checked, unchecked, disabled, focus |
| `UiChip` | neutral, accent, positive, negative, danger; active |
| `UiStack` / `UiCluster` | spacing steps 1 through 8 |

Use these components for new `/app` and public-shell work. Existing `mw-*`
controls are migration compatibility, not a reason to create another local
button or field pattern.

The platform-neutral token source is
`frontend/src/design-system/tokens.json`. Run `npm run tokens:build` after
editing it; `npm run verify` fails when the generated CSS is stale. The Figma
collection, scope, component-property, and Code Syntax mapping is documented in
`docs/design-system/FIGMA_LIBRARY_SPEC.md`.

### Migration coverage

| Surface | Status |
|---|---|
| Shared foundations | JSON source generates CSS and a Figma Plugin API adapter manifest; both checked in CI |
| Active numerical styles | Raleway through `--font-numeric`; no separate monospace family |
| Public navigation, Login, Signup | Use v1 Button, Card, Field, and Checkbox primitives |
| `/design-system` | Executable examples of the locked v1 inventory |
| Dashboard, Watchlists, Portfolio | Shared shell tokens and rectangular shape rules; legacy component markup remains for incremental migration |
| Figma library publication | Not performed; token source, adapter manifest, and construction contract are ready |

Do not describe this foundation release as a completed page-by-page rebuild.
New pages and edited controls should consume the shared primitives. Existing
board geometry and route behavior retain their own contracts.

## 5. The Moonwalking `/app/*` watchlist and `UI_CONTRACT.md`

`docs/UI_CONTRACT.md` requires token-like rows (tables, the watchlist
widget, intelligence log) to share one left/right rail layout and states
"Watchlist must always render as full-width rows... must not compress
into multi-column grid." That contract was written for the **home
board's** watchlist widget (`frontend/src/components/WatchlistPanel.jsx`
/ the legacy `Watchlist.jsx` family — see `docs/ai/AI_INDEX.md` for which
of those are actually live).

The **Moonwalking app shell's** watchlist at `/app/watchlists`
(`frontend/src/mvp/MvpApp.jsx`'s `WatchlistsPage`) is a separate account
management surface. On current `main` it renders a responsive HTML table
with editable notes inside `.mw-table-shell`; it does not offer the card,
compact, or list view modes that existed on the unmerged
`codex/portfolio-risk-board` branch. The home-board rail contract therefore
does not govern this route pixel-for-pixel, but both surfaces should retain
the same principles: stable identity and numeric columns, truthful empty
states, and no overlapping content. Any future view-mode redesign is a
product decision and must ship with matching JSX, CSS, and mobile tests.

---

## 6. Tooling decision and remaining migration

- **The active frontend is CSS-first, not Tailwind.** The conflicting
  Tailwind configs and inactive PostCSS plugin were removed during the
  2026-10-18 integration because no `@tailwind` layers were generated and
  current entry points are styled by the CSS files listed in
  `docs/ai/AI_INDEX.md`. Utility-looking class strings remain in inactive
  legacy components such as `AppRoot.jsx` and `SymbolPanel.jsx`; they are
  not a styling contract. If one of those components is promoted into an
  active route, migrate it to the shared CSS system or make Tailwind a
  separately reviewed build decision. Do not quietly reactivate Tailwind
  across the entire repository.
- **Migration is intentionally incremental.** The live app shell now uses
  shared layout, radius, typography, spacing, and semantic color aliases.
  Many older component rules still contain literal values. Move them onto
  tokens while editing those components, with visual verification, rather
  than doing a repository-wide search-and-replace.

---

## 7. Maintenance

If you add, rename, or repurpose a token: update
`frontend/src/design-system/tokens.json`, regenerate both outputs with
`npm run tokens:build`, and update the relevant contract here. Run
`npm run verify` before committing. The frontend uses npm and
`frontend/package-lock.json` as its dependency contract.

Token generation stages both outputs under an exclusive lock, checks that the
source has not changed, then publishes them with rollback on normal write
failures. An interrupted process leaves `.tokens-build.lock` to block builds.
After confirming the generator has stopped, remove that marker and run
`npm run tokens:build` to recover. Production builds also run `tokens:check`.
