# 1-Minute Retention Logic Roadmap

Current implemented features (baseline):

- Throttled recompute window (ONE_MIN_REFRESH_SECONDS)
- Enable/disable master switch (ENABLE_1MIN)
- Enter / stay hysteresis thresholds (ONE_MIN_ENTER_PCT / ONE_MIN_STAY_PCT)
- Minimum dwell time before removal (ONE_MIN_DWELL_SECONDS)
- Max retained symbols cap (ONE_MIN_MAX_COINS)
- Persistence state with snapshot reuse

Planned / optional future enhancements:

1. Separate thresholds for positive vs negative movers
   - ONE_MIN_ENTER_PCT_UP / ONE_MIN_ENTER_PCT_DOWN
   - ONE_MIN_STAY_PCT_UP / ONE_MIN_STAY_PCT_DOWN
2. Decaying momentum score instead of raw % filtering (EMA-based)
3. Aging penalty: gradually lower priority of stale entries after X minutes
4. Cool‑off period after removal to avoid rapid re‑entry (per symbol cooldown)
5. Add REST endpoint to mutate 1‑min settings live (POST /api/config/one-min)
6. Provide diagnostics endpoint returning raw internal persistence state
7. Include volume acceleration factor in retention decision
8. Adaptive thresholds: widen enter threshold when list is near capacity
9. Persist state across process restarts (lightweight JSON snapshot)
10. Add Prometheus style metrics counters / gauges for retention events
11. Frontend hint fields: entered_at, dwell_elapsed, momentum_score
12. Batch price retrieval abstraction to allow failover provider
13. Optional WebSocket push for 1‑min snapshot deltas
14. Unit tests covering hysteresis edge cases & dwell expiry
15. CLI flags to override env at runtime (--one-min-enter, etc.)

Testing ideas:

- Simulate oscillating % changes around stay threshold -> verify no churn
- Flood with > max_coins strong movers -> verify capacity trimming & order stability
- Force long dwell then drop below zero -> ensure removal after dwell

Data structure refactors (future):

- Replace dict of entries with dataclass objects for clarity
- Introduce ring buffer for historical momentum scoring

Migration notes if enabling adaptive / scoring:

- Keep existing env vars as defaults; layer new logic behind feature flag (ONE_MIN_SCORING_MODE=ema|raw)

Last updated: (placeholder – update when changes made)
