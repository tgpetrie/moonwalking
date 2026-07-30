# Sentiment Source Research — Free-First Expansion (July 2026)

Companion to `SENTIMENT_SOURCE_SALVAGE_PLAN.md`. This is the "what should we add
next, and what does it cost" research pass. Nothing here is wired into code yet —
it is an investigation to decide which accounts are worth setting up.

Pricing on JS-rendered vendor pages (Neynar, LunarCrush) could not be scraped
exactly; those rows are marked **verify live**. Everything else is cited below.

## Implementation status (uncommitted, on `codex/sentiment-source-v1-research`)

- ✅ **Market-positioning health display** — `normalizeSentiment.marketPositioning`
  + `MarketPositioningStatus.jsx`, rendered in the Sentiment panel.
- ✅ **Hyperliquid** wired into `_get_derivatives_positioning_payload` (keyless,
  on-chain; funding normalized from 1h to 8h-equivalent). Live-verified.
- ✅ **Coinalyze** wired but **inert until `COINALYZE_API_KEY` is set** (free key).
  When unset it is not counted among configured exchanges. Symbol format
  (`BTCUSDT_PERP.A`) is best-effort — verify against the key when activated.
- ✅ **Per-coin positioning** (`backend/derivatives_positioning.py`) — Hyperliquid
  keyed by bare symbol, keyless. Funding crowding + OI level + an OI×price read
  (falls back to funding×price until the in-memory OI snapshot store has a real
  span). Surfaced in two places: portfolio position-intel card
  (`intel.positioning`, context — not counted in signal coverage) and SymbolPanel
  overview via `/api/positioning/<symbol>`. Coins with no perp show "no derivatives
  market". Shared `CoinPositioning.jsx` renders both. In the live UI the per-coin
  card is surfaced in the mounted Coin Pressure panel (`SentimentPopupAdvanced`)
  Intel tab — the orphaned `SymbolPanel` is not used.
- ⏳ Not yet built: RSS news, Reddit, Farcaster, Polymarket, DefiLlama, DEX data,
  AI-native vendors. Long/short + liquidations (Coinalyze key) slot into the same
  per-coin block later. See rounds below.

## TL;DR — what to actually do

**Set up now (free, worth it):**

1. **Reddit app (OAuth client)** — the best *free* social source. 100 req/min with
   OAuth, full public post/comment/subreddit access, $0 cost. Caveat: non-commercial
   only, and it now needs pre-approval under Reddit's Nov-2025 "Responsible Builder
   Policy."
2. **Neynar account (Farcaster)** — the best *free-first* replacement for X/Twitter.
   Crypto-native network, cleaner signal-to-noise than Reddit or X, developer-friendly
   credits. **verify live** whether the current free/trial credit allotment is enough.
3. **Santiment free account** — test-drive `social_volume` / `crowd_sentiment` across
   1000+ channels. Free plan exists but is rate-limited; good enough to evaluate.
4. **No account needed: crypto news RSS** — CoinDesk, Cointelegraph, Decrypt, The Block,
   Bitcoin Magazine all publish free RSS/Atom. This is the free `news_context` path.

**Skip / defer:**

- **X/Twitter** — effectively pay-only now. No usable free read tier; pay-per-use
  ~$0.005/read (cap 2M/mo), Basic/Pro closed to new signups, Enterprise ~$42k/mo.
  Not worth it for V1.
- **CoinGlass API** — no free tier ($29/mo entry, $299/mo for commercial). You already
  pull funding + OI **free** straight from Binance/OKX/Bybit. Only pay if you want
  cross-exchange **liquidations** and **long/short ratio** aggregated over 30+ venues.
- **CryptoPanic API** — free developer tier is being **discontinued April 1, 2026**.
  Paid is cheap ($9/mo) but free RSS covers the same news need.
- **LunarCrush (Galaxy Score / AltRank)** — enriched social, but API is gated behind
  higher paid plans. Defer until the core signal plumbing is stable (matches salvage plan).

## Source-by-source

### Social chatter (`social_chatter`)

