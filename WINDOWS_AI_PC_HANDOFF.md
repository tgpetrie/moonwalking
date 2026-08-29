# Moonwalkings / BHABIT — Windows AI PC Handoff

Last updated: 2026-08-29

Read this after `HANDOFF.md`. This document is intentionally specific to the
current sell-side/risk-level work and to resuming it on a Windows machine.

## Transfer state — read this first

- Repository: `https://github.com/tgpetrie/moonwalking.git`
- Current branch: `feat/feature-retention-snapshots`
- Current `HEAD`: `65146cea`
- The branch is three commits ahead of
  `origin/feat/feature-retention-snapshots`.
- The sell-side feature described below is **uncommitted** on the current Mac.
  A pull on the Windows PC will not contain it until these changes are reviewed,
  committed, and pushed (or transferred as a patch). Do not recreate the work
  independently and then try to merge two versions.
- Nothing from this sell-side session has been deployed to production.

Current sell-side working-tree files:

```text
M  HANDOFF.md
M  backend/app.py
M  backend/production_entrypoint.sh
M  deploy/railway/env.example
M  frontend/src/api.js
M  frontend/src/components/SentimentPopupAdvanced.jsx
M  frontend/src/components/SentimentPopupAdvanced.test.jsx
M  frontend/src/styles/sentiment-popup-advanced.css
?? WINDOWS_AI_PC_HANDOFF.md
?? backend/sell_plan_outcomes.py
?? backend/sell_side_intelligence.py
?? backend/tests/test_risk_levels_route.py
?? backend/tests/test_sell_plan_outcomes.py
?? backend/tests/test_sell_side_intelligence.py
```

## Read-only boundary

BHABIT remains an information-only assistant.

- It does not create, preview, stage, edit, cancel, or submit a Coinbase order.
- It does not call a Coinbase trading endpoint.
- `methodology.order_placement` is always `false` in the risk-level response.
- “Stop trigger” and “sell limit” explain the two fields a person would need if
  they independently chose to create a stop-limit order.
- The feature does write to BHABIT's own SQLite database. That local write
  records what BHABIT displayed so the recommendation can be measured later;
  it is not a market transaction or an exchange-account write.

Do not broaden this boundary without explicit owner authorization and a fresh
security review.

## Where the displayed numbers come from

### Source data

1. Current price: the Flask process's live Coinbase USD price cache.
2. Price structure: public Coinbase Exchange candles from
   `/products/{SYMBOL}-USD/candles`.
3. Candle window: 50 one-hour candles (approximately 50 hours).
4. Candle cache: five-minute TTL by default.
5. Live risk context: canonical Event Evolution state plus sampled Coinbase spot
   pressure. This context can raise a top-risk warning but cannot change the raw
   support, resistance, or ATR calculations.

No social, news, sentiment, Fear & Greed, funding, open-interest, watchlist, cost
basis, allocation, or portfolio-size value enters the current level formula.
Those sources remain separate context elsewhere in the product.

Social has one indirect path into the **warning state**, not into the price
levels: Event Evolution may group a current social alert (for example social
divergence) and give that event a down direction. The risk scorer gives a
down-directed grouped event +1 point. It does not read `social_heat`, post
counts, engagement, or sentiment scores directly, and it gives no point merely
for a Social modifier. The current reason line says “latest grouped signal
direction is down”; it does not yet identify that the direction may have come
from a social detector. If strict tape-only risk scoring is desired, filter
social-family events before passing direction into `build_sell_plan`.

### Descriptive candle measurements

Implemented in `backend/position_levels.py`:

- Support = lowest low in the 50-hour candle window.
- Resistance = highest high in that window.
- ATR = mean true range over the latest 14 available candle transitions.
- Range position = current price's percentage position between support and
  resistance, clamped to 0–100.
- One-hour momentum = latest completed candle close versus the prior close.
- Volume ratio = latest hourly volume divided by the median of prior hourly
  volumes in the window.

These are descriptive observations, not historically proven predictive levels.

### Stop trigger and sell limit

Implemented in `backend/sell_side_intelligence.py` as `sell_levels_v1`:

```text
support_buffer = max(0.20 × ATR, 0.15% × current_price)
stop_trigger = min(support - support_buffer, current_price - 1.00 × ATR)

limit_gap = max(0.10 × ATR, 0.20% × stop_trigger)
limit_gap is capped at 0.75% × stop_trigger
sell_limit = stop_trigger - limit_gap
```

