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

# PR: Stability tranche (baselines + banner sorting + endpoint-drift gates)

Stability
- Backend rows now run through `_null_if_nonpositive` before slicing so any `previous_price`, `initial_price_*`, or `price_*_ago` that isn’t `> 0` becomes `null`, and the core slices (`banner_1h_price`, `banner_1h_volume`, `gainers_1m`, `gainers_3m`, `losers_3m`) are emitted via the aggregate endpoint **`/data`**.
- The 1h price/volume banner builders compute percent deltas via `_safe_float`, drop anything that isn’t a finite non-zero float, and sort using `_sort_rows_by_numeric` so “top mover” strips are deterministic and `None`-safe.
- Frontend rendering now shares a single sanitizer (`frontend/src/utils/num.js`) and applies it in row/cell renderers so baselines consistently map `null → "—"` and never feed percent math with zeros.
- Gates hardened against endpoint drift:
  - Gate A: `scripts/verify_no_zero_baselines.sh` auto-detects the correct aggregate endpoint.
  - Gate B: `backend/test_baselines_unittest.py` supports `BASELINE_PATH` and auto-selects a JSON endpoint with rows when unset.

Data contract
 - Baseline fields (`previous_price`, `initial_price_*`, `price_*_ago`) must be either a positive float or `null`.
 - `0` is treated as “missing” and must not be emitted by the backend nor used in percent math on the frontend.
 - Banner percent fields must be a finite non-zero float, otherwise the row is omitted from the banner slice.

Tests
- `python3 -m py_compile backend/app.py`
- `PYTHONPATH=. backend/.venv/bin/python -m unittest -q backend.test_baselines_unittest` (or `BASELINE_PATH=/data ...` when needed)
- `npm --prefix frontend run build`

One-liner Debug
```bash
curl -sS -m 15 http://127.0.0.1:5001/data \
  | jq '{fatal:(.errors.fatal // null), coverage:(.coverage // {}), b1p:((.banner_1h_price // [])|length), b1v:((.banner_1h_volume // [])|length)}'
```

Next Steps (real host, Coinbase reachable)
1. Start backend and confirm the actual port in logs (this workspace commonly uses **`:5001`**).
2. Verify aggregate returns and no fatal errors:
   ```bash
   curl -sS -m 15 http://127.0.0.1:5001/data | jq -r '.errors.fatal'
   curl -sS -m 15 http://127.0.0.1:5001/data | jq '{banner_1h_price: (.banner_1h_price|length), banner_1h_volume: (.banner_1h_volume|length), gainers_1m: (.gainers_1m|length), gainers_3m: (.gainers_3m|length), losers_3m: (.losers_3m|length)}'
   ```
3. Run gates (use **`/data`** as canonical; `/api/data` is legacy/optional and may be absent in this workspace):
   ```bash
   bash scripts/verify_no_zero_baselines.sh http://127.0.0.1:5001/data
   BASELINE_PATH=/data PYTHONPATH=. backend/.venv/bin/python -m unittest -q backend.test_baselines_unittest
   ```

Suggested commit title
- `fix(stability): guard baselines and banner sorting`
Notes