| Source | Free? | Cost / limits | Account setup | Verdict |
|---|---|---|---|---|
| **Reddit** | ✅ Yes | 100 req/min (OAuth), 10/min unauth; commercial = $0.24/1k calls, enterprise ~$12k/yr | Create Reddit "app" → OAuth2 client id/secret; **pre-approval required** (Responsible Builder Policy, Nov 2025); non-commercial only on free | **Best free social.** Needs OAuth + spam/noise filtering + a persistence layer first (per salvage plan). |
| **Farcaster via Neynar** | ⚠️ Free tier **verify live** | Paid tiers ~300/600/1200 RPM (Starter/Growth/Scale) + credit model | Sign up at dev.neynar.com → API key | **Best X-alternative.** Crypto-native, low bot noise. Worth an account to evaluate the free credits. |
| **StockTwits / CryptoTwits** | ⚠️ Partial | Official API is partner-gated; per-message bull/bear tags → daily sentiment ratio. CryptoTwits launched 2025 for crypto | Apply for API access; scraping tools exist (Apify ~$5 credit ≈ 2,100 msgs) | Interesting **structured** sentiment (explicit bull/bear tags). Later — official access is unclear. |
| **X / Twitter** | ❌ No usable free | Pay-per-use default (Feb 2026): $0.005/read, cap 2M/mo; Basic/Pro closed to new signups; Enterprise ~$42k/mo | Developer account + billing | **Skip for V1.** Cost/noise not justified. |

### Market positioning (`market_positioning`) — already partly built

| Source | Free? | Cost / limits | Verdict |
|---|---|---|---|
| **Binance / OKX / Bybit (direct)** | ✅ Yes | Public market endpoints, free | **Already implemented.** Funding + OI. Keep as the base. |
| **CoinGlass** | ❌ No free API | $29 Hobbyist (30 rpm, personal), $79 Startup, $299 Standard (commercial), $699 Pro | Only pay if you want **liquidations + long/short** aggregated across 30+ exchanges. Web platform is free (manual reference), API is not. |

### News context (`news_context`)

| Source | Free? | Cost / limits | Verdict |
|---|---|---|---|
| **RSS: CoinDesk, Cointelegraph, Decrypt, The Block, Bitcoin Magazine** | ✅ Yes | Free RSS/Atom, no key | **The free path.** Dedup by title/URL; freshness per salvage plan (24h display / 2h breaking). |
| **CryptoPanic API** | ❌ Free tier ending 4/1/2026 | PRO $9/mo or $99/yr | Cheap, adds vote/sentiment metadata + 50-source aggregation, but RSS covers the base need. Optional later. |

### Enriched / vendor sentiment (paid, later)

| Source | Free? | Cost / limits | Verdict |
|---|---|---|---|
| **Santiment** | ✅ Free plan (limited) | Free plan rate-limited; paid tiers + 14-day trial for depth | **Test the free plan.** social_volume, social_dominance, crowd_sentiment over 1700+ assets / 1000+ channels. |
| **Messari** | ✅ Free tier | 20 req/min free; Sentiment API depth behind Enterprise | Usable free for light macro/context. |
| **LunarCrush** | ❌ API gated to paid | Individual ~$24–30/mo **verify live**; API on Builder/Scale | Galaxy Score / AltRank. Defer until core stable. |

### Market mood (`market_mood`) — already built

- **Alternative.me Fear & Greed** — free, already used.
- **CoinGecko global** — free Demo plan (~30 calls/min), already used.

## How this maps to the project rules

- **Free-first:** Reddit + Farcaster/Neynar + Santiment-free + RSS news cover all four
  source roles at $0–low cost. No paid vendor is required to expand beyond the current
  derivatives work.
- **Context, not signal:** every source above stays in its role bucket
  (`social_chatter` / `news_context`) and must expose provenance + freshness + failure
  state — same contract as the `market_positioning` block just shipped. None of them
  should feed a generic buy/sell score.
- **Sequencing (from salvage plan):** RSS news → Reddit (needs persistence + spam
  filtering) → Farcaster → enriched vendors. Do **not** batch-add; each source lands
  behind its own health display like the positioning block.

## Open questions to confirm before building

1. **Is Moonwalking commercial?** If yes, Reddit's free tier ToS (non-commercial) is a
   blocker → budget for $0.24/1k calls or pick Farcaster-first.
2. **Neynar + LunarCrush exact free/entry pricing** — confirm on the live pricing pages
   (JS-rendered, not scrapeable here).
3. **Do we need cross-exchange liquidations/long-short** badly enough to pay CoinGlass
   $29–299/mo, or is direct-exchange funding + OI sufficient for now?

## Round 2 — broader & newer sources (2026)

The salvage list is ~2 years old and predates a whole wave of crypto-native / AI-native
data providers, plus some **free** alternatives to the paid tools flagged above. Highlights:

