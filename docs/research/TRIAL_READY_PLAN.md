# Deliverable 3: trial-ready data collection and testing plan

Written 2026-10-24 on branch `claude/data-source-plan` (docs only). Research and
planning only: no code, accounts, purchases, outreach or deployments are part of this
document. It builds on `REPOSITORY_INVENTORY.md`, `DATA_SOURCE_COVERAGE.md` and
`BHABIT_SCORING_RESEARCH.md`, and keeps the separate Gemini vendor research intact.

## 0. Goal and ground rules

**Goal:** find out, cheaply and honestly, whether any external source adds
information beyond price, volume and the derivatives data BHABIT already has, for coin
scoring and for portfolio risk guidance.

1. **Cost cap $0 by default.** Anything that costs money, needs an account, sends a
   message on BHABIT's behalf, or needs a crypto wallet is a **user decision** (section 8).
2. **Everything runs on your PC**, writing to a new local store. Nothing goes to the
   production volume, and nothing is deployed, until a source passes the gates and a
   retention design exists.
3. **No scraping; official APIs and documented downloads only.** Respect licences.
   Several "free" tiers are evaluation or personal use only, and bhabit.net is a
   commercial site; a source that passes the test may still need a paid licence to ship.
4. **Public hosts are shared with the live collector's IP:** at most 1 request per second
   per host, with backoff on any 429.
5. **No keys in the repo or in chat.** Keys live in environment variables or a local
   untracked file.
6. **Every test is pre-registered** (section 4) before data is looked at.

## 1. Step zero: before any trial clock starts

| # | Task | Output | Cost |
|---|---|---|---|
| 0.1 | Freeze the **universe**: the 407 coins in the candle archive, plus your actual holdings (export, or list symbols) | `universe.csv` with symbol, Coinbase product id, listing dates if known | $0 |
| 0.2 | **Coverage table per source** against that universe (DeFiLlama and Hyperliquid are done: up to 63% / 44% and 33%). Remaining: DropsTab, Nansen, Santiment, Token Terminal | One row per source with covered and uncovered coins | $0 (needs a key or account for some) |
| 0.3 | **Licence check** for each source: evaluation vs production use, storage and redistribution of history, attribution | A short table; any "personal use only" source is flagged *evaluate-only* | $0 |
| 0.4 | **Fee check:** read your Coinbase fee tier (app settings) or export fills; replace the assumed cost scenarios (0.2 / 0.5 / 0.9 / 1.2%) with your real figure | One number | $0 |
| 0.5 | Decide the **point-in-time universe** rule: use the PIT watch log *(memory)* or Coinbase product status history so delisted coins are not silently dropped | A rule written down | $0 |

## 2. Data collection design

**New local store** `external_features.sqlite` (outside the repo runtime and outside the
production volume). Append-only; no overwrites.

| Column | Meaning |
|---|---|
| `provider`, `endpoint`, `metric` | What was collected |
| `coin_key` | Bare symbol, plus the provider's own id (mapping kept separately; many symbols are ambiguous, e.g. 124 DeFiLlama symbols) |
| `value` | The number |
| `source_ts` | Time the provider says the value refers to |
| `ingest_ts` | When **we** fetched it (UTC) |
| `vintage` | `forward` (collected live) or `backfill` (history pulled later) |
| `raw_ref` | Hash and path of the cached raw response |

**Point-in-time rules.** A value is usable at time t only if `ingest_ts + latency <= t`
(forward data) or, for backfilled data, only after lagging one bar plus a stated
publication latency. **Backfilled provider history is treated as optimistic**: providers
revise and relabel. It can reject a hypothesis or justify a forward test, but **no
source is adopted on backfill alone**; adoption needs forward confirmation (section 6).

