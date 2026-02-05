# UI Contract: Rails, Rows, Motion, and Hierarchy

This document defines the non-negotiable UI layout and interaction contract for the dashboard. All components that render token-like rows MUST comply, including:

- 1-minute gainers table
- 3-minute gainers table
- 3-minute losers table
- Watchlist
- Intelligence Log (AnomalyStream) whenever it displays token-like entries or metric rows

If any component violates this contract, it is considered a bug.

---

## 1) Global Rails Contract

### 1.1 Core principle: one set of rails
All row-based components must share the same horizontal alignment rails:

- **Left rail**: token block (rank/icon/symbol/name)
- **Right rail**: metrics/actions cluster (price, percent, action buttons)

Watchlist and Intelligence Log must align their right-side metrics to the same right edge as the tables.

### 1.2 Row structure (canonical)
All token rows MUST follow this structure:

- Left block: token identity (rank + symbol/name)
- Right block: a fixed cluster with:
  - Price
  - Percent change
  - Actions (watchlist star, info button)

No component may improvise its own spacing.

### 1.3 Forbidden layout pattern
Do NOT use `justify-content: space-between` for token row containers.

Instead:
- Left block in normal flow
- Right cluster pushed to the far right via `margin-left: auto`
- Explicit internal spacing inside right cluster

---

## 2) Canonical Class Contract

The following classes (or direct equivalents) are canonical and must be used consistently across tables, watchlist, and intelligence log rows.

### 2.1 Row wrapper
- `.bh-row` (row root)
- `.bh-row-grid` (enforces the left/right rails grid)

### 2.2 Left token block
- `.bh-token`
- `.bh-token__name` (or `.bh-token__sym` / `.bh-token__label` as implemented)

### 2.3 Right cluster
- `.bh-right` (container for metrics/actions)
- `.bh-right__price`
- `.bh-right__pct`
- `.bh-right__actions`

Spacing requirements:
- Price ↔ pct: tight (small gap)
- Pct ↔ actions: slightly larger (medium gap)
- Entire cluster pinned to same right rail across all components

### 2.4 Banners (marquee)
- `.bh-banner-track` for track
- `.bh-banner-track--manual` for RAF-driven marquee (no keyframes)

---

## 3) Component Alignment Requirements

### 3.1 Tables are the reference
Tables define the canonical rails. All other row-based components must match them.

### 3.2 Watchlist is always full width
Watchlist rows must always render as full-width rows aligned to the same rails as the tables.
- Watchlist must not compress into multi-column grid.
- Watchlist must not use different right-cluster spacing.

### 3.3 Intelligence Log must align to the same rails
If Intelligence Log displays token-like metric rows:
- Left block = label/token identity
- Right block = metrics/actions pinned to the right rail

If Intelligence Log is text logs but shows metrics, the numeric/metric column must still align to the same right rail.

---

## 4) 1-Minute Layout Rules (4-or-less full width + 4x4 grid)

### 4.1 Rule: 4 or fewer rows = full width rows
When 1m list contains **4 rows or fewer**, render:
- single-column full-width rows
- identical rails as all other components
- no grid compression

### 4.2 Rule: more than 4 rows = 4x4 grid (up to 16 visible)
When 1m list contains **more than 4 rows**, render:
- a 4-column grid layout
- up to 16 items visible by default (4x4)
- each cell row still uses the same left/right rails internally

### 4.3 Show-more behavior
If more than 16 items exist, expand without breaking rails or changing row alignment.

---

## 5) 3-Minute Table Rules

### 5.1 Default visible
- 3m gainers: top 8
- 3m losers: top 8

### 5.2 Expand limit
- both expand to 16 via Show more
- row alignment remains identical

---

## 6) Motion Contract (efficient, always alive)

### 6.1 Always-on breathe must exist
Always-on breathe must be present even between data updates.
Preferred implementation:
- **single board overlay** (not per-row animation)

### 6.2 Allowed animation properties
Allowed:
- `opacity`
- `transform`

Avoid:
- animating box-shadow across many rows
- large-area filter animations tied to frequent updates

### 6.3 Hover bubble/glow contract
Hover must produce a responsive bubble/glow effect.

Mechanism:
- Board sets `--emit-x`, `--emit-y`
- Board toggles `data-row-hover="1"`

CSS uses those vars to position a radial glow overlay.

Requirements:
- bubble follows pointer smoothly (no layout shift)
- reveal localized to hovered row region
- hover glow tone: gold-forward highlight

---

## 7) Acceptance Checklist

A change is accepted only if all are true:

1. Tables, Watchlist, Intelligence Log share the same rails alignment.
2. 1m table: 4 or fewer items render full width; >4 uses 4x4 up to 16.
3. Watchlist always full width and aligned to same rails as tables.
4. Right cluster spacing: price near pct, actions slightly separated, pinned right.
5. Hover bubble/glow uses `--emit-x/--emit-y` and `data-row-hover="1"`.
6. Always-on breathe exists and is cheap (overlay-based).
7. No `justify-content: space-between` used to fake rails.

