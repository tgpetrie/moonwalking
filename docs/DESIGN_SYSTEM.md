# Design System — BHABIT + Moonwalking

This is the cross-system reference: what the tokens mean, where they live,
what each visual system's real conventions are, where they already agree,
where they genuinely disagree (and haven't been unified yet, on purpose),
and how to style something new so it stays consistent — for a human or an
AI agent picking this up cold.

**Token values live in code, not here.** The source of truth is
[`frontend/src/styles/design-tokens.css`](../frontend/src/styles/design-tokens.css).
This document explains *why* those values are what they are and *how* to
use them; if the two ever disagree, the CSS file is correct and this file
is stale — fix this file to match it.

**This document does not replace the existing home-board specs.** It sits
above them:

| Doc | Scope | Status |
|---|---|---|
| `docs/FRONTEND_UI_RULES.md` | Home board (`/`) — grid, spacing, motion, the BHABIT bunny layer | Authoritative for the home board, unchanged by this doc |
| `docs/UI_CONTRACT.md` | Home board — row/rail layout contract for token-like rows (tables, the *legacy* watchlist widget, intelligence log) | Authoritative for those components, unchanged by this doc. See the gap noted in §4 below — it predates the Moonwalking `/app/*` watchlist and does not govern it |
| **This document** | Shared tokens + hierarchy across **both** systems; the Moonwalking `/app/*` shell's own conventions, which had no written spec before this | New |

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
| `--color-violet` | `#c084fc` | Brand/accent primitive. See the unresolved note below before using this for gain/loss |
| `--color-violet-strong` | `#a855f7` | Darker accent, e.g. button hover states |
| `--color-rose` | `#ff9fb4` | **Negative** signal (danger/risk/down), Moonwalking's convention (`--mw-danger`) |
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
--signal-negative      → --color-rose
```

**Unresolved, on purpose:** BHABIT colors a *losing price* with
`--bh-loss`, which is this same violet (`.is-down`, `.token-pct-loss`,
`.bh-banner-change--neg` in `index.css` all resolve to it). Moonwalking
reuses that identical violet as `--mw-accent` — its general brand/button
color, unrelated to gain or loss — and separately invented `--mw-danger`
(rose) for its own "down" state. So the same hex means "price fell" in one
system and "this is a branded button" in the other, and the two systems
render a losing price in two different colors today. Unifying that
repaints something a user already sees, which is a real visual-behavior
call, not a missing token — so it hasn't been made here. If you're asked
to make this consistent: decide whether BHABIT's `--bh-loss` usage should
move to `--signal-negative` (rose), and update `index.css`'s `.is-down`
family deliberately, in a change that says so, not as a side effect of
touching tokens.

### Radius

One knob drives every corner: `--radius-base: 2px`, then `--r-1`
(×1) through `--r-4` (×4). `--r-4` was added by this token file — it was
referenced by `.mw-watchlist-asset`'s `border-radius` before this file
existed but never defined anywhere, so that card had square corners
instead of the intended rounded ones. If you find another `var(--r-N)`
with no matching value, that's the same bug class — check
`design-tokens.css` defines it, and if not, that's a real fix, not a
style preference.

### Type

- `--font-sans` — Raleway, the UI/body font for both systems.
- `--font-mono-numeric` — the monospace stack both systems already reach
  for on tabular numbers (prices, scores, timestamps), previously repeated
  as the same literal font stack in a dozen files (alerts, scorecard,
  sentiment popup, ask-codex). Use this token for any new numeric/tabular
  display instead of retyping the stack.
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
  | `--text-3xl` | `clamp(1.5rem, 3vw, 2.1rem)` | page h1 (matches the Risk Board's existing h1 clamp) |

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
650px   card grids collapse to one column (the watchlist's existing breakpoint)
900px   two-column layouts collapse to one
1100px  desktop-wide layouts (the risk board's expanded-card breakpoint)
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
   scores, timestamps) get `--font-mono-numeric` and
   `font-variant-numeric: tabular-nums`. This is already the convention in
   both systems' price displays; it's just not centralized before this.
4. **Use the type scale**, not a new `rem` value, unless you've checked
   the existing 25+ ad hoc sizes really don't cover the case.
5. **New floating/overlay UI** picks a z-index tier from §2's z-index
   table, not a guessed number.
6. **A new breakpoint** snaps to one of the four in §2, not a new pixel
   value picked to make one component look right.

---

## 4. The Moonwalking `/app/*` watchlist and `UI_CONTRACT.md`

`docs/UI_CONTRACT.md` requires token-like rows (tables, the watchlist
widget, intelligence log) to share one left/right rail layout and states
"Watchlist must always render as full-width rows... must not compress
into multi-column grid." That contract was written for the **home
board's** watchlist widget (`frontend/src/components/WatchlistPanel.jsx`
/ the legacy `Watchlist.jsx` family — see `docs/ai/AI_INDEX.md` for which
of those are actually live).

It does not govern, and predates, the **Moonwalking app shell's**
watchlist at `/app/watchlists`
(`frontend/src/mvp/MvpApp.jsx`'s `WatchlistsPage`, styled by
`.mw-watchlist-*` in `mvp-shell.css`). That page deliberately does
compress into a multi-column card grid (`Cards` view — `Compact` and
`List` are the other two view modes it offers), which is a real
divergence from `UI_CONTRACT.md`'s rule, not an oversight to silently
"fix" by cramming it back into the old rail contract. If the two
watchlists should look and behave the same, that's a product decision
(which one wins, or do both stay) — flag it rather than pick silently.

---

## 5. Known gaps and cleanup flagged, not fixed, by this pass

- **Two conflicting Tailwind configs.** `frontend/tailwind.config.js` and
  `frontend/tailwind.config.cjs` both exist, with different, contradictory
  theme extensions (different color palettes; `.js` sets the font family
  to "Saira", which isn't loaded anywhere and isn't used by any real
  component — every component that sets a font explicitly uses Raleway).
  **Bigger finding: neither is actually active.** There is no
  `@tailwind` directive anywhere in `frontend/src`, so Tailwind's
  base/components/utilities layers are never generated at all, despite
  the PostCSS plugin being configured
  (`frontend/postcss.config.cjs`). Every Tailwind utility class name used
  across the codebase — `bg-purple-700`, `font-mono`, `text-orange-400`,
  etc., including in live, currently-rendered components like
  `CodexPanel.jsx` and `AlertsIndicator.jsx` — currently produces zero
  CSS. This is either dead tooling to remove (delete both configs, the
  `tailwindcss`/`autoprefixer` devDependencies, and stop writing Tailwind
  classes) or a real capability someone meant to wire up and never did
  (add `@tailwind base; @tailwind components; @tailwind utilities;` to
  `index.css`, pick one config, delete the other, and audit whether the
  now-real utility classes collide with anything). Either is a reasonable
  call; making it silently is not, since it either deletes working
  config files or newly activates hundreds of previously-inert class
  names across the app. Flagged for a deliberate decision.
- **The gain/loss color clash** described in §2 — same violet hex means
  two different things depending on which system's CSS you're reading.
- **`--r-4` and `--mw-success`** were both referenced before being
  defined anywhere — fixed by `design-tokens.css`, but if you find another
  `var(--x)` with nothing defining `--x`, treat it the same way: a silent
  bug (the property computed to its initial value, invisibly), not a
  style choice.

---

## 6. Maintenance

If you add, rename, or repurpose a token: update
`frontend/src/styles/design-tokens.css` (the values) **and** this file's
§2 (the reasoning and table row) in the same change. A token that exists
in one and not the other is exactly the kind of silent drift this
document exists to prevent.
