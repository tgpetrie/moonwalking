Frontend UI rules — enforced layout

Purpose
- Keep layout rails stable and predictable. Do not change `.bh-row`, `.bh-board-row-*`, or the 1m two-mode layout without approval.

Rules
- Canonical grid lives in `frontend/src/index.css` under the `.bh-` namespace.
- `TokenRow` is the single source of truth for row structure. Use only its props: `rank`, `symbol`, `name`, `currentPrice`, `previousPrice`, `percentChange`, `onToggleWatchlist`, `onInfo`, `isWatchlisted`.
- Do not introduce per-table `grid-template-columns` that conflict with `.bh-row`.
- Motion wrappers may be used (e.g., `motion(TokenRow)`), but never let motion own the structure of the row — `TokenRow` must remain a `forwardRef` component.
- Rabbit glow/reveal is driven by event delegation on `.board-core` in `frontend/src/Dashboard.jsx` (updates CSS vars, rows remain purely presentational).

How to revert
- The edits in this change are confined to `frontend/src/components/Losers3m.jsx` and `frontend/src/components/Watchlist.jsx`.
- To revert these two files to the previous commit:

```bash
# from repo root
git checkout -- frontend/src/components/Losers3m.jsx frontend/src/components/Watchlist.jsx
```

- If you want to revert the entire working tree to the branch state before these edits (dangerous if you have other uncommitted work):

```bash
git reset --hard HEAD
```

Contact
- If you want me to also fold duplicate CSS rules or run a quick `npm run build` to validate, say so and I'll proceed.