The trigger therefore sits below observed support and has at least one ATR of
room from the current quote. The sell limit sits below the trigger to define a
small execution band. A stop-limit can still remain unfilled if price gaps
through that limit; the UI states this explicitly.

If the old range support is already above the live quote, structure has already
failed; the implementation uses the lower ATR band as its fallback reference
instead of presenting the broken range low as a valid stop anchor.

### Other displayed levels

- Structural invalidation = recent support.
- First trim area = recent resistance, only when resistance is above the
  current quote.
- Displayed reward/risk = distance to first trim divided by distance to stop.
- Support/re-entry-watch zone = `support - 0.10 × ATR` through
  `support + 0.25 × ATR`, capped below the current quote.
- If price is already above the observed resistance, the UI shows no first trim
  inside the measured range. A two-risk-unit extension is retained only as the
  forward-measurement boundary and is explicitly not a validated target.

### Top / exit risk score

This score explains warning flags; it is not a probability.

| Evidence available at display time | Points |
|---|---:|
| Current price at or below support | +5 |
| Price in top 15% of recent range | +2 |
| Resistance no more than 1.5% overhead | +1 |
| Latest completed hourly momentum is negative | +2 |
| Negative momentum with volume ratio at least 1.5× | +1 |
| Live Reversal/Fading/Fakeout/Exhaustion/Fragile warning | +2 |
| Latest grouped signal direction is down | +1 |
| Sampled Coinbase spot pressure is selling | +1 |

Labels:

- `Protect now`: price is at/below support or score is at least 5.
- `Top watch`: score is 3–4.
- `No top signal`: score is below 3.

## Historical evidence and measurement

The initial levels do **not** come from a backtest or a proven historical edge.
Every payload says `outcome_validated: false`.

The new ledger in `backend/sell_plan_outcomes.py` begins prospective evidence
collection:

- Opening/displaying a plan records at most one plan per coin per clock hour.
- Horizon: 24 hours.
- Outcome: `target_first`, `stop_first`, `expired`, or still open.
- It also retains maximum favorable and maximum adverse movement.
- The ledger is global to that BHABIT deployment and keyed by coin/hour; it is
  not user-specific and has no `user_id`.
- It measures how BHABIT's displayed plan behaved, not whether a person placed
  the order, received a fill, made a profit, or followed the suggestion.
- The UI displays raw counts and recent rows.
- `target_first_rate` deliberately remains `null`; no predictive success rate
  is claimed without a controlled methodology.
- Production persistence path:
  `MW_SELL_PLAN_OUTCOMES_DB=$DATA_DIR/sell_plan_outcomes.sqlite`.

This ledger is separate from the existing controlled signal-outcome scorecard.
Existing signal history does not currently alter the stop or target formula.

## Where users can see it now

The current feature is on-demand, not a new alert family.

| Surface | Current behavior |
|---|---|
| Coin Pressure → Coin tab | Compact “Sell-side intelligence” block with trigger, limit, invalidation, and first trim |
| Coin Pressure → Risk Levels tab | Full explanation, support zone, top-risk reasons, and plan history |
| Board rows / live-ranking rows | Clicking the coin opens Coin Pressure, so the compact block becomes visible |
| Watchlist rows | Clicking can open Coin Pressure; levels appear only if the backend has a current sampled price for that coin |
| Alert rows | Clicking an existing alert opens Coin Pressure; risk levels are visible there, but the risk plan did not create that alert |
| Portfolio page | Existing descriptive support/resistance remains; the new stop-limit plan is not yet rendered there |
| Alerts Center / global feed | No new risk-level event is emitted |
| Email / Telegram / Discord / browser notification | No risk-level notification is emitted |
| One-hour banners | Not displayed |

### Coin coverage limitation

This is not guaranteed for every Coinbase coin yet.

- The backend samples 120 online Coinbase USD products by default, keeps a core
  list of majors, and rotates the remaining markets.
- `/api/risk-levels/{symbol}` requires that symbol to have a current price in
  that server-side sample plus sufficient public hourly candles.
- The endpoint itself is not restricted to watchlist or portfolio membership.
- A watchlist/portfolio coin outside the current backend sample can therefore
  show “current price required” even if the frontend obtained a separate spot
  quote.

Before expanding coverage, choose deliberately between:

1. Safe on-demand server price lookup with eligibility checks, TTL caching, and
   rate limiting.
2. Guaranteed background coverage for watchlist and portfolio symbols.
3. Full-universe background coverage, which has the highest API/storage cost.

Do not silently trust a browser-supplied price merely to fill the card; that
would let an untrusted input create and grade a false plan.

