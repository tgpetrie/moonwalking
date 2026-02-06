# Rabbit dot-bloom TODO

- Verify `.rabbit-bg` is actually rendered once inside `.board-core` (no duplicates).
- Confirm hover works across all row sources (1m gainers, 3m gainers, 3m losers, watchlist) and adjust selector if any table isn’t using `.bh-row`.
- Tune bloom intensity/opacity (goal: rabbit nearly invisible, bloom clearly readable on hover).
- Kill any remaining competing rabbit CSS blocks (make sure the “FINAL OVERRIDE” really is last).
- Add a tiny dev note in UI rules docs: “rabbit glow is driven by event delegation in `Dashboard.jsx`.”

# UI Polish TODO

- [x] Center 1m/3m table headers and align header font weight to token name weight.
- [x] Make “Show more” controls smaller + more discreet.
- [x] Add per-cell micro-animations + coordinated stagger across row children.
- [x] Keep row dividers anchored below rows only.
- [x] Trim sentiment card/popup to show only actionable data.
- [x] Remove unused alert filter types from the UI.