### 🏆 Best *new* free finds (set up now)

| Source | Role | Free? | Limits | Why it matters |
|---|---|---|---|---|
| **Coinalyze** | `market_positioning` | ✅ **Free API** | 40 calls/min per key (free key required) | **The free alternative to CoinGlass.** Funding, OI, predicted funding, **liquidations**, and **long/short history** aggregated across many exchanges — i.e. the exact cross-exchange data CoinGlass charges $299/mo for. This is the single biggest upgrade to your current direct-exchange positioning work. |
| **DefiLlama** | on-chain context | ✅ **Free, keyless** | Generous, no signup | TVL, stablecoin flows, DEX volume, chain/protocol data. Zero-friction on-chain `news_context`/regime input. |
| **Polymarket** | alt-sentiment | ✅ **Free API** | Public CLOB/gamma API | Prediction-market **odds as crowd sentiment** ("83% chance BTC hits $X"). A genuinely different, non-social sentiment signal; ~94% accurate a month out per their stats. |
| **Augmento** | `social_chatter` | ✅ Free (delayed) | Real-time & API access are paid; free = delayed | AI sentiment over X + Reddit + Bitcointalk across 93 topics / 25+ assets. Good free-first vendor to evaluate; delayed data is fine for context. |

### On-chain analytics (mostly paid, some free)

| Source | Free? | Verdict |
|---|---|---|
| **DefiLlama** | ✅ Free, keyless | Use it. |
| **Dune Analytics** | ✅ Free tier (+ limited API) | Custom SQL on-chain; good for bespoke metrics later. |
| **Glassnode / CryptoQuant** | ⚠️ Some free, depth paid | BTC/ETH macro-cycle metrics; paid for the good stuff. Later. |
| **Nansen / Arkham** | ❌ Mostly paid | Smart-money / entity attribution. Not needed for sentiment. |
| **Bitquery / Covalent / Moralis** | ✅ Free tiers | Raw on-chain query infra; only if you build custom flows. |

### AI-native attention / "InfoFi" (newer, mostly paid)

| Source | Free? | Verdict |
|---|---|---|
| **Kaito AI** | ❌ API paid | Sunset the "Yaps" post-to-earn program Jan 2026; now Pro + **API** + Attention Markets. AI **narrative/mindshare** sentiment over X — a modern replacement for raw X scraping. Watch-list; evaluate if budget appears. |
| **Cookie DAO / cookie.fun** | ⚠️ Gated | AI-agent index + mindshare data layer. Niche (AI-agent tokens). Later. |

### Market-data aggregators (for completeness)

| Source | Free? | Verdict |
|---|---|---|
| **CoinGecko** | ✅ Free Demo (~30/min) | Already used. |
| **CoinMarketCap** | ✅ Free tier | Alternative to CoinGecko. |
| **CoinAPI** | ✅ Small free tier | Unified market data; overkill for now. |
| **Amberdata** | ❌ Enterprise | Institutional; skip. |
| **Velo Data** | ❌ API $199/mo (terminal free) | Nice web terminal, paid API. Skip. |
| **Laevitas** | ❌ Enterprise / pay-per-request | Institutional derivatives. Skip. |
| **CCData / CryptoCompare (CoinDesk Data)** | ❌ **Free tier retired May 21, 2026** | Was a go-to free source; the 250k-lifetime free tier is dead. Don't build on it. |

### News APIs (RSS still wins for free)

| Source | Free? | Verdict |
|---|---|---|
| **RSS (CoinDesk/Cointelegraph/Decrypt/The Block)** | ✅ Free | Still the free default. |
| **NewsAPI** | ✅ 200 credits/day, 12h delay, no full text | Too delayed for breaking context. |
| **NewsData.io / CryptoNews-API / APITube** | ✅ Small free tiers | Optional structured news + sentiment tags; RSS covers the base. |

### Free-first alt-signals worth a mention

- **Google Trends** (free via `pytrends`): retail-interest proxy. **Caveat:** 2026 data shows
  it decoupling from price as flows shift to ETFs/institutions — treat as weak context only.
- **The Tie / Santiment / LunarCrush**: premium X-sentiment vendors (paid) — the "buy signal
  quality" tier once core plumbing is stable.

### Updated free-first shortlist (supersedes Round 1 where they overlap)