## APIs

```text
GET /api/risk-levels/BTC
GET /api/risk-levels/status
```

The per-coin response contains:

```text
status
plan.current_price
plan.top_signal
plan.stop
plan.profit
plan.support_zone
plan.market_structure
plan.methodology
history.outcomes
history.history
```

## Windows development setup

### Recommended: Windows 11 + WSL2

The repository's supported launchers are Bash scripts and the production server
uses Gunicorn, so WSL2 is the least surprising Windows environment.

In Ubuntu/WSL:

```bash
git clone https://github.com/tgpetrie/moonwalking.git
cd moonwalking
git fetch origin
git switch feat/feature-retention-snapshots
git pull --ff-only

python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r backend/requirements.txt

cd frontend
npm ci
cd ..

./start_app.sh
```

Open `http://127.0.0.1:5173`. Flask is expected at `127.0.0.1:5003`; the
separate sentiment service uses `127.0.0.1:8003`.

### Native PowerShell fallback

Gunicorn and the Bash launchers are not the native-Windows path. Run each
service in its own PowerShell terminal instead.

Initial setup from the repository root:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r backend\requirements.txt

Set-Location frontend
npm ci
Set-Location ..

@"
VITE_API_BASE_URL=http://127.0.0.1:5003
VITE_API_BASE=http://127.0.0.1:5003
VITE_API_URL=http://127.0.0.1:5003
VITE_PROXY_TARGET=http://127.0.0.1:5003
"@ | Set-Content frontend\.env.local
```

Backend terminal:

```powershell
.\.venv\Scripts\Activate.ps1
$env:HOST = "127.0.0.1"
$env:PORT = "5003"
Set-Location backend
python app.py
```

Frontend terminal:

```powershell
Set-Location frontend
$env:VITE_PROXY_TARGET = "http://127.0.0.1:5003"
npm run dev
```

Optional sentiment-service terminal:

```powershell
.\.venv\Scripts\Activate.ps1
python -m backend.sentiment_api --host 127.0.0.1 --port 8003
```

## Verification on the Windows PC

Backend tests:

```powershell
.\.venv\Scripts\Activate.ps1
python -m pytest -q `
  backend\tests\test_risk_levels_route.py `
  backend\tests\test_sell_side_intelligence.py `
  backend\tests\test_sell_plan_outcomes.py `
  backend\tests\test_position_levels.py
```

Frontend build and tests:

```powershell
Set-Location frontend
npm run verify
```

API smoke test after Flask has warmed:

```powershell
Invoke-RestMethod http://127.0.0.1:5003/api/risk-levels/BTC |
  ConvertTo-Json -Depth 10
```

Manual UI check:

1. Open `http://127.0.0.1:5173`.
2. Click a coin row to open Coin Pressure.
3. Confirm the Coin tab shows “Sell-side intelligence.”
4. Open `Risk Levels`.
5. Confirm the stop trigger is above the sell limit and both are below the
   current price.
6. Confirm “Why the stop goes there,” the gap-risk warning, support/re-entry
   zone, top-risk reasons, and raw history counts are visible.
7. Confirm no trade or order-confirmation UI appears.

Verification completed on the Mac before handoff:

- 69 relevant backend regression tests passed.
- Frontend production build passed.
- All 413 frontend tests passed.
- Not yet visually checked in a running browser.

## Files to inspect first

```text
backend/sell_side_intelligence.py
backend/sell_plan_outcomes.py
backend/position_levels.py
backend/app.py
frontend/src/components/SentimentPopupAdvanced.jsx
frontend/src/styles/sentiment-popup-advanced.css
backend/tests/test_risk_levels_route.py
backend/tests/test_sell_side_intelligence.py
backend/tests/test_sell_plan_outcomes.py
frontend/src/components/SentimentPopupAdvanced.test.jsx
```

## Decisions still required

1. Should risk levels be guaranteed for watchlist and portfolio coins, or only
   calculated on demand from the rotating market universe?
2. Should `Top watch` / `Protect now` become Alerts Center events? If yes, add
   transition-based deduplication, expiry, cooldowns, and outcome measurement;
   do not emit one on every price poll.
3. Should users opt into Telegram/email/browser notifications for high risk?
4. Should portfolio cost basis and position size affect the wording? They must
   not affect raw market structure unless the product explicitly introduces a
   separate personalized risk layer.
5. Should social/derivatives context qualify the warning? If added, display
   those inputs separately and test that unavailable sources never become
   neutral guesses.
