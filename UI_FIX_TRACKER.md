# UI Fix Tracker (scope: small UI parity only)

## Non-negotiables
- Do NOT touch Intelligence Log / terminal panel styles or markup.
- Do NOT change rabbit layering/placement.
- No new components. No refactors. No layout changes.
- No blur, no filter, no drop-shadow, no backdrop-filter.
- Motion is **opacity + transform only**.
- Motion must be implemented via **existing Framer Motion** (preferred), not new CSS animation systems.
- CSS may be used only for hover-glow visuals and reduced-motion fallbacks.
- Allowed edits: global CSS + minimal row/table markup to share canonical hooks + small edits to existing motion props/variants.

## Goal
Bring hover glow + always-on micro motion parity to:
- 1m table (reference: already correct)
- 3m gainers table
- 3m losers table
- top scrolling banner items
- bottom volume banner items

Exclude:
- Intelligence Log (no hover glow parity work, no micro motion changes)

## Checklist (single source of truth)

### A) Hover glow parity (glassy “lasso” feel, no slab)
- [ ] A0: Identify canonical row hook used by the 1m table (class + data attrs).
	Output needed: exact selector(s) that currently drive the glow for 1m.
- [ ] A1: Identify row wrapper + class/attrs for 3m gainers and 3m losers.
	Goal: confirm whether they use the same row component or different ones.
- [ ] A2: Identify banner item wrapper + class/attrs for:
	- top banner
	- bottom volume banner
- [ ] A3: Unify eligible rows/items to one canonical hook:
	- same row class (ex: `.mw-row`) and
	- same state attr (ex: `[data-state="gain|loss"]` or `[data-side="gain|loss"]`)
	Only minimal markup edits allowed (add class/attr, do not restructure).
- [ ] A4: CSS parity: ensure the hover-glow effect triggers from the canonical hook
	across 3m tables + both banners.
	Constraints:
	- No background fill “slab"
	- No blur/filter/shadows
	- Keep rails/lines sharp
	- Glow should feel like a selection lasso: transparent center, subtle rim/tint
- [ ] A5: Verify visually:
	- hover glow works on 1m, 3m gainers, 3m losers, top banner items, bottom banner items
	- NO change in Intelligence Log
- [ ] A6: Regression guard:
	- confirm hover glow does not introduce borders or container fills
	- confirm rabbit silhouette brightens naturally through the hover state

### B) Always-on micro motion parity (FRAMER-FIRST)
- [ ] B0: Locate where micro motion is defined today (Framer Motion props/variants).
	Search strings:
	- `motion.`
	- `animate=`
	- `variants`
	- `transition`
	- `repeat`
	- `repeatType`
- [ ] B1: Identify which tables/banners currently use micro motion and which do not.
	Target IN:
	- 3m gainers rows
	- 3m losers rows
	- top banner items
	- bottom volume banner items
	Exclude:
	- Intelligence Log
- [ ] B2: Unify to one canonical micro-motion contract (same variant/transition)
	reused by all eligible rows/items.
	Constraints:
	- constant (always-on), not hover-dependent
	- only opacity + transform
	- avoid scale on the whole row if it fuzzes rails; prefer tiny y drift + per-cell offsets
- [ ] B3: Strength pass (make it more visible without becoming jittery):
	Tune ONLY these knobs:
	- translateY amplitude: ~0.6–1.2px (avoid >2px)
	- opacity pulse range: ~0.92–1.00
	- duration: ~4.5–6.5s (slower reads cleaner)
	- stagger: per-cell delay 0.06–0.14s (if per-cell exists)
- [ ] B4: Reduced motion:
	- if `prefers-reduced-motion`, disable motion (Framer + any CSS fallback)
- [ ] B5: Verify visually:
	- micro motion is present on 1m + 3m + both banners
	- unchanged/absent in Intelligence Log

## Proof steps (must pass twice)
- [ ] P1: `./start_app.sh` runs clean
- [ ] P2: Open UI → confirm hover glow works on 1m, 3m, top banner, bottom banner
- [ ] P3: Confirm micro motion visible on 1m, 3m, banners (constant, subtle, stronger than before)
- [ ] P4: Confirm NO hover glow/motion changes in Intelligence Log
- [ ] P5: Restart and confirm same behavior (no regress)

## “Done means proven” rules
A checkbox is only checked if:
- the code change exists, AND
- you visually verified it in the UI, AND
- it did not violate Non-negotiables.

## Notes / Findings
- Row hook (1m): 
- Row hook (3m gainers):
- Row hook (3m losers):
- Banner hook (top):
- Banner hook (bottom):
- Motion source file(s):
- Any gotchas discovered:

If you want, I can also give you a second file, AI_WORK_ORDER.md, that’s a strict template you paste into Claude/Codex every time (so they can’t wander).

