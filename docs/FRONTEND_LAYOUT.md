CBMo4ers / BHABIT Frontend Layout & Style Spec

Authoritative UX + UI spec for the dashboard as of mid-November.
This is "the truth" the code must follow.

---

1. Page Structure & Grid

Viewport: Dark canvas, full-screen, no visible card borders.

High-level layout:
  1. Top region:
    - TopBannerScroll (1-hour price change) – horizontal autoscroll strip.
  2. Core board:
    - GainersTable1Min (1-minute gainers board) – special layout.
    - GainersTable3Min (3-minute gainers) and Losers3m (3-minute losers) – side by side, aligned grid, shared numbering and width.
    - WatchlistPanel – shares width logic with the 1-minute board and 3-minute tables.
  3. Bottom region:
    - VolumeBannerScroll – horizontal autoscroll strip for 1-hour volume change.
  4. Background / Brand:
    - BHABIT rabbit art behind the board at low opacity.
    - BHABIT logo + “Profits Buy Impulse” at the top center (or top board header), following the style guide.

Grid rules:
  - All “board” content (1m + 3m + watchlist) lives inside a single board shell.
  - Max width (e.g. 1200–1400px), centered.
  - Same left/right padding.
  - All tables and panels line up on that grid:
    - Header text aligned.
    - Numbering columns aligned.
    - Row heights consistent.

---

2. Color & Typography Rules

Use the BHABIT palette (from your style guide), but these are the semantic rules:
  - Background: near-black (--bh-bg).
  - Base text: light grey/soft white (--bh-text).
  - Gainers (positive): gold/orange (--bh-gain).
  - Losers (negative): purple (--bh-loss).
  - Price / key numeric values: cyan/blue (--bh-price or --bh-cyan).
  - Secondary labels (timeframes, tags): muted grey / desaturated tones.

Typography:
  - Headings: Prosto One / Raleway per style guide.
  - Table text: Raleway (or your chosen body font).
  - Numbering (rank): same font family as row, slightly heavier weight, same size across ALL tables.

All text in banners and tables must be inside classes that encode both size and color (no random inline styles):

Examples (class names are placeholders, but the behavior is required):
  - `.token-symbol` – uppercase ticker, medium size, base color.
  - `.token-price-current` – price, cyan, larger.
  - `.token-price-prev` – smaller, below current, color based on move.
  - `.token-change` – gold/purple depending on direction.
  - `.token-volume` – same alignment rules as price.

---

3. Ambient Glow, Lines, and Hover

3.1 Row Background
  - Always transparent. No filled card background, no grey boxes. The board lives on a dark canvas.

3.2 Static Bottom Line (Outer Glow Rail)
  - Each row has a permanent rail under it:
    - A thin horizontal gradient line under the row.
    - This rail:
      - Is always present (not just on hover).
      - Matches the BHABIT gradient (gold/orange → purple).
      - Sits perfectly centered under the row (no double-lines, no offset).

3.3 Inner Hover Glow
  - On hover:
    - A soft inner glow appears, centered under the row text.
    - Positive row → transparent gold/orange glow.
    - Negative row → transparent purple glow.
    - The glow should be inside the row bounds, not floating under the next row.

Implementation shape (conceptual):
  - Each row has:
    - Static rail: `.row-ambient-line`.
    - Hover overlay: `.row-hover-glow` (opacity 0 → 1 on hover).
    - `.row-hover-glow` uses `position: absolute` inside a `position: relative` row container so it always lines up.

If the current UI shows “two lines” (one static + one misaligned), it means the hover glow is not anchored to the row container correctly. Fix that by:
  - Ensuring `.table-row` is `position: relative`.
  - Ensuring both rail + glow share the same horizontal positioning logic.

3.4 Breathing / Alive Effect
  - Optional but desired: very subtle scale/opacity breathing on the whole board or background rabbit. Do not bounce the actual data rows aggressively.

---

4. Rabbit Background (BHABIT Art)

Requirements:
  - Rabbit art sits behind the core board (z-index below rows).
  - Low opacity (e.g. 4–10%). It should be visible but not legible enough to interfere with data.
  - Placement: anchored to one side (e.g. right side) per the design file.
  - Use `mix-blend-mode` and `opacity` as in the style guide.

---

5. Top Price Banner (TopBannerScroll)

Required row structure (per token):
  1. Left cluster: token icon, symbol `.token-symbol`, timeframe tag `.token-tag`.
  2. Center cluster: current price `.token-price-current` (large, cyan), previous price `.token-price-prev` (small, below), gains/losses color semantics.
  3. Right cluster: percent change pill `.token-change` (gold/purple border/text).

Logic:
  - Banner row uses same `is-gain` / `is-loss` classes as tables.
  - Classes drive colors; do NOT hardcode gold for everything.

Autoscroll:
  - Banner content scrolls horizontally (looping marquee) at a readable speed.

---

6. Bottom Volume Banner (VolumeBannerScroll)

Same skeleton as TopBannerScroll for symbol + current/previous volume + % change pill. Respect typography and colors.

---

7. 1-Minute Gainers Board (GainersTable1Min)

7.1 Interleaved Ranking
  - Shared sequence of ranks across both columns: 1 -> left, 2 -> right, 3 -> left, ...
  - Rank column widths and font size must match the 3-minute tables.

7.2 Column Behavior
  - 4 or fewer tokens: single full-width column.
  - 5+ tokens: split into two columns with interleaved ranks; combined width must match 3-minute tables.

7.3 Cell Content
  - Rank number, token icon + symbol, current price, previous price (required), 1-minute % change.

---

8. 3-Minute Tables (GainersTable3Min + Losers3m)

Layout:
  - Two tables side-by-side inside same grid row; combined width aligns under the 1-minute board.
  - Header alignment and font sizes must match.

Numbering:
  - Each table has its own 1-based rank; rank font size identical across 1m and 3m boards.

Cell content: rank, symbol, current price, previous price (required), 3-minute % change, direction coloring.

When no data: render shells + placeholder rows so layout doesn't collapse.

---

9. Watchlist Panel

Uses same width rules as 1-minute board and 3-minute tables. Appears under the 3-minute tables (or under 1-minute per latest layout). Rows use same hover glow and static rail.

---

10. Behavior When Backend/Data Is Missing

All tables/banners still render consistent skeletons: header titles, placeholder rows or “No data” messages, consistent font sizes and spacing.

---

11. How the AI Should Use This Doc

1. Read this doc fully.
2. Audit components (DashboardShell.jsx, GainersTable1Min.jsx, GainersTable3Min.jsx, Losers3m.jsx, WatchlistPanel.jsx, TokenRow.jsx, TopBannerScroll.jsx, VolumeBannerScroll.jsx, index.css).
3. For each component: compare markup/classes to requirements and fix missing previous price, wrong colors, incorrect widths/alignments, hover/rail placement, rabbit opacity, and use shared CSS classes.
4. Only ask questions if the design file and this doc conflict or something is truly ambiguous.

---

12. TL;DR
  - This file is the single source of truth for frontend layout and styling. Use it to drive a full audit and remediation pass.

If desired, additional CSS snippets for the ambient line + hover glow can be added to `index.css` to complete the implementation.
