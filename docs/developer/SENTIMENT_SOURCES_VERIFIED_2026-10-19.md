# Sentiment sources: Gemini's research, checked (2026-10-19)

Gemini answered `GEMINI_BRIEF_SENTIMENT_SOURCES.md` with a source inventory,
a point-in-time plan, a build order, a test design and risks (the full reply is
in the user's Gemini chat). This file records what Claude verified from this
machine (US) and what does not hold. Pricing, plan limits and policy claims
were **not** re-verified unless stated; treat them as Gemini's, unverified.

## 1. Endpoints tested from this PC (unauthenticated, one request per 1.1 s)

| Source | Endpoint tested | Result | Notes |
| --- | --- | --- | --- |
| CoinGecko | `/api/v3/global` | 200 | Already used by `sentiment_api.py` |
| CoinPaprika | `/v1/global` | 200 | Already used by coin intel |
| Hyperliquid | `POST /info` `metaAndAssetCtxs` | 200 | Already used (`derivatives_positioning.py`) |
| Hyperliquid | `POST /info` `fundingHistory` (RENDER, from 2026-09) | 200 | **History can be backfilled** |
| OKX | `/api/v5/public/funding-rate`, `/open-interest` (RENDER-USDT-SWAP) | 200 | Already used for BTC/ETH; works per coin |
| OKX | `/api/v5/public/funding-rate-history` | 200 | History can be backfilled (recent) |
| Bybit | `/v5/market/open-interest` | **403** | CloudFront country block. Do not work around |
| Binance | `api` / `fapi` | **451** | Known; `data.binance.vision` reachable |
| Deribit | `get_book_summary_by_currency` (BTC options) | 200 | Majors only |
| Coinalyze | `/v1/future-markets` | 401 | Needs the free key; code slot already exists |
| Coinbase status | `status.coinbase.com/api/v2/incidents.json` | 200 | **Only the last 50 incidents** (here 2026-09-03 to 2026-10-12), not "recent months" |
| DefiLlama | `/protocols`, `/hacks` | 200 | Free, keyless |
| DefiLlama | `/emissions` (unlocks) | **402** | Paid, as Gemini said |
| Polymarket | Gamma `/events?tag_id=21` | 200 | Keyless |
| DEX Screener | `/latest/dex/tokens/{RENDER Solana address}` | 200 | Keyless |
| GeckoTerminal | `/api/v2/networks/solana/tokens/...` | **403** | Blocked from here (HTML challenge). Gemini listed it as keyless |
| GitHub | `/repos/fetchai/fetchd/releases` | 200 | 60 requests/hour without a token |
| RSS | Cointelegraph, Decrypt, The Block | 200 | |
| RSS | CoinDesk `/arc/outboundfeeds/rss/` | 308 then 200 | Follow the redirect (no trailing slash) |
| CryptoPanic | `/api/v1/posts/?public=true` | **403** | Consistent with the free tier being gone |
| CoinMarketCal | `developers.coinmarketcal.com/v1/events` | **no response** | Unverified; needs a key anyway |
| Santiment | GraphQL (anonymous) | 200 | Reachable; plan limits unverified |

## 2. Corrections to Gemini's reply

1. **Sample size is understated by about half.** For a 5-point difference in
   7-day return between two equal groups, with 80% power, using the real
   spread of the shock bucket (standard deviation 18.5% on Coinbase
   2022–2026, not Gemini's 22%):
   - at α = 0.01: **641 events in total**, not 380;
   - at α = 0.002 (0.01 across five sources): **848**.
   Shock events (+10% day, 5x volume, 15+ points above BTC) run at about 32
   a month over 2022–2026 and 37 a month in the last year. Forward-only
   collection would therefore take **about 17 to 26 months**, not 9 to 10.
   Unequal group sizes push this higher.
2. **The test's event definition drifts from Study 1.** Gemini's Part D uses
   "move minus BTC ≥ 10 points". Study 1's shock bucket used 15 points. Use 15
   so the result is comparable.
3. **Coinbase status history is short.** The incidents feed holds the last 50
   incidents only, so listing and halt history must be logged forward. The
   `/products` diff watcher Gemini proposes is the right fix.
4. **GeckoTerminal is not usable keyless from here** (403). DEX Screener is.
5. **Part A is not CSV-ready.** Several fields contain unquoted commas.
6. **Not verified by Claude:** every price, plan and rate limit; Reddit's
   commercial pricing and pre-approval policy; Neynar credits; the claimed
   2026 shutdowns of the Dune SIM API, Glassnode free tier and CCData free
   API; Coinalyze history depth; Polymarket rate limits.

What holds: the source roles, the point-in-time rules (store `first_seen_utc`,
filter on it, log edits, never backfill news), the ticker-collision warning
(UP, TRUST, EDGE, RED, COMP, BIO, AI and others need project names or contract
addresses), the hindsight problem with wallet labels and Google Trends, and
the advice not to work around region blocks.

## 3. What the code already has

| Area | Where | State |
| --- | --- | --- |
| Fear & Greed, CoinGecko global | `backend/sentiment_api.py` | Live |
| Market-wide funding and OI (BTC/ETH) | `sentiment_api.py`: OKX and Hyperliquid live; Binance 451; Bybit 403; Coinalyze inert without `COINALYZE_API_KEY` | Live, in memory |
| Per-coin positioning | `backend/derivatives_positioning.py` (Hyperliquid) | Live; OI history kept **in memory** (`_OI_HISTORY`), lost on restart |
| Coin context | `backend/coin_intel_external.py` (CoinPaprika, CoinGecko, optional LunarCrush) | Live |
| RSS | `backend/rss_handler.py` (feedparser) via `sentiment_orchestrator.py` | Older pipeline; in memory; still calls the dead CryptoPanic API; placeholder User-Agent |
| Reddit | `backend/reddit_handler.py` (PRAW, OAuth) | Needs a Reddit app; placeholder client id |
| Point-in-time event log | none | **Missing.** Nothing is recorded at the time |

## 4. Build order, fitted to this code

Free first. Each step is a small change, behind the existing `data_status`
contract.

1. **Point-in-time log (new SQLite file, separate from the live stores).** Built: see `PIT_LOG.md` (steps 1 to 3).
   One append-only table along the lines of Gemini's `pit_context_log`
   (`product_id`, `source_id`, `event_type`, `source_published_utc`,
   `first_seen_utc`, values, `source_url`, `payload_sha256`,
   `revision_of`). Plus a `symbol_registry` keyed by Coinbase product id with
   contract addresses, so RNDR and RENDER, and colliding tickers, never mix.
2. **Coinbase `/products` watcher** (every 5 minutes, keyless): log status
   transitions (new listing, `cancel_only`, `limit_only`, delisted) and the
   status-page incidents.
3. **Persist what is already fetched:** write the Hyperliquid and OKX
   positioning snapshots to the log instead of only to memory.
4. **Coinalyze:** set the free key; the code path exists.
5. **RSS forward logger:** CoinDesk (follow the redirect), Cointelegraph,
   Decrypt, The Block every 5 to 15 minutes; store `guid`, title, URL,
   `pubDate` and `first_seen_utc`; match coins only by project name, cashtag
   or contract. Remove the CryptoPanic call and set a real User-Agent.
6. **DefiLlama hacks and DEX Screener liquidity** (keyless), then GitHub
   releases (free token raises the limit to 5,000 an hour), then Neynar and
   Reddit if their keys and terms fit.

**One test is possible now, without waiting:** Hyperliquid funding history
is settled on-chain and can be backfilled. Funding at the moment of a shock
spike can be tested against the 2022–2026 event list for coins with a
Hyperliquid perp, preregistered like Studies 1 and 2. OKX funding history adds
a second venue for recent months.

## 5. Not recommended

GeckoTerminal from this machine (blocked), Google Trends (rescales history,
ticker collisions), CryptoPanic (free tier gone), Bybit and Binance live APIs
(region blocks), paid unlock APIs until the free plumbing exists, and any
vendor sentiment score used as a signal without forward logging.
