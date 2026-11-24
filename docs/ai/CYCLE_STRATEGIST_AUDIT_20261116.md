# Cycle Strategist red-team audit · November 16, 2026

Reviewed `de09b26..c4b2199` on `claude/elliott-abc-v2-reclaim-20261115`.
The first-parent chain is `aa59e33`, `d74f5fe`, `45c6683`, `baf0077`,
`08e3adf`, `475a981`, `c4b2199`. The diff and checks include the Coinbase
paper collector and replay brought in by the merge. Fixes live on
`codex/cycle-strategist-audit-20261116`.

| Audit area | Result | Evidence |
|---|---|---|
| Cycle math | Corrected | Resampling requires all seven UTC days or every day of the UTC month. Indicator warmup restarts after gaps. Monthly exhaustion requires at least 18 bearish months and a histogram moving toward zero while still negative. Divergence and MACD kiss use closed data. Flash wicks need both adjacent days to establish isolation. All requested Fibonacci ratios participate in the 6% comparison. Breadth excludes unavailable measurements; the industry gate uses a fixed universe and stays neutral when breadth is unknown. |
| Strategist and paper execution | Corrected | Scanner rows keep the weekly SMA ladder, daily floor, RSI regimes, and other decision evidence. Mode A queues all proposals. Mode B can only simulate sells; absent, stale, crossed, wide and thin books block both simulated fills and stop arming. Pause, caps and proposal transitions share a SQLite write lock. Approval only records a decision; repeating it returns the same record, and a conflicting decision returns 409. |
| Smart Alerts | Corrected | All 11 predicates exercised against scanner output. Stored invalid rules are skipped without stopping other rules. A transaction reserves each cooldown before delivery. Test sends cannot consume real cooldowns. Quiet hours suppress action-queue push, wake-up bypasses quiet hours, and watch only logs. Destination failures are recorded separately. |
| Flask and frontend contract | Corrected | Owner routes return no-store responses, including errors. Malformed bodies and IDs are rejected. Public agent surfaces omit private strategist evidence. Public macro requests cannot change the shared industry calculation. Coinbase Trade destinations resolve through the common USD spot helper. |
| End-to-end smoke | Passed | An isolated Flask client used fixture responses at the Coinbase HTTP boundary, the actual daily loader and scanner, a signed owner session, `build_cycle_context`, `run_once`, and temporary SQLite stores. The routed scan produced an SMA-only LTC trim, an AVAX breakout proposal, and a RENDER monthly RSI/MACD alert. Both proposal decisions were verified twice through the HTTP endpoint. |
| Full checks | Backend and frontend passed | Backend: 984 passed, 33 skipped. Frontend: 590 passed in 45 files; production build passed. The separate repository-level volume fixture failure was reproduced on the original commit. |

Security reproductions against `c4b2199` used temporary stores. An anonymous
observation request returned a strategy's simulated size and proceeds. A new
account could register the configured owner email and access owner-only routes.
A credentialed, bodyless POST could approve a proposal from a different origin;
browser exploitation requires an origin and cookie policy that send the owner's
cookie plus a known proposal ID. The public scan also let callers displace the
shared cache and influence the decision universe. The patch filters private
observations, reserves the configured owner email, requires JSON for decisions,
and separates validated public supplements from the stable industry calculation.
The development session fallback now uses a random key; stable sessions across
restarts or workers require an explicitly configured secret.
An authorized but malformed stored RSI rule could stop all later rules; input
validation and per-rule containment now prevent that. New POSIX paper captures
are created with mode `0600`; Windows still uses the destination directory ACL.

Verification uses the repository's backend pytest config (run from `backend`),
the separate tests under `tests/`, `npm --prefix frontend test -- --run`, and
`npm --prefix frontend run build`. A bare root pytest run also collects an
older calibration script that needs `/home/claude/calib/decisions.npz`. The
separate repository-level suite's existing `test_load_dev_volume_fixture`
asserts 10 points while the helper returns 60 on both revisions (1,475 passed).

The RSI and StochRSI calculations were cross-checked against TradingView's
[RSI](https://www.tradingview.com/support/solutions/43000502338-relative-strength-index-rsi/)
and [StochRSI](https://www.tradingview.com/support/solutions/43000502333-stochastic-rsi-stoch-rsi/)
definitions. The daily loader's page and bucket rules were checked against
[Coinbase Exchange candle documentation](https://docs.cdp.coinbase.com/api-reference/exchange-api/rest-api/products/get-product-candles).

No deployment, external notification, exchange order, or service restart was
performed. The CLI has no live quote feed; only a caller supplying a valid
two-sided book can produce a simulated automatic order. Point Flask and the
runner at the same agent, smart-alert, and paper SQLite paths when they run
from different checkouts. Provision or verify the intended owner account on a
private instance before exposing signup, and configure a strong Flask session
secret on reachable deployments. The indicators and rules remain descriptive;
the review does not establish trading performance.