1. **Coinalyze** — free, upgrades your positioning work with liquidations + long/short. **Top pick.**
2. **RSS news** — free, no account.
3. **DefiLlama** — free, keyless on-chain context.
4. **Reddit (OAuth)** — free social (non-commercial caveat).
5. **Farcaster/Neynar** — free-tier crypto social (verify credits).
6. **Polymarket** — free prediction-odds sentiment.
7. **Augmento (delayed) / Santiment (free) / Messari (free)** — free vendor sentiment to trial.

## Round 3 — newest on-chain & AI-native (2025–2026, didn't exist on the old list)

These are the genuinely *new* categories that emerged after the salvage list was written.

### 🏆 The standout: on-chain perp positioning

| Source | Role | Free? | Why it's new & why it matters |
|---|---|---|---|
| **Hyperliquid** | `market_positioning` (on-chain) | ✅ **Free public API** | Barely existed 2 years ago; now the **dominant on-chain perp DEX** — ~$172B 30-day volume, **$9B+ open interest, 180+ assets**, funding + OI + liquidations, all on-chain. This is the **on-chain counterpart to your CEX derivatives block** (Binance/OKX/Bybit). Pair it with Coinalyze (CEX-aggregated) and you cover both worlds. Also queryable free via Dune; Nansen has paid HL endpoints. |

`market_positioning` now has a clean free stack: **direct CEX (built) → Coinalyze (CEX-aggregated, free) → Hyperliquid (on-chain, free)**.

### Free real-time DEX / token data (new tokens your CEX board misses)

| Source | Free? | Limits | Note |
|---|---|---|---|
| **DEX Screener** | ✅ Free, **no auth** | 300 req/min | Real-time DEX pair price/liquidity/volume across chains. Easiest possible integration. |
| **GeckoTerminal** (CoinGecko on-chain) | ✅ Free | ~30 req/min | 250+ chains, 1,700+ DEXs, 37M+ tokens, OHLCV + trades. |
| **DexPaprika** (Coinpaprika) | ✅ Free tier | 30 req/min | 200+ chains, another free option. |
| **Birdeye** | ⚠️ Freemium | 30k CUs/mo; streaming $250/mo | Best **Solana** depth + token-security data. |
| **Mobula** | ✅ Free tier | multichain | CoinGecko-alternative market + on-chain data. |

Use case: these cover **long-tail / brand-new tokens** and DEX liquidity that a CEX price board never sees — useful for a "new listings / early momentum" context lane, not core signal.

### Newer on-chain analytics platforms

| Source | Free? | Note |
|---|---|---|
| **Flipside Crypto** | ✅ Free SQL + Data API | 30+ chains, curated datasets, AI agents. Strong free option. |
| **Artemis** | ⚠️ Some free | REST API: protocol revenue, fees, TVL, stablecoin supply, dev activity for 12,000+ tokens. Good macro/fundamental context. |
| **Allium / Goldsky** | ❌ Enterprise | Real-time indexing, 23+ chains. Skip unless you need custom pipelines. |
| **⚠️ Dune SIM API** | — | **Being retired Aug 1, 2026.** Do not build on SIM; use Allium/Flipside if you need wallet/tx endpoints. |

### AI-native intelligence (the category that didn't exist then)

| Source | Free? | Note |
|---|---|---|
| **Grok / xAI API** | ❌ Paid (cheap per-token) | **The pragmatic X-sentiment workaround** now that the X API is paywalled: Grok reads & analyzes X threads directly (~30-min delay). Far cheaper than X Enterprise; delay is fine for context. Strongest "modern replacement for scraping Twitter." |
| **Token Metrics API** | ⚠️ Paid tiers (Advanced 20k calls/mo) | AI Trader/Investor **Grades**, sentiment, smart indices, AI reports. Black-box vendor signal — label clearly if used. |
| **Kaito API** (from Round 2) | ❌ Paid | AI narrative/mindshare over X. |
| **aixbt (Virtuals)** | ❌ Token-gated | Terminal needs 600k+ AIXBT held; no clean public API. Skip. |
| **Oracles: Pyth / Chainlink** | ✅ Free feeds | Low-latency price truth (Pyth is free, on-chain). You already have price, but useful as a cross-check. |

### Where these land against the project rules

- **On-chain positioning (Hyperliquid)** is same-role as your shipped block → highest-value new addition, free, behind its own health display.
- **DEX data (DEX Screener/GeckoTerminal)** = coverage/context for new tokens, **not** a predictive signal — keep it in a clearly-labeled context lane.
- **AI-native (Grok, Token Metrics)** = black-box vendor signals. Per the salvage plan's "retire unless reverified" spirit: only use with explicit provenance labels; never fold silently into a score.
- **Deprecation watch:** Dune SIM (Aug 1 2026), CCData free (May 21 2026), CryptoPanic free (Apr 1 2026) all dying — don't anchor on them.

