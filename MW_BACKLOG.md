# Moonwalkings Living Backlog (MW_BACKLOG)

This file is the living work queue.
Rules live in MW_SPEC.md.

Status keys
- Open
- In progress
- Done
- Blocked

Owners
- Codex: implements patches
- Claude: plans and guards against regressions
- Gemini: verifier only (runs checks, confirms behavior, reports)


## Done (locked)
- Rabbit watermark centered + bloom hover correct (mark Done only if confirmed in current build)


## P0 (Open now)

[ ] P0.1 Two boards seam fix (includes rails alignment + spacing contract)
Owner: Codex
Scope: unify the page under one canonical board wrapper/grid so there is no tint split/seam; ensure Watchlist + Intelligence align under same rails and the vertical rhythm is consistent.
Definition of Done:
- Page is one continuous background/overlay stack (no mid-page seam).
- Watchlist + Intelligence align to table rails under the same wrapper.
- Clear spacing between: banners -> 1m -> 3m -> bottom banner/panels.
Verification:
- Scroll top to bottom: no seam, no overlay shift.
- Screenshot: edges line up across sections.

[ ] P0.2 Alerts system restore: real Moonwalking alerts only (no trend/score)
Owner: Codex
Scope: alerts data source + Alerts panel UI + Intelligence Log rendering
Definition of Done:
- Floating Alerts button shows unread count only; no toasts/popups cover the board.
- Clicking opens a glass drawer/panel matching Sentiment panel design language.
- Alerts show only main Moonwalking alert taxonomy types (no trend/score feed anywhere).
- Alerts can be organized/grouped by taxonomy category.
- Intelligence Log renders the same alert objects in its matrix/list style (no card redesign).
- Alert rows include: symbol (no -USD), age/timestamp, type/severity chips, message, Advanced Trade link.
Verification:
- Badge increments as alerts arrive; Mark read works; Clear works.
- Panel count equals Intelligence Log count in the same moment.
- Click 10 Advanced Trade links: correct pairs.

[ ] P0.3 3m movers reliability (3m is lacking)
Owner: Codex
Scope: baseline windows + cadence + fallback method if needed
Definition of Done:
- 3m gainers and losers reliably populate (not stuck sparse) during normal conditions.
- 3m values are computed from real baselines and remain stable under publish cadence.
Verification:
- /data shows reasonable counts for gainers_3m and losers_3m.
- Values persist across several minutes without collapsing to tiny lists.


## P1 (Next)

[ ] P1.1 Sentiment truth audit (no fake defaults, per-symbol correctness)
Owner: Codex
Scope: ensure per-symbol lookup is used; offline states are honest; remove any null->0.5 normalization presented as signal.
Definition of Done:
- Different symbols can show different sentiment when available.
- When missing: UI shows OFFLINE/UNAVAILABLE/STALE with timestamps; no fake midpoint.
Verification:
- Spot check several symbols; confirm no cloned panels.

[ ] P1.2 Watchlist truth audit (baseline + dedupe + full rails)
Owner: Codex
Scope: baseline at add time, no duplicates, full rails alignment, renders through brief data blips
Definition of Done:
- Watchlist change-since-added is correct and stable.
- No duplicate product_id.
- Visual alignment matches tables.
Verification:
- Add/remove several assets; verify baseline stays fixed and math is consistent.


## Intake (paste new tasks here)
Template:
[ ] P?.? Title
Owner:
Scope:
Definition of Done:
Verification:


⸻
