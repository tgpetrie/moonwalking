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


_Repo_: `moonwalkings` • _SHA_: `58788672` • _Updated_: `2025-11-01T05:36:46Z`


_Repo_: `moonwalkings` • _SHA_: `83989331` • _Updated_: `2025-11-01T05:37:54Z`


_Repo_: `moonwalkings` • _SHA_: `b89b0cb6` • _Updated_: `2025-11-01T05:43:27Z`


_Repo_: `moonwalkings` • _SHA_: `b89b0cb6` • _Updated_: `2025-11-01T05:43:27Z`


_Repo_: `moonwalkings` • _SHA_: `b0e47195` • _Updated_: `2025-11-01T05:57:36Z`


_Repo_: `moonwalkings` • _SHA_: `6e258bbf` • _Updated_: `2025-11-01T15:02:54Z`


_Repo_: `moonwalkings` • _SHA_: `bdcc3ac1` • _Updated_: `2025-11-01T15:04:42Z`
