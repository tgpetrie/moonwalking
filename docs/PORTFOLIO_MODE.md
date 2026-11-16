# BHABIT Portfolio Mode

Portfolio Mode turns the authenticated member area into a private, view-only trading cockpit without granting BHABIT authority to trade or move funds.

## Stage 1 contract

- Route: `GET /api/portfolio`
- Authentication: existing BHABIT session cookie
- Ownership: `COINBASE_PORTFOLIO_OWNER_EMAIL` must match the signed-in account
- Coinbase permissions: View is required; Trade and Transfer must both be false
- Data: balances, held funds, fills, open-order visibility, current valuation, allocation, and honestly bounded cost basis
- Cache: short live cache with bounded last-good stale fallback

The API never returns the Coinbase key name or private key. The frontend never calls a private Coinbase endpoint directly.

## Server secrets

Set these as encrypted Railway variables or in a local ignored `.env` file:

```dotenv
COINBASE_PORTFOLIO_OWNER_EMAIL=you@example.com
COINBASE_API_KEY_NAME=organizations/.../apiKeys/...
COINBASE_API_KEY_SECRET=<encrypted Railway secret>
```

Create a portfolio-specific Coinbase CDP API key with View only. Do not enable Trade, Transfer, or Withdrawal for Stage 1. Never paste the private key into chat, commit it, or expose it through a `VITE_` variable.

The backend uses Coinbase App JWT authentication and scopes all account data to the portfolio attached to that key.

## Cost-basis truth

Advanced Trade fills can reconstruct the weighted cost of quantities covered by those fills. If the current quantity exceeds the fill-covered quantity, BHABIT marks the difference as transferred-in or otherwise unverified. Summary P&L includes only holdings with complete cost basis and labels the coverage percentage.

## Deliberate omissions

Stage 1 does not contain live order creation, exchange-side order previews,
automated trading, transfer, withdrawal, or direct action links from notifications.
Protection levels, targets, and historical probabilities stay in `NOT ENOUGH
PROOF` until the comparable-event store has an adequate asset-specific sample.

The separate owner-only paper execution controls store local modes and paper
tickets in SQLite (`MW_PAPER_EXECUTION_DB` can override the default location).
Their Coinbase-shaped payloads are generated locally and never sent to Coinbase.
Guardian only auto-approves defenses whose size is covered by a fresh owner
portfolio snapshot; browser-provided holding flags are not verification.
Autonomous paper tickets are blocked when
position count, realized R, or sentiment posture is unavailable. The paper API
does not yet supply those trusted risk inputs, so its autonomous previews remain
blocked rather than assuming safe defaults.

The Cycle chart reads up to three years of closed daily public Coinbase candles
and complete Monday–Sunday UTC weekly aggregates. History is cached locally
through the current UTC day (`MW_CYCLE_HISTORY_DB` overrides its location).
Range levels use the latest closed daily price. Fib levels are retracements
down from the observed high, and historical shelves group daily highs and lows
into 2% price bands with at least three touches, ranked by touches and volume.
Coverage and missing-day counts describe the actual observed window; short
listing histories are not labeled multi-year.

## Later stages

1. Connect verified portfolio-aware risk inputs and record paper plans.
2. Grade paper outcomes and expose calibrated ranges only when samples are adequate.
3. Add Coinbase order preview with explicit in-app confirmation.
4. Consider capped auto-trading only in a separate funded portfolio with a kill switch and complete audit trail.
