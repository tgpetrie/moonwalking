# PR: Consolidate active hover CSS & preserve legacy hover rules

What changed
- Consolidated active hover and row styles into `frontend/src/index.css`:
  - single `:root` for brand tokens
  - unified section headers/underlines
  - `.table-row` base rule with `row-breathe` animation and hover zoom
  - new `.row-hover-glow`, `.row-hover-glow-gain`, `.row-hover-glow-loss`
- Moved older `.row-hover-foot*` rules out of the active stylesheet into `frontend/src/legacy-hover.css` (not imported). This preserves the legacy shapes for reference without adding runtime CSS.
- Wired the app to use `useUnifiedData()` and passed `data.gainers_1m`, `data.gainers_3m`, `data.losers_3m` into the panels. Components now use a single `TokenRow.jsx`.
- Added a tiny script in `frontend/package.json` to detect accidental re-introduction of legacy selectors:
  - `npm --prefix frontend run lint:css:legacy` → `grep -R "row-hover-foot" src || true`

Why
- Remove dead CSS that is no longer used and reduce confusion.
- Keep the legacy rules in the repo for quick reference without loading them in the app.
- Unify styles so hover behavior (glow) is consistent across panels.

How to test locally
1. Start backend (if not running):
   ```bash
   # backend
   cd backend
   # run your python server as you normally do (e.g., `python app.py`)
   ```
2. Start frontend dev server (keep terminal open):
   ```bash
   VITE_PORT=5173 BACKEND_PORT=5001 npm --prefix frontend run dev -- --host 127.0.0.1 --port 5173
   # if Vite auto-selects another port, open the exact Local URL it prints (e.g., http://127.0.0.1:5174/)
   ```
3. Verify visually:
   - Hover rows in 1-min and 3-min panels (gain & loss): you should see the long, soft glow (.row-hover-glow) under the row.
   - No diamond/foot-shaped glow should appear.
   - Watchlist should load without `useWebSocket` provider errors.

Automated checks to run
- Frontend build:
  ```bash
  npm --prefix frontend run build
  ```
- Lint for legacy selectors:
  ```bash
  npm --prefix frontend run lint:css:legacy
  ```

Rollback / recovery
- Legacy rules are preserved in `frontend/src/legacy-hover.css` and this branch — you can re-introduce them quickly if needed. Git history also preserves previous states.

Notes
- The `lint:css:legacy` script currently greps the `src` folder. We can add this step to CI to fail PRs that reintroduce the legacy class.
