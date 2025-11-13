# AI Index (source of truth)
Project: BHABIT / CBMo4ers
Services: Flask :5001 • Bridge :5100 • Vite :5173

## 🔒 UI Canonical Spec
**READ THIS FIRST** before touching UI: `docs/UI_HOME_DASHBOARD.md`
- Defines BHABIT dashboard layout (1m hero, 3m side-by-side, watchlist)
- Two implementation paths: Path A (explicit panels) vs Path B (generic MoversPanel)
- Do NOT reintroduce legacy "BHABIT Crypto Dashboard / Alerts 25 NEW" header
- Current implementation: Path A with explicit components

## Entrypoints
- Frontend mount: `frontend/src/main.jsx` → `<AppRoot />` (hard-pinned)
- Do not use loader/token demos.

Docs map → `UI_HOME_DASHBOARD.md` (UI spec) • `ROUTES.md` • `DATA_SHAPES.md` • `ARCHITECTURE.md` • `WORKFLOWS.md` • `STYLE_GUIDE.md` • `CHANGELOG_AI.md`

Events: `gainers1m`, `gainers3m`, `losers3m`, `banner1h`, `vol1h`, `heartbeat`

Key modules: `frontend/src/components/Dashboard.jsx` • `frontend/src/components/GainersTable3Min.jsx` • `frontend/src/hooks/` • `frontend/src/lib/`

Ground rules: White screen = render exception; keep `frontend/index.html` stock; case-correct imports.


## Branch & Ownership Rules for AI / Copilot

If you are an AI / copilot acting on this repo, follow these rules exactly.

1. Do NOT push core UI work to AI branches

Never route core dashboard work to AI-only or experimental branches such as:
	•	exp/copilot-agent*
	•	ai-*
	•	any branch explicitly marked as “agent”, “ai”, or “prompt-sandbox”

These branches are for:
	•	docs/ai/* files
	•	agent prompts, instructions, and scaffolding
	•	internal AI helper scripts or experiments that are not part of the production UI

They are not for:
	•	`frontend/src/Dashboard.jsx`
	•	`frontend/src/AppRoot.jsx` / `App.jsx`
	•	`frontend/src/components/*` panels used in the home/dashboard layout
	•	`frontend/src/styles` / `index.css` that affect the live dashboard

2. Treat `Dashboard.jsx` as production, not AI playground

The file:
	•	`frontend/src/Dashboard.jsx`

is canonical home-dashboard layout. It:
	•	Fetches `/data`
	•	Wires the 1h price banner → 1m hero → 3m gainers/losers → volume banner
	•	Controls detail panels (e.g. AssetDetailPanel, insights, etc.)

If you modify this file, you must:
	1. Work on a normal app branch only, for example:
		•	`working913`
		•	`feature/dashboard-layout-*`
		•	`main` (via PR)
	2. Keep it consistent with `docs/UI_HOME_DASHBOARD.md`.
	3. Avoid moving it, renaming it, or relocating it into any `ai-*` / `exp/copilot-*` branch or folder.

3. Allowed AI changes by area

AI branches (`exp/copilot-agent*`, `ai-*`) may only contain:
	•	`docs/ai/AI_INDEX.md` and other AI-specific docs
	•	Agent configuration files and prompt templates
	•	Example scripts or stubs that are not imported into the live dashboard

Core app branches (e.g., `working913`, `feature/*`, `main`) must contain:
	•	`frontend/src/Dashboard.jsx`
	•	`frontend/src/AppRoot.jsx` / `App.jsx`
	•	Canonical components referenced in `UI_HOME_DASHBOARD.md`
	•	Canonical CSS/layout for the BHABIT dashboard

If you’re changing any of the above, you are doing app work, not AI infra, and you must commit it on a core app branch.

4. What to do if you’re on the wrong branch (AI instruction)

If you, as an AI assistant, detect that you’re on an `ai-*` / `exp/copilot-*` branch and about to edit core UI files (`Dashboard.jsx`, `AppRoot.jsx`, home panels, canonical CSS):
	1. Stop.
	2. Instruct the user (in your response) to:
		•	stash changes,
		•	switch to a proper app branch (e.g., `working913`),
		•	then re-apply the changes there.
	3. Only suggest git commands like:

```
git stash push -m "dashboard ui work"
git checkout working913
git stash pop
```

Do not suggest committing core UI changes to the AI branch.

5. Tie-in with `UI_HOME_DASHBOARD.md`

For any AI / copilot:
	•	`docs/UI_HOME_DASHBOARD.md` is the UI law.
	•	`docs/ai/AI_INDEX.md` is how you, the AI, should behave.
	•	When in doubt:
		•	UI behavior, layout, components → edit on core app branch, keep aligned with `UI_HOME_DASHBOARD.md`.
		•	Agent behavior, prompts, metadata → edit on AI branch (exp/copilot-agent*).

If a change affects the home dashboard users see, it belongs on the app branch, not the AI branch.

---

For AI / copilot behavior and branch rules, also see `docs/UI_HOME_DASHBOARD.md` – Branch & Ownership Rules for AI / Copilot.

_Repo_: `moonwalkings` • _SHA_: `58788672` • _Updated_: `2025-11-01T05:36:46Z`


_Repo_: `moonwalkings` • _SHA_: `83989331` • _Updated_: `2025-11-01T05:37:54Z`


_Repo_: `moonwalkings` • _SHA_: `b89b0cb6` • _Updated_: `2025-11-01T05:43:27Z`


_Repo_: `moonwalkings` • _SHA_: `b89b0cb6` • _Updated_: `2025-11-01T05:43:27Z`


_Repo_: `moonwalkings` • _SHA_: `b0e47195` • _Updated_: `2025-11-01T05:57:36Z`


_Repo_: `moonwalkings` • _SHA_: `6e258bbf` • _Updated_: `2025-11-01T15:02:54Z`


_Repo_: `moonwalkings` • _SHA_: `bdcc3ac1` • _Updated_: `2025-11-01T15:04:42Z`