### Updated "new & free, worth setting up" (on-chain + AI focus)

1. **Hyperliquid** — free on-chain perp positioning (funding/OI/liquidations). ← top new pick
2. **DEX Screener** — free, no-auth real-time DEX data.
3. **GeckoTerminal** — free broad on-chain token/OHLCV.
4. **Flipside** — free SQL on-chain analytics.
5. **Coinalyze** (Round 2) — free CEX-aggregated derivatives.
6. **Grok/xAI API** — cheap paid, best modern X-sentiment path (if any social budget).

## Sources

- Reddit API pricing/limits: https://www.socialcrawl.dev/blog/reddit-data-api-2026 , https://octolens.com/blog/reddit-api-pricing
- X/Twitter API pricing: https://postproxy.dev/blog/x-api-pricing-2026/ , https://www.socialcrawl.dev/blog/x-twitter-api-2026
- CoinGlass pricing: https://comparedge.com/tools/coinglass/pricing , https://dev.to/great-time-flies/coinglass-api-review-2026-is-it-worth-it-for-crypto-quant-traders-2bcf
- Neynar: https://dev.neynar.com/pricing , https://docs.neynar.com/reference/what-are-the-rate-limits-on-neynar-apis
- CryptoPanic: https://cryptopanic.com/developers/api/plans , https://cryptopanic.com/developers/api/about
- LunarCrush: https://lunarcrush.com/pricing/ , https://lunarcrush.com/products/lunarcrush-api/
- Santiment: https://cryptoadventure.com/santiment-review-2026-on-chain-metrics-social-signals-alerts-and-api-limits/ , https://api.santiment.net/
- Messari: https://docs.messari.io/api-reference/endpoints/signal/sentiment/overview
- StockTwits: https://anysite.io/sources/stocktwits/ , https://www.benzinga.com/content/45346216/stocktwits-launches-cryptotwits-bridging-traditional-finance-and-crypto-for-10m-investors
- Coinalyze (free derivatives API): https://api.coinalyze.net/v1/doc/ , https://coinmarketman.com/coinalyze/
- Laevitas / Velo (paid derivatives): https://www.laevitas.ch/ , https://velodata.gitbook.io/velo-data
- On-chain free tiers (DefiLlama/Dune/Glassnode): https://altfins.com/knowledge-base/best-free-crypto-api-in-2026-9-no-cost-options-compared/ , https://finestel.com/blog/top-onchain-analysis-tools/
- Kaito AI / Cookie DAO (AI mindshare): https://www.coingecko.com/learn/what-is-kaito-earn-yap-points , https://www.cookie.fun/
- Polymarket (prediction-market sentiment): https://polymarket.com/crypto
- Google Trends (retail interest): https://www.altrady.com/blog/crypto-trading-strategies/crypto-google-trends-signal-2026
- Augmento / The Tie (X sentiment vendors): https://augmento.ai/plans , https://www.thetie.io/solutions/sentiment-api/
- CCData free tier retirement: https://coinstats.app/blog/top-coindesk-api-alternatives-for-crypto-data/
- NewsAPI / news vendors: https://thunderbit.com/blog/best-news-apis-compared
- Hyperliquid (on-chain perps): https://www.datawallet.com/crypto/hyperliquid-statistics , https://docs.nansen.ai/api/hyperliquid , https://defillama.com/protocol/hyperliquid
- DEX data APIs (DEX Screener/GeckoTerminal/Birdeye): https://www.coingecko.com/learn/top-5-best-onchain-dex-data-apis , https://coinpaprika.com/education/best-free-dex-api-2025-dexpaprika-vs-dextools-vs-geckoterminal-vs-dexscreener-vs-birdeye/
- Onchain analytics (Flipside/Artemis/Allium/Dune SIM retirement): https://api.flipsidecrypto.com/ , https://about.artemis.ai/products/api , https://www.allium.so/blog/
- AI-native (Grok/xAI, Token Metrics, aixbt): https://www.tokenmetrics.com/api , https://medium.com/predict/top-ai-agents-for-crypto-in-2026-leading-trading-and-analysis-tools-165089bdc3f5
- Awesome crypto API list (315+ services): https://github.com/buddies2705/awesome-blockchain-crypto-api