**Raw cache.** Save every response with its hash so results are reproducible and
the exact payload can be inspected (the same approach Codex's pilot used).

**Storage estimate.** Hyperliquid funding: 133 coins x about 8,760 hourly rows = about
1.2M rows (roughly 100 MB). DeFiLlama daily fees, revenue and TVL for about 180 coins:
a few hundred thousand rows. Both are small enough for a local file.

## 3. Source trial cards (in recommended order)

| # | Source | Pull | Budget | Covers | Test | Needs from you |
|---|---|---|---|---|---|---|
| 1 | **Hyperliquid funding history** (keyless) | `fundingHistory` per coin, 500 hourly rows per request, paged forward, 1 year | About 2,400 requests, roughly 40 minutes at 1 req/s | 133 of 407 coins (33%) | H2, H3 | Nothing |
| 2 | **DeFiLlama public API** | `/protocols`, `/summary/fees/{slug}`, `/protocol/{slug}` for matched protocols | About 400-600 requests, roughly 10 minutes | Up to 179 coins with fees (upper bound) | H4 | Nothing |
| 3 | **Coinbase deep history** (existing public candles) | Extend the archive back to 2-3 years for the same coins | About 11,000 requests per extra year, about 90 minutes | All 407 | Longer baseline, more regimes | Nothing |
| 4 | **Santiment free tier** | Daily MVRV, dormancy, exchange flows for about 40-60 majors, older than 30 days | 1,000 calls per month; plan about 300 | Majors only | H6 (regime) | A free account and key |
| 5 | **DropsTab Builders** | Full unlock and vesting schedule for the universe, one pull, stored locally | Unknown until granted; grant is up to 3 months | Unknown | H1 | An application, written truthfully (section 8) |
| 6 | **Nansen** (only if 1-5 show promise) | Smart-money netflow for about 100 coins | About 200 calls at $0.05 = **about $10** (a $25 cap is a sensible limit) | Majors and large DEX tokens | H5 | A funded wallet; your decision |
| 7 | **Santiment Pro trial** (14 days) | Recent 30 days, plus hourly series, only after step 4 shows promise | Within 5,000 calls | Majors | Confirms live ingestion | Start the clock deliberately |

**Not trialled:** Zerion (a feature for portfolio state, not a predictor), Glassnode and
CryptoQuant (BTC/ETH-centred, API gated), LunarCrush (noisy, paid), CryptoDataDownload
(duplicates free Coinbase history).

## 4. Pre-registered hypotheses

Each is fixed before looking at outcomes. Horizons and thresholds are listed here and
may not change after the first look.

| ID | Hypothesis | Data | Horizons | Primary test |
|---|---|---|---|---|
| H1 | Cliff unlocks above 2% of circulating supply within 14 days precede negative BTC-residual returns | DropsTab | 7 and 14 days around the event | Event study against **matched same-coin clean controls**; need at least 100 events to claim anything, otherwise "cannot decide" |
| H2 | Extreme funding (z-score) predicts reversal in BTC-residual returns | Hyperliquid | 24h, 7d | Incremental IC over M0 |
| H3 | Open-interest change times price predicts continuation or squeeze | Hyperliquid (forward only; no free OI history) | 24h | Forward-only IC |
| H4 | Rising protocol fees (30-day change) predict relative returns among DeFi coins | DeFiLlama | 30d, 90d | Cross-sectional rank IC |
| H5 | Smart-money netflow precedes positive residual returns | Nansen | 24-72h | Incremental IC |
| H6 | Regime features (MVRV, dormancy) improve regime classification; social volume adds nothing | Santiment | 7d | Incremental IC; **expected null for social volume** |

**Test count:** 6 hypotheses at 1-2 horizons is about 10 headline tests. Report all of
them, not only the successes.

## 5. Evaluation protocol

**Baseline M0 is rebuilt from the candle archive**, not taken from BHABIT's current score
(whose short-horizon relation is negative and whose 24-hour value is about zero; see the
scoring research and its audit). M0 uses volatility-normalised returns at 1, 7 and 30
days, realised volatility, relative volume against the coin's own median, and BTC beta
and BTC-residual momentum. Its own out-of-sample IC is the number a source must beat.

**Labels:** BTC-residual, volatility-scaled forward returns at 24h, 7d and (for H4) 30d
and 90d, with 0.2 / 0.5 / 0.9 / 1.2% cost scenarios reported side by side.

**Statistics (corrections learned from the scoring audit):**
* **Incremental IC:** rank correlation between the feature residualised on M0 and BTC,
  and the forward residual return, cross-sectional per time bucket; report the mean,
  the ICIR, and the share of buckets that are positive.
* **Uncertainty:** calendar-week or month blocks, not individual observations. With only
  months of data, say so and do not over-read the interval.
* **Controls:** matched same-coin controls, **excluding hours near a signal or event**
  (the audit showed 29% of controls were themselves signal hours and that it changed a
  result); BTC-neutral returns; placebo shuffles.
* **Overlap:** purged and embargoed walk-forward (embargo at least the horizon), not a
  single split; at least 12 months across rising, flat and falling BTC regimes.
* **Regime stability:** the effect's sign must hold in at least two of three BTC regimes
  (the audit showed several effects flip).
* **Multiple testing:** a headline result needs about t >= 3.0 (Harvey, Liu and Zhu,
  2016) and a Benjamini-Hochberg adjustment across the pre-registered list.

**Collinearity filter (Gemini's idea, kept):** drop any external metric whose rank
correlation with an M0 feature is 0.5 or more; it is already captured for free.

## 6. Go / no-go gates

A source moves to **shadow collection** (collected forward, not shown, not used in
alerts) only if all of the following hold on the covered subset:

1. Incremental out-of-sample IC of at least **+0.03** (and ICIR at least 0.5 as a
   secondary check), with a week-block interval excluding zero.
2. Positive in at least about **65%** of blocks and sign-consistent in at least two of
   three BTC regimes.
3. Survives clean controls and BTC-neutral returns.
4. For event studies: effect size larger than the realistic cost scenario (at least the
   0.5% scenario, reported at all four).
5. **Forward confirmation:** the same sign and at least half the size over at least
   8-12 weeks of forward-collected data.
6. Licence permits the intended use, and coverage is stated as "X% of coins".

A source is **discarded** if it fails (1) or (3). A source that passes backfill but not
forward confirmation stays on a watch list. **Paid conversion** (Nansen, Santiment) only
after (5), with a written cost cap and your approval. Anything that reaches production
also needs the retention and storage design from `docs/ops/PRODUCTION_VOLUME.md`.

## 7. Schedule

| Phase | When | Work | Cost | Decision |
|---|---|---|---|---|
| 0 | Days 1-3 | Step zero; build the local store and fetch harness; rebuild M0 and its baseline IC | $0 | Is M0's IC measurable? |
| 1 | Week 1 | Sources 1-3; start **forward daily snapshots** for every source from Day 1 (this clock cannot be recovered later) | $0 | First backfill results (H2, H4) |
| 2 | Week 2 | Run H2, H3, H4 under the protocol; first report with intervals and coverage | $0 | Continue, drop, or watch |
| 3 | Weeks 3-4 | DropsTab (if granted) and the H1 event study; Santiment free (H6); optional Nansen | $0-$25 | Spend decision (yours) |
| 4 | Weeks 5-12 | Forward confirmation; weekly check of the gates | $0 | Shadow, drop, or watch |
| 5 | Week 12 | Final report: gates, intervals, coverage, cost scenarios | | Adopt for shadow or stop |

Two clocks are the only time-sensitive items: the **DropsTab grant** (about 3 months, so
start the unlock pull early and store it) and the **Santiment Pro trial** (14 days; start
it only after the free tier justifies it).

## 8. What needs you (nothing here has been done)

1. **Universe and holdings:** a list of symbols you hold or care about.
2. **Your real fee tier or a fills export** to replace the assumed cost scenarios.
3. **DropsTab Builders application:** write it truthfully (a solo-operated crypto
   analytics site under evaluation). The draft in the Gemini research claims an
   established team, an annual vendor-stack decision and a liquidations pipeline; none
   of that is accurate and it should not be sent unedited. Contact addresses in that
   draft are unverified.
4. **Santiment free account** (and API key kept out of the repo).
5. **Nansen x402 budget:** payment is in USDC from a wallet you control. Decide a cap
   (suggested $25) or skip.
6. **Approval to start**, so that no account, message or payment happens by default.

## 9. Ownership (so the workstreams stay separate)

| Workstream | Owner | Boundary |
|---|---|---|
| Vendor facts, pricing, limits, outreach wording | **Gemini** (as written; not edited here) | I only checked and flagged its claims |
| 15-minute bars, cost-sensitivity grid, delayed-entry ledger | **Codex** | Pilot at `50c8d873` stays on its own branch |
| Matched controls, incremental IC, final evaluation, this plan | **Claude** | Docs only until the gates pass |

## 10. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Backfilled history is revised or relabelled (look-ahead) | `vintage` column; forward confirmation required |
| Survivorship (today's coin list) | PIT universe rule; report coverage; include delisted coins where the provider has them |
| Symbol ambiguity (124 DeFiLlama symbols) | Map by provider id (e.g. CoinGecko id), not symbol |
| Multiple testing | Pre-registered list; t >= 3.0; BH adjustment; report every test |
| Coverage looks like skill (feature exists only for large coins) | Compare with M0 **on the same subset** |
| Free-tier licence blocks production use | Licence table in step 0.3; "evaluate-only" flag |
| Shared IP rate limits hurt the live collector | 1 request per second per host; backoff; run off-peak |
| Cost creep | $0 default; written cap; no purchase without your approval |
| Findings overstated | Report intervals, coverage, regimes, and every failed test |

## 11. Definition of done for the trial

A single report that, for each source: states coverage as a percentage of the 407
coins and of your holdings; gives incremental IC with block intervals under clean
controls; shows regime sign stability; gives the cost-scenario results; states the licence
position; and ends with one of **adopt for shadow / watch / discard**. The default
outcome, consistent with what the existing evidence suggests, is that most sources are
discarded and one or two (likely funding history, unlocks, or protocol fees) earn a
forward test.
