# AI Index (source of truth)
Project: BHABIT / CBMo4ers
Services: Flask :5001 • Bridge :5100 • Vite :5173
Entrypoints
- Frontend mount: `frontend/src/main.jsx` → `<Dashboard />` (hard-pinned)
- Do not use loader/token demos.

Docs map → `ROUTES.md` • `DATA_SHAPES.md` • `ARCHITECTURE.md` • `WORKFLOWS.md` • `STYLE_GUIDE.md` • `CHANGELOG_AI.md`

Events: `gainers1m`, `gainers3m`, `losers3m`, `banner1h`, `vol1h`, `heartbeat`

Key modules: `frontend/src/components/Dashboard.jsx` • `frontend/src/components/GainersTable3Min.jsx` • `frontend/src/hooks/` • `frontend/src/lib/`

Ground rules: White screen = render exception; keep `frontend/index.html` stock; case-correct imports.


_Repo_: `moonwalkings` • _SHA_: `58788672` • _Updated_: `2025-11-01T05:36:46Z`
