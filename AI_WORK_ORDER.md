## Prime directive
Use `UI_FIX_TRACKER.md` as the single source of truth.
Do **not** work on anything outside its scope.

If you (the AI) are unsure whether a change is in-scope, stop and return only:
- what you inspected
- what you found
- which checklist item it maps to

## Roles
- Claude = planner/auditor (identify files + minimal plan, no edits unless explicitly asked)
- Codex/Copilot = executor/surgeon (patch-only, minimal diffs, verify, update tracker)

## Non-negotiables (repeat)
- Do NOT touch Intelligence Log / terminal panel styles or markup.
- Do NOT change rabbit layering/placement.
- No new components. No refactors. No layout changes.
- No blur, no filter, no drop-shadow, no backdrop-filter.
- Motion is **opacity + transform only**.
- Micro motion should be implemented via existing **Framer Motion** (preferred).
- Allowed edits: global CSS + minimal markup to apply canonical hooks + small edits to existing motion props/variants.

## Session workflow (must follow)
### 0) Start state (required)
Return these outputs first:
- `git status -sb`
- `git diff --stat`

If the tree is not clean, say exactly what files are dirty and why they should/shouldn’t be committed.

### 1) Scope lock
State the next 1–3 checklist items you are working on (ONLY those items).
Example:
- Working items: A1, A2, A3
- Not working: everything else

### 2) Locate (no edits yet)
For each item, list:
- exact file paths
- exact search strings you used
- exact selectors/classnames/attrs found

### 3) Patch (minimal)
Make only the smallest changes needed to complete the chosen items.

Constraints for patching:
- Prefer adding a shared class/attr over rewriting markup.
- Prefer reusing an existing Framer Motion variant/transition over inventing a new animation system.
- Any CSS added must be tied to a single canonical selector that affects only the eligible tables/banners.

### 4) Verify (must be explicit)
You must verify in two layers:
1) Static verification
   - `git diff` shows only expected files.
2) Runtime verification
   - run `./start_app.sh`
   - confirm the expected UI behaviors (hover glow + micro motion) in the correct places
   - confirm Intelligence Log is unchanged

If runtime verification is not possible, do not check the box—note it as “implemented but unverified”.

### 5) Update tracker
Update `UI_FIX_TRACKER.md`:
- check only boxes that are truly verified
- add “Notes / Findings” (selectors, files, what changed)

### 6) Commit discipline
Commit only if:
- changes are in-scope
- tracker updated
- verification performed

Commit message format:
`ui: hover glow parity + micro motion parity (tables+banners)`

## Output format (required)
When you finish a patch, respond with:
1) ✅ Items completed (which checklist boxes checked)
2) Files changed (list)
3) What was verified (exactly what you looked at)
4) What remains (next 1–3 items to do)
