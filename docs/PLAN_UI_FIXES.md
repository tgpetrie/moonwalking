# PLAN_UI_FIXES — Shared Checklist (Claude = Auditor)

Scope: Minimal, surgical edits only. No refactors. No new components. UI_CONTRACT unchanged unless explicitly stated.

## Rules of engagement
- No refactors. No new components. Minimal, targeted edits only.
- UI_CONTRACT stays untouched unless a step explicitly says otherwise.
- One source of truth for hover hue: only:
  - .bh-row[data-side="gainer"]
  - .bh-row[data-side="loser"]
- "Done" requires proof: file paths + what to verify + command output when applicable.
- Cascade discipline: final authoritative rules must live at the end of frontend/src/index.css

## Status key
- Todo / Doing / Done / Blocked

---

## 0) Baseline capture

### 0.1 Record current state
Status: Done
Goal: Freeze a before/after snapshot so improvements are provable.
Proof required:
- git rev-parse HEAD
- git status --short
- git diff --stat

Notes:
- Commit: 92886e974aa30c6550daacd6681cbc8cd25700b4
- Status: M frontend/src/index.css, ?? docs/UI_CONTRACT.md, ?? docs/PLAN_UI_FIXES.md, ?? frontend/scripts/verify_ui_contract.sh, ?? docs/VERIFY_UI_FIXES.md
- Diff: frontend/src/index.css | 141 insertions(+)

### 0.3 Baseline verification run
Status: Done
Goal: Establish current failure state
Command: ./frontend/scripts/verify_ui_contract.sh
Results (after script bug fix):
- FAIL: Too many .bh-row::after occurrences (20 found, expected <= 6)
- FAIL: Legacy gain/loss selector families present (is-gain, is-loss, bh-row--gain, bh-row--loss)
- PASS: data-side selectors exist
- FAIL: No authoritative hover marker near file end
- PASS: CSS references --emit-x and --emit-y
- PASS: data-row-hover gating present
- PASS: rabbit-bg present
Score: 4 PASS / 3 FAIL

Next: Execute INSTRUCTIONS_FOR_CODEX.md (instructions 1-6)

### 0.2 Confirm app boots
Status: Todo
Goal: Confirm dev servers run and UI renders.
Proof required:
- "No white page"
- "No console errors"
- Command used to start dev + confirmation it's running

---

## 1) CSS sanity: eliminate selector wars

### 1.1 Inventory ALL competing row pseudo rules
Status: Done
Goal: Find every bh-row pseudo-element rule and map conflicts.
Targets:
- .bh-row::after
- .bh-row:hover::after
- .bh-row::before
- .bh-row:hover::before
- any selector family referencing gain/loss:
  - is-gain, is-loss
  - bh-row--gain, bh-row--loss
  - data-side="gainer"/"loser"

Proof required:
- Conflict map (file order) listing:
  - selector
  - what it controls (rail, hover fill, glass, mask, box-shadow, backdrop-filter)
  - whether it uses !important
- Explicit duplicate callouts
- Identify "final/authoritative/last" blocks that are not actually last in the file

Findings:
- 20+ .bh-row::after occurrences
- 6 .bh-row::before occurrences
- Multiple "FINAL/AUTHORITATIVE" blocks that are NOT last
- Selector families mixed: is-gain, is-loss, bh-row--gain, bh-row--loss, data-side

### 1.2 Enforce attribute-only hue targeting
Status: Todo
Goal: Ensure only data-side attrs control gain/loss hue.
Allowed hue selectors:
- .bh-row[data-side="gainer"] …
- .bh-row[data-side="loser"] …

Proof required:
- grep/rg output showing no other selector family changes hue
- Confirmation legacy selectors are either neutralized or mapped to attribute logic without affecting hue

### 1.3 Ensure masked inner-glass hover is final
Status: Todo
Goal: Ensure the intended "masked inner-glass hover" behavior is the cascade winner.
Must be controlled in the final authoritative block (end of file):
- rail (::before)
- hover glass (::after)
- mask-image/backdrop-filter/box-shadow outcome

Proof required:
- Show final authoritative block (end of frontend/src/index.css)
- Confirm no later overrides exist for those selectors/properties

---

## 2) Watchlist layout contract

### 2.1 Confirm watchlist row structure matches tables
Status: Todo
Goal: Watchlist rows share .bh-row structure and data-side wiring.
Proof required:
- File path + excerpt of row markup/classes showing .bh-row usage and data-side

### 2.2 Force watchlist single-column (scoped, unbreakable)
Status: Todo
Goal: Watchlist rows are forced single-column always, regardless of 1m grid rules.
Constraint:
- Minimal CSS edits only unless a missing class hook makes it impossible.
Preference:
- Scoped selector that wins by specificity + being last.

Proof required:
- Exact selector added + why it wins (specificity + order)
- Confirm no impact to 1m/3m panels

---

## 3) Rabbit spotlight contract (JS drives CSS, not hope)

### 3.1 Verify emitter variables + hover flag are real and connected
Status: Todo
Goal: DashboardShell (or equivalent) sets:
- --emit-x, --emit-y
- data-row-hover="1"

Proof required:
- File path + code excerpt where vars and attribute are set
- Confirm event delegation selector matches real row classes (e.g., .bh-row)

### 3.2 Implement spotlight reveal in CSS using those vars
Status: Todo
Goal: Rabbit is nearly invisible by default; revealed locally near pointer only on row hover.
Constraints:
- No slab fill
- Localized mask centered at (--emit-x, --emit-y)
- No new assets

Proof required:
- Final CSS block at end of file showing spotlight mask logic
- Visual verification note: invisible idle -> localized reveal on hover

---

## 4) Hover colors: gold for gainers, purple for losers, never greenish

### 4.1 Audit variables used for hover glow and rails
Status: Todo
Goal: Identify which vars feed hover glow and rails and what their actual values are.
Proof required:
- List of vars -> actual RGBA/HSLA sources used

### 4.2 Lock gain to gold family, loss to violet family
Status: Todo
Goal:
- gainer hover uses gold family
- loser hover uses violet family
- no accidental green/teal cast in hover glow rails

Proof required:
- Exact CSS values used
- Quick screenshot notes or manual check notes

---

## 5) Banner speed lock (top + bottom match)

### 5.1 Confirm both banners share the same speed contract
Status: Todo
Goal: TopBannerScroll and VolumeBannerScroll move at the same perceived speed.
Proof required:
- Identify whether both use:
  - CSS duration (e.g., --bh-banner-duration), or
  - manual px/sec (requestAnimationFrame)
- If mismatched, propose smallest change to unify

### 5.2 Hover pause parity
Status: Todo
Goal: Both banners pause on hover (or both don't), using the same rule.
Proof required:
- Code excerpt or CSS rule showing hover pause behavior in both

---

## 6) Prove no regressions

### 6.1 Console clean
Status: Todo
Proof required:
- No console errors

### 6.2 No white page / layout collapse
Status: Todo
Proof required:
- App renders reliably after restart

### 6.3 Mint price only where intended
Status: Todo
Proof required:
- Mint only on current price, not previous price

### 6.4 Row alignment contract holds
Status: Todo
Proof required:
- token left aligned
- numbers right aligned
- tight price/% spacing
- star/info has room without drifting layout

---

## 7) Lightweight verification artifact

### 7.1 Add verification script or doc snippet (no test frameworks)
Status: Todo
Goal: Produce PASS/FAIL checks for:
- Single authoritative hover block exists at bottom
- Only data-side selectors control hue
- Rabbit spotlight selectors present and linked to data-row-hover/emit vars

Proof required:
- File path for script/doc + sample output
