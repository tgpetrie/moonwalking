# Deliverable 2: which proposed data sources BHABIT already covers

Written 2026-10-24 on branch `claude/data-source-plan` (docs only). Combines three inputs:
the repository inventory (`REPOSITORY_INVENTORY.md`), the scoring research
(`BHABIT_SCORING_RESEARCH.md`, with its audit corrections), and the separate Gemini vendor
research (kept as written; not edited here).

**Legend.** *Covered* = in the running path today. *Partial* = covers part of what the
source would add. *Dormant* = code exists but is inert without a key or a flag.
*Absent* = no reference anywhere in the code (verified by search of `backend/` and `frontend/`).

**Verification status of vendor facts.** Verified from the vendors' own pages on
2026-10-24: DropsTab, Nansen, Santiment, DeFiLlama (partly), Hyperliquid funding
history. **Not verified** (taken from Gemini's research): Zerion, Token Terminal,
Glassnode, CryptoQuant, LunarCrush pricing, CryptoDataDownload, IntoTheBlock, CoinDesk Data.

---

## 1. Verified facts that correct or qualify the Gemini research

| Gemini claim | Checked result |
|---|---|
| DropsTab: free API for token unlocks via a Builders Program | **True, with limits:** "up to 3 months free, up to the Advanced plan", aimed at students, hackathon teams and indie developers. Not free indefinitely; the commercial path is Basic/Advanced/Pro/Enterprise. Call limits and licence terms quoted by Gemini were not on the page. |
| Nansen: 100 credits + 10 daily; x402 at $0.01 per query | **Partly wrong.** Free plan gives 100 trial credits and **tops the balance back up to 10 per day** (it does not accumulate +10). x402 is $0.01 only for basic endpoints; **Smart Money endpoints are $0.05 per call**, so 1,000 smart-money calls cost about $50 (half price under a first-100-calls promotion). Some premium-label calls cost 150 credits each. |
| Santiment: 1,000 free calls per month, 30-day lag, Pro 5,000 | **True.** About a year of history on the free tier. Whether one call returns a full series is unverified (Santiment may weight calls by data volume). |
| DeFiLlama: free public API; paid API $300 per month | **True:** unlocks and 38 other endpoints are on the $300 plan (1M calls per month, 1,000 requests per minute). |
| BHABIT baseline includes "liquidation imbalance" | **Not in the code.** Funding and open interest are fetched; liquidations are not (a comment lists them but only funding and open-interest endpoints are called). |
| Hyperliquid historical funding | **Verified now:** the public `fundingHistory` endpoint returns 500 hourly rows per request (fields `coin`, `fundingRate`, `premium`, `time`) and pages forward, so a year per coin is about 18 requests. |

## 2. Coverage by proposed source

| Source | Pillar | In BHABIT today | Evidence | Incremental value | Measured or known coverage |
|---|---|---|---|---|---|
| **DeFiLlama** (free public API) | Fundamentals, TVL, fees, flows | **Absent** (listed "not yet built" in the July research note) | No reference in `backend/` or `frontend/` | Medium for DeFi-token fundamentals at 7-90 day horizons; none at 1-hour horizons | **Up to 63%** of your 407 coins match a DeFiLlama protocol symbol (256) and **up to 44%** have fee data (179). Both are upper bounds: 124 symbols match several protocols and need ID-level mapping. Unlock endpoints are paid |
| **DropsTab** | Unlocks, vesting, funding rounds | **Absent**. Partial overlap: CoinPaprika events (free) and CoinMarketCal (dormant) | `coin_intel_external.py` flags | High in principle: scheduled supply is deterministic and orthogonal to price | Unknown until the Builders key is granted; ask for the coin list first |
| **Nansen** | Smart-money and entity flows | **Absent**. Partial overlap: Arkham flag only (no data path) | `coin_intel_external.py` | Medium-high if labels hold up; short-horizon | Majors and large DEX tokens; small caps unlikely |
| **Santiment** | On-chain regime, social, dev activity | **Dormant, legacy** (referenced in `social_apis_handler.py`; documented as "candidate, not implemented") | `SENTIMENT_SOURCES.md` | Medium for regime (MVRV, dormancy); social metrics need a test against noise | Top assets only; free tier lags 30 days |
| **Zerion** | Wallet and DeFi position state | **Absent**. Portfolio layer is Coinbase-account only | `portfolio_mode.py` | Structural feature for Portfolio Intelligence, not predictive; only useful if holdings live on-chain | Not a coin-level source |
| **Token Terminal** | Protocol financials | **Absent** | none | Overlaps DeFiLlama fees; adds P/F style multiples | Unverified; free CSV tier per Gemini |
| **Glassnode** | BTC/ETH on-chain | **Absent** | none | Low for BHABIT (two coins) | BTC/ETH-centred |
| **CryptoQuant** | Exchange flows | **Absent** | none | Low-medium; BTC/ETH-centred; API gated | Majors |
| **IntoTheBlock** | On-chain holder metrics | **Absent** | none | Unknown | Unverified |
| **LunarCrush** | Social metrics | **Dormant** (coin-scoped metrics; inert without `LUNARCRUSH_API_KEY`) | `coin_intel_external.py` | Low; social metrics are noisy and lag price per Gemini | Needs a paid plan |
| **CryptoDataDownload** | OHLCV, risk series | **Covered** by Coinbase candles (free, and 1 year already archived locally) | candle archive | Low; it offers history you can already pull from Coinbase | n/a |
| **CoinDesk Data (ex-CCData)** | Aggregated market data | **Covered** by Coinbase and CoinGecko | | Low | Gemini says the free tier ended in 2026 (unverified) |

## 3. Coverage by information category (from the scoring research)

| Category | Today | Gap |
|---|---|---|
| Price and volume | **Covered**: Coinbase WS and REST, 1-minute to hourly; 1 year of hourly candles archived locally | No tick or order-book depth |
| Liquidity | **Partial**: spread-based buckets (wide at 30 bps, thin at 80 bps), 24-hour quote volume | No order-book depth or market-impact estimate |
| Market context | **Covered**: BTC-relative and market-median relative moves, spot buy/sell imbalance | Spot imbalance is sampled, not stored |
| Derivatives positioning | **Partial**: BTC/ETH funding and open interest from five venues (market-wide); per-coin from Hyperliquid for **133 of 407 coins (33%)**, with an in-memory open-interest history of about 24 hours | No stored history; **no liquidations**; free history is now verified for Hyperliquid funding |
| Sentiment (market-wide) | **Covered**: Alternative.me Fear and Greed, CoinGecko global | Market-wide only |
| Sentiment (coin-level) | **Partial and weak**: CoinGecko community metrics (update frequency unverified), CoinPaprika timeline; LunarCrush dormant | No attention-shock series, no mention counts against a baseline |
| News | **Dormant**: RSS and CryptoPanic handlers in the legacy pipeline | Not wired; RSS scores were applied to every coin in the old aggregator |
| Events and unlocks | **Partial**: CoinPaprika events; CoinMarketCal dormant | **No unlock or vesting schedule** |
| On-chain flows and labels | **Absent** (Arkham flag only) | Whole category |
| Fundamentals (fees, revenue, TVL) | **Absent** | Whole category; bounded by DeFi coverage (at most 44% of coins) |
| Wallet and position state | **Partial**: Coinbase account only | On-chain wallets absent |
| Listing history (survivorship) | **Absent in repo**; a PIT watch task logs product status *(memory)* | Needed for any point-in-time universe |

## 4. What this means

1. **The largest genuinely new, free, testable inputs are:** Hyperliquid funding
   history (133 coins, free, verified), DeFiLlama fees and TVL (up to 179 coins, free),
   and Santiment's free tier (1,000 calls; majors; 30-day lag). Of these, only the first
   two cover a meaningful share of your universe.
2. **Unlocks (DropsTab) are the best-motivated new signal but depend on a time-limited
   free grant** (3 months), so plan the test to finish inside that window.
3. **Nansen is cheaper to confirm than to backtest.** The free credits only confirm
   endpoints; a real backtest costs dollars per hundred coins, paid in crypto, which is
   your decision.
4. **Most of Gemini's rank 6-8 sources add little for a 407-coin Coinbase universe**
   (BTC/ETH-only coverage, duplicated history, or noisy social).
5. **Coverage is a hard filter, not a footnote.** A feature available for 33-44% of
   coins can only improve those coins; hold-out tests must be run on the covered subset
   and reported as such, never as a universe-wide claim.
6. **Still unmeasured:** coverage of DropsTab, Nansen and Santiment against the 407 coins
   and against your actual holdings. Those lists need an account or key, so they are
   step zero of the trial plan.

## 5. Existing documents to reconcile

* `docs/developer/SENTIMENT_SOURCE_RESEARCH.md` (July 2026) already recommends
  Reddit (free OAuth, pre-approval required), Neynar/Farcaster, a free Santiment account
  and news RSS as the first free-first additions, and to defer LunarCrush, CoinGlass and
  CryptoPanic. This coverage assessment is consistent with it and extends it to
  fundamentals, unlocks and on-chain flows, which it did not cover.
* `docs/developer/SENTIMENT_SOURCE_SALVAGE_PLAN.md` defines four source roles
  (market mood, market positioning, news context, social chatter), per-role staleness
  windows, and divergence thresholds (0.25 warning, 0.40 critical). Those thresholds are
  heuristic and should be treated as hypotheses in the same way as the scoring weights.
* Both documents state that sources are *context* until validated. The trial plan keeps
  that rule.

*Source files for the coverage numbers:* `~/.moonwalking/analysis/llama_coverage.json`
and `hyperliquid_coverage.json` (symbol-matching; not committed).
