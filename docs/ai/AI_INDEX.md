# AI Index (source of truth)
Project: BHABIT / CBMo4ers
Services: Flask :5001 • Bridge :5100 • Vite :5173

## CBMOOVERS_DASHBOARD_GUARDRAILS

Scope: CBMoovers / BHABIT home dashboard (1m gainers, 3m gainers/losers, top/bottom banners, watchlist, bunny layer, sentiment/info panel).

**Source-of-truth docs (MUST follow):**
- `docs/FRONTEND_UI_RULES.md`
- `docs/DATA_PIPELINES.md`

If existing code disagrees with these docs, assume the **docs are correct** and update the code to match them — not the other way around.

---

### 1. Layout & Grid – Board Home

When changing ANYTHING in the home board layout:

- Do **NOT** introduce new layout systems for the board.
- Allowed board wrappers (and only these):
	- `.bh-board`
	- `.bh-board-row-full`
	- `.bh-board-row-halves`
	- `.bh-board-panel`
- All token rows (1m, 3m, watchlist) must use the **canonical** row grid:
	- Implemented in `TokenRow.jsx` / `AnimatedTokenRow.jsx`
	- CSS owner is `.bh-row` in `frontend/src/index.css`
- You may adjust numeric grid values (column widths, padding) **inside** `.bh-row`, but:
	- Do **NOT** create per-table `grid-template-columns`.
	- Do **NOT** add random width overrides on individual tables.

**If columns are misaligned:**
- Fix `.bh-row` and the board wrappers.
- Do not create one-off hacks inside individual table components.

---

### 2. Data & Endpoints – Board Fetching

All board data must flow through the existing API helpers and hooks:

- Frontend API helper:
	- `frontend/src/api.js`
- Frontend hooks:
	- `frontend/src/hooks` (e.g. `useBoardData`, `useDataFeed`, or equivalent)

**HTTP endpoints:**

- Primary board endpoint:
	- `GET /data` (same-origin, via Vite dev proxy)
- `/api/data` is a **backend alias / fallback** only.
	- Do **NOT** hard-code `http://127.0.0.1:5001/...` in React code.
	- Use relative URLs passed through the existing API helper.

**SWR / REST / CORS rules:**

- Use the **existing** SWR hook layer. Do not reinvent the fetch loop.
- Board components should consume data via the hook, not call `fetch` directly.
- CORS is a fallback concern; the normal dev/production path is:
	- Browser → SPA → relative path `/data` → Vite proxy → Flask backend.

If you need a new board-level data field:
- Add it to the backend `/data` payload.
- Document it in `docs/DATA_PIPELINES.md`.
- Then surface it via `api.js` + the existing hook.

---

### 3. Feature-Specific UI Rules

#### 3.1 1-Minute Gainers

- Exactly **one** component: `GainersTable1Min.jsx`.
- It chooses layout mode based on `items.length`:
	- `items.length <= 4` → full-width, single column (`.bh-board-row-full`).
	- `items.length > 4` → two columns (`.bh-board-row-halves`), left + right split.
- Both modes:
	- Use the canonical `.bh-row` grid via `TokenRow` / `AnimatedTokenRow`.
	- Must show both:
		- `current_price`
		- `price_1m_ago` (previous price), with correct BHABIT colors.
- Do **NOT** create a second 1m component. Layout mode is a **branch inside** `GainersTable1Min`.

#### 3.2 3-Minute Gainers / Losers

- Live together in a single `.bh-board-row-halves` block:
	- Left `.bh-board-panel`:
		- Header: `Top Gainers (3m)`
		- Body: 3m gainers table
	- Right `.bh-board-panel`:
		- Header: `Top Losers (3m)` with losers color (`.bh-section-header--losers`)
		- Body: 3m losers table
- Both sides:
	- Use `.bh-row` via `TokenRow` / `AnimatedTokenRow`.
	- No per-table grid definitions.

#### 3.3 Watchlist

- Always full width **under** the 3m grid:
	- Wrapper: `.bh-board-row-full` + `.bh-board-panel`.
- Data:
	- Watchlist symbols from `WatchlistContext`.
	- Price/details from `latest_by_symbol` in the board payload.
- Do **NOT** introduce duplicate watchlist state.

#### 3.4 Banners (1h Price, 1h Volume)

- Use a shared banner component (e.g. `BannerTicker`) for:
	- 1h Price Change
	- 1h Volume
- Both banners:
	- Live in `.bh-board-row-full` + `.bh-board-panel`.
	- Do **NOT** use `.bh-row`; they are chip-based tickers.
- No visible pill outline; styling matches the BHABIT spec.
- Chip click uses the `trade_url` field in the data payload.

---

### 4. Sentiment & Info Button

- The info icon in each row is wired into the sentiment system:
	- Must use the existing context/hook layer (e.g. `SentimentContext`).
	- Fetches from the sentiment endpoint(s) specified in `docs/DATA_PIPELINES.md`.
- Do **NOT**:
	- Invent new sentiment endpoints from the board.
	- Bypass the context layer with direct `fetch` calls.
- All sentiment logic (data shape, scoring) must match `docs/DATA_PIPELINES.md`.

---

### 5. Motion, Stagger, Bunny

- Motion:
	- Use `AnimatedTokenRow = motion(TokenRow)` with `forwardRef`.
	- Use the shared variants file (`motionVariants.js` or equivalent).
	- Apply stagger at the table wrapper level, not per-row layout.
- Bunny layer:
	- Implemented as `.bh-bunny-layer` behind the 1m + 3m block.
	- Visual only; must not influence layout or row spacing.

---

### 6. Absolute “Do Not” List

When editing the board:

- Do **NOT**:
	- Add new layout wrappers outside the `.bh-board*` + `.bh-row` system.
	- Define new grid systems per table.
	- Hard-code backend hosts/ports in React (`http://127.0.0.1:5001/...`).
	- Create duplicate 1m/3m/watchlist components.
	- Add new sentiment endpoints from the frontend.

If you cannot make a change while respecting:
- `docs/FRONTEND_UI_RULES.md` and
- `docs/DATA_PIPELINES.md`

…then **do not modify the board**.

Drop those in, save, and any agent that ignores them is just telling on itself. (See <attachments> above for file contents. You may not need to search or read the file again.)


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
