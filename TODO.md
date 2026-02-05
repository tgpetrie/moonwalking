# Rabbit dot-bloom TODO

- Verify `.rabbit-bg` is actually rendered once inside `.board-core` (no duplicates).
- Confirm hover works across all row sources (1m gainers, 3m gainers, 3m losers, watchlist) and adjust selector if any table isn’t using `.bh-row`.
- Tune bloom intensity/opacity (goal: rabbit nearly invisible, bloom clearly readable on hover).
- Kill any remaining competing rabbit CSS blocks (make sure the “FINAL OVERRIDE” really is last).
- Add a tiny dev note in UI rules docs: “rabbit glow is driven by event delegation in `Dashboard.jsx`.”
