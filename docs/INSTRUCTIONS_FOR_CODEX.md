# INSTRUCTIONS FOR CODEX — UI Fixes

These are surgical instructions. Execute them in order. Do not refactor. Do not add features.

---

## INSTRUCTION 0: Fix verification script bug

**File:** `frontend/scripts/verify_ui_contract.sh`

**Problem:** Lines 66-67 cause `rg` to interpret `--emit-x` and `--emit-y` as flags.

**Fix:**
```bash
# OLD (lines 66-67):
emitx="$(rg -n '--emit-x' "$CSS" || true)"
emity="$(rg -n '--emit-y' "$CSS" || true)"

# NEW:
emitx="$(rg -n -F -- '--emit-x' "$CSS" || true)"
emity="$(rg -n -F -- '--emit-y' "$CSS" || true)"
```

**Proof required:** Run `./frontend/scripts/verify_ui_contract.sh` and confirm no rg flag error.

---

## INSTRUCTION 1: Consolidate .bh-row::after hover blocks

**File:** `frontend/src/index.css`

**Problem:** 20+ `.bh-row::after` rules scattered throughout file, many duplicates.

**Goal:** Reduce to 6 or fewer by commenting out duplicates and consolidating at file end.

### 1.1: Comment out legacy hover blocks (do not delete)

Locate and **comment out** (using `/* ... */`) these blocks:

- **Lines 854-862** (`.bh-row.is-gain:hover::after` rail gradient)
- **Lines 864-875** (`.bh-row.is-loss:hover::after` rail gradient)
- **Lines 2333-2357** (`.board-core .bh-row.is-gain:hover::after`)
- **Lines 2358-2377** (`.board-core .bh-row.is-loss:hover::after`)
- **Lines 3185-3196** (`.bh-row.is-gain:hover::after` with `.token-row`)
- **Lines 3197-3208** (`.bh-row.is-loss:hover::after` with `.token-row`)

Wrap each block with:
```css
/* DISABLED — Legacy hover (replaced by data-side final block)
[original content]
*/
```

### 1.2: Add authoritative marker comment at line ~4027

Before the existing "SINGLE SOURCE OF TRUTH" block (currently line ~4027), add this marker:

```css
/* =========================================================
   AUTHORITATIVE CANONICAL ROW HOVER — FINAL
   This block is the ONLY source of truth for:
   - .bh-row::before (rail)
   - .bh-row::after (hover glass)
   Do not add hover rules above this line.
   ========================================================= */
```

### 1.3: Consolidate data-side hover rules

At the end of the file (after line 4107), ensure ONLY these selectors control hover hue:

```css
/* Gainer hover (gold) */
.board-core .bh-row[data-side="gainer"]::before { /* rail */ }
.board-core .bh-row[data-side="gainer"]:hover::after { /* glass */ }

/* Loser hover (purple) */
.board-core .bh-row[data-side="loser"]::before { /* rail */ }
.board-core .bh-row[data-side="loser"]:hover::after { /* glass */ }
```

Do NOT modify the existing rules at lines 4102-4107 — they are correct. Just ensure nothing comes after them.

**Proof required:**
- Run: `rg -n '\.bh-row::after\b' frontend/src/index.css | wc -l`
- Expected: <= 6
- Run: `./frontend/scripts/verify_ui_contract.sh`
- Expected: "PASS: Pseudo-element duplication seems controlled"

---

## INSTRUCTION 2: Neutralize legacy gain/loss class selectors

**File:** `frontend/src/index.css`

**Problem:** Selectors using `.is-gain`, `.is-loss`, `.bh-row--gain`, `.bh-row--loss` still control hover behavior.

**Goal:** These classes can exist for banner/chip styling, but MUST NOT drive row hover hue.

### 2.1: Verify banner/chip usage is isolated

These selectors are ALLOWED (non-row elements):
- `.bh-banner-item.is-gain`
- `.bh-banner-chip.is-loss`
- Anything NOT under `.bh-row` or `.board-core .bh-row`

### 2.2: Remove row-specific legacy selectors

Search for and comment out:
- Any `.bh-row.is-gain` or `.bh-row.is-loss` NOT already disabled in INSTRUCTION 1
- Any `.bh-row--gain` or `.bh-row--loss` (currently lines 660, 666-667)

Wrap with:
```css
/* DISABLED — Legacy class-based row styling (replaced by data-side)
[original content]
*/
```

**Proof required:**
- Run: `rg '\.bh-row\.(is-gain|is-loss|bh-row--(gain|loss))' frontend/src/index.css`
- Expected: All matches should be inside `/* DISABLED ... */` comments
- Run: `./frontend/scripts/verify_ui_contract.sh`
- Expected: "PASS: No legacy gain/loss selector families found" OR acceptable banner-only usage

---

## INSTRUCTION 3: Add rabbit spotlight --emit-x/--emit-y usage

**File:** `frontend/src/index.css`

**Problem:** Rabbit spotlight mask exists but doesn't reference JS-provided CSS variables.

