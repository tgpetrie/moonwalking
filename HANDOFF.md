# HANDOFF

## Snapshot

- Date: 2026-03-11
- Current branch: `main`
- Repo purpose: BHABIT Moonwalking is a React + Vite frontend and Flask backend for a live crypto tracking dashboard with alerts, movers, watchlist/insights tooling, and an in-progress product-shell pivot toward account-backed, cross-device watchlists.

## Important recent work

### 1. MVP shell for cross-device watchlists

- Commit: `3155fc5a` - `Add MVP watchlist product shell`
- What changed:
  - `frontend/src/App.jsx` now boots a routed MVP shell instead of the old single-screen entry.
  - `frontend/src/mvp/MvpApp.jsx` added page layouts for `/`, `/login`, `/signup`, `/dashboard`, `/watchlists`, `/portfolio`, `/settings`, and `/u/:username`.
  - `frontend/src/styles/mvp-shell.css` added the new public/member UI system and responsive shell styling.
- Important constraint:
  - This work is still UI-only and in-memory. The watchlists, session, profile, and settings state in `frontend/src/mvp/MvpApp.jsx` are seeded `useState` data, not backend-authenticated persistence.

### 2. Dashboard cue and alert layout lane that still matters

- Commit: `17c9cbb6` - `feat(frontend): add row cue hierarchy and alert layout pass`
  - Added `frontend/src/utils/rowCue.js`.
  - Reworked cue wiring and layout across `frontend/src/components/DashboardShell.jsx`, `frontend/src/components/TokenRowUnified.jsx`, `frontend/src/components/GainersTable1Min.jsx`, `frontend/src/components/GainersTable3Min.jsx`, `frontend/src/components/LosersTable3Min.jsx`, `frontend/src/components/AlertsTab.jsx`, `frontend/src/components/SentimentPopupAdvanced.jsx`, `frontend/src/index.css`, `frontend/src/styles/alerts-tab.css`, and `frontend/src/styles/sentiment-popup-advanced.css`.
- Commit: `8eab79f5` - `snapshot: canonical board override (minimal CSS)`
  - Tightened the canonical board styling in `frontend/src/index.css`.
- Commit: `7420683d` - `feat(frontend): replace cue emojis with SVG-based indicators`
  - Replaced emoji cues with SVG-based indicators in `frontend/src/utils/rowCue.js` and updated `frontend/src/components/DashboardShell.jsx`.

## Files that matter most right now

- `frontend/src/mvp/MvpApp.jsx`
  - Current MVP shell, route handling, seeded watchlist/profile/session state, and the watchlists page interactions.
- `frontend/src/styles/mvp-shell.css`
  - Visual system for the new MVP product shell.
- `frontend/src/App.jsx`
  - Current frontend entrypoint now routed to the MVP shell.
- `frontend/src/index.css`
  - Canonical styling for the legacy dashboard/board and the cue-related overrides from the March 8-9 work.
- `frontend/src/components/DashboardShell.jsx`
  - Main legacy dashboard composition layer and cue integration point.
- `frontend/src/utils/rowCue.js`
  - Row cue hierarchy and SVG indicator logic.
- `backend/watchlist.py`
  - Existing watchlist API is process-local and unauthenticated; this is not usable for true cross-device persistence.
- `backend/app.py`
  - Flask app entrypoint and the place where real auth/persistence wiring will need to live.
- `frontend/src/context/WatchlistContext.jsx`
  - Old localStorage-based watchlist provider; useful reference for what exists today and what must not remain the source of truth for cross-device sync.

## Persistence reality check

- The new MVP shell does not yet load or save watchlists through the backend.
- `frontend/src/mvp/MvpApp.jsx` uses in-memory React state only.
- `frontend/src/context/WatchlistContext.jsx` still shows the old browser-localStorage pattern.
- `backend/watchlist.py` currently uses `watchlist_db = set()` with no users, no auth, no sessions, and no durable storage.
- Result: there is still no true authenticated cross-device persistence for watchlists.

## Next exact step

Implement user-scoped persistent watchlist CRUD in the Flask backend before adding more shell UI:

1. Replace the process-local `watchlist_db = set()` in `backend/watchlist.py` with a real store keyed by user.
2. Add authentication/session handling so the backend can identify the current user on every watchlist request.
3. Expose authenticated `/api/watchlists` CRUD that supports:
   - list watchlists for current user
   - create/rename/delete watchlists
   - add/remove/update watchlist items and notes
   - load/save profile metadata if you want `/portfolio` to persist in the same pass
4. After that backend exists, swap `frontend/src/mvp/MvpApp.jsx` off seeded `useState` data and onto fetch/mutation calls against those endpoints on login and edit.

If choosing the lowest-friction path inside this repo, the first code change should be: add a persistent backend watchlist store module plus authenticated `/api/watchlists` routes, then wire the frontend shell to it.

## Resume prompt for another device

Read `HANDOFF.md`, then inspect commits `3155fc5a`, `17c9cbb6`, `8eab79f5`, and `7420683d`. Keep the dashboard cue work intact, but make the new MVP shell real by replacing the in-memory watchlist state in `frontend/src/mvp/MvpApp.jsx` and the process-local store in `backend/watchlist.py` with authenticated backend persistence for cross-device watchlists.