**Current situation:**
- Line 3279-3309: `.board-core .rabbit-bg` exists
- It uses `--emit-x` and `--emit-y` in mask-image
- Verification script should detect these

**Action:** Verify the existing code at lines 3279-3309 contains:

```css
-webkit-mask-image: radial-gradient(
  ellipse 280px 110px at var(--emit-x, 50%) var(--emit-y, 50%),
  ...
);
mask-image: radial-gradient(
  ellipse 280px 110px at var(--emit-x, 50%) var(--emit-y, 50%),
  ...
);
```

If these exist, the CSS side is complete. If NOT, add them to the `.board-core .rabbit-bg` rule.

**Proof required:**
- Run: `rg -n -F -- '--emit-x' frontend/src/index.css`
- Expected: At least one match
- Run: `rg -n -F -- '--emit-y' frontend/src/index.css`
- Expected: At least one match
- Run: `./frontend/scripts/verify_ui_contract.sh`
- Expected: "PASS: CSS references --emit-x and --emit-y"

---

## INSTRUCTION 4: Verify DashboardShell emitter (JS side)

**Files to inspect:**
- `frontend/src/components/DashboardShell.jsx` (or similar)
- `frontend/src/App.jsx`
- Any component that contains the `.board-core` wrapper

**Goal:** Confirm JS sets these on the board container:
- `style={{ '--emit-x': '...px', '--emit-y': '...px' }}`
- `data-row-hover="1"` when row is hovered

**Actions:**
1. Search for where `.board-core` or `.rabbit-bg` container is rendered
2. Verify there's event delegation for row hover (`.bh-row:hover` or similar)
3. Confirm CSS vars are set via inline styles or setAttribute

**Proof required:**
- File path + line numbers where:
  - Board container ref is created
  - Mouse event listeners are attached
  - CSS vars are updated
  - `data-row-hover` attribute is toggled

---

## INSTRUCTION 5: Force watchlist single-column

**File:** `frontend/src/index.css`

**Problem:** Watchlist may inherit 1m grid's two-column layout.

**Goal:** Watchlist rows must always be single-column, full-width.

### 5.1: Add scoped override at END of file

After line 4107 (the final row hover block), add:

```css
/* =========================================================
   WATCHLIST LAYOUT OVERRIDE — Always single-column
   ========================================================= */

.watchlist-panel .panel-row--1m,
.bh-watchlist .panel-row--1m,
[data-panel="watchlist"] .panel-row--1m {
  grid-template-columns: 1fr !important;
  row-gap: 0;
}

.watchlist-panel .bh-1m-grid,
.bh-watchlist .bh-1m-grid {
  grid-template-columns: 1fr !important;
}
```

### 5.2: Verify existing override doesn't conflict

Check if there's already a rule around line 3230:

```css
.watchlist-panel .panel-row--1m {
  grid-template-columns: 1fr !important;
}
```

If it exists but is NOT at the end of the file, comment it out and use the new block from 5.1 instead.

**Proof required:**
- Visual check: Watchlist panel shows rows stacked vertically, never side-by-side
- Verify 1m and 3m panels still show two columns

---

## INSTRUCTION 6: Lock hover colors to gold/purple (no green)

**File:** `frontend/src/index.css`

**Current variables (lines 4102-4107):**

```css
.board-core .bh-row[data-side="gainer"]:hover::after {
  background: linear-gradient(90deg,
    rgba(255,176,46,...) /* gold */
  );
  box-shadow: inset 0 0 0 1px rgba(255,176,46,...);
}

.board-core .bh-row[data-side="loser"]:hover::after {
  background: linear-gradient(90deg,
    rgba(150,110,255,...) /* purple */
  );
  box-shadow: inset 0 0 0 1px rgba(150,110,255,...);
}
```

**Verify:** No `rgba` values use green channels significantly higher than red/blue (no teal/mint contamination).

**Proof required:**
- Gold family: `rgba(255, 176, 46, ...)` or similar (R > G > B)
- Purple family: `rgba(150, 110, 255, ...)` or similar (B > R > G)
- NO values like `rgba(16, 174, 155, ...)` (mint/teal) in hover glass

---

## VERIFICATION CHECKLIST

After completing all instructions, run:

```bash
./frontend/scripts/verify_ui_contract.sh
```

Expected output:
```
PASS: Pseudo-element duplication seems controlled (after_count <= 6)
PASS: No legacy gain/loss selector families found (or banner-only)
PASS: data-side selectors exist for both gainer and loser
PASS: Authoritative hover marker found near end of file
PASS: CSS references --emit-x and --emit-y
PASS: CSS references data-row-hover gating
PASS: CSS references rabbit-bg
----
Total PASS: 7
Total FAIL: 0
```

If any FAIL remains, see the corresponding INSTRUCTION number and re-execute.

---

## FINAL PROOF

Update `docs/PLAN_UI_FIXES.md` with:
- Each completed instruction's status changed to "Done"
- Proof output pasted under each step
- Final verification score: 7/7 PASS
