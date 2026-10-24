# Deliverable 3 (revised): trial-ready data collection and testing plan

Revised 2026-10-24 on branch `claude/data-source-plan` (docs only). Planning only: no
code, accounts, purchases, outreach, trials or deployments are part of this document.
It builds on `REPOSITORY_INVENTORY.md`, `DATA_SOURCE_COVERAGE.md`, the corrected
`BHABIT_SCORING_RESEARCH.md` (read its corrections log first), and
`FIRST_EXPERIMENT_SPEC.md`. The separate Gemini vendor research is not edited.

## Revision notes (what changed from the first version, commit `3dfaf5c`)

| # | Change | Why |
|---|---|---|
| R1 | **Removed the automatic rejection of external features whose rank correlation with an existing feature is 0.5 or more.** Redundancy is now a diagnostic; usefulness is judged by out-of-sample incremental contribution (section 5). | A high correlation does not mean zero added information, and the rule was unsupported. |
| R2 | **Separated three stages:** research data collection (A), shadow evaluation (B) and production eligibility (C). Forward confirmation is required only for C. | The first version required forward confirmation before starting the collection that produces it. |
| R3 | **Rebuilt the schedule around outcome maturation.** A 12-week plan cannot confirm 30-day or 90-day outcomes (section 7). | 12 non-overlapping 30-day blocks need about 56 weeks; 90-day blocks need about 168. |
| R4 | **Aligned the test method with the corrected scoring research:** short horizons included, clean controls, de-duplication, tie-aware ranks, selection and entry assumptions stated. | The scoring audit found each of these mattered (corrections C1-C4). |
| R5 | **Verified the assets the plan relies on** before assuming them (section 1). | The first version assumed the candle archive and point-in-time records; the checks changed several statements. |
| R6 | **Tagged every statement** as verified, unverified, assumption or hypothesis (legend below). | To stop vendor claims and predictions blending into facts. |
| R7 | **Reviewed every acceptance threshold** instead of treating it as a rule (section 6). Several are underpowered or arbitrary; they are now defaults with stated reasons. | See the numbers in section 6. |
| R8 | **Reconciled with existing work** that the first version missed (section 2): the point-in-time log that has run since 2026-10-19 and the pre-registered daily studies on `origin/claude/render-history-data`. | They change priors (funding) and what data already exists. |

**Legend.** **[V]** verified by direct check, with date and source. **[U]** unverified
claim (source named). **[A]** assumption made for planning. **[H]** hypothesis to be
tested; never to be quoted as a finding.

## 0. Goal and ground rules

**Goal:** find out, cheaply and honestly, whether any external source adds information
beyond price, volume and the derivatives data BHABIT already has, for coin scoring and
portfolio risk guidance. A clean "no" is a successful outcome.

1. **Cost cap $0 by default.** Anything that costs money, needs an account, sends a
   message on BHABIT's behalf, or needs a crypto wallet is a user decision (section 9).
2. **Everything runs on your PC** and writes to local stores. Nothing is written to the
   production volume, and nothing is deployed, before Stage C.
3. **Official APIs and documented downloads only; no scraping; no region workarounds.**
   Several "free" tiers are evaluation or personal use only, and bhabit.net is a commercial
   site, so licence terms are a gate, not a footnote.
4. **At most 1 request per second per public host**, with backoff on any 429, because the
   live collector shares the IP.
5. **No keys in the repository or in chat.**
6. **Every test is pre-registered** (section 4) before outcomes are examined.

## 1. Verified availability of the assets this plan relies on

Checked on 2026-10-24 by reading the files directly.

| Asset | Status | Facts |
|---|---|---|
| **Local hourly candle archive** `~/.moonwalking/data/candle_archive.sqlite` | **[V] exists, intact** (`quick_check` ok) | 767 MB. 407 products, hourly candles 2025-10-01 to 2026-10-12 (about 3.04M rows). **312 products have history from the start of the window; 95 start later (new listings or late data).** Of the 312: **165 have at least 95% of hourly candles, 142 have 60-95%, 5 have under 60%.** A missing hourly candle inside a fetched window means no trades that hour, not a gap. **Only coins listed today are included (survivorship).** Lives on this PC only; not in git. |
| **Daily candle panel** (492 Coinbase USD products **including delisted**, 2022-01-03 to 2026-10-17) | **[V] exists, but only in another session's temporary scratchpad** (`.../render-historical-data-bf650f/.../scratchpad/daily_all`: 494 files, 28 MB) | Fragile: scratchpads are session-specific. Regenerable with `scripts/move_study/fetch_daily_all.py` on `origin/claude/render-history-data`. **This is the only survivorship-free price panel found.** Must be copied to a stable location before use. |
| **Downloaded funding files** (Binance monthly archives and Hyperliquid daily windows) | **[V] exist in the same scratchpad** (Binance 6,582 files, 35 MB; Hyperliquid 4,522 files, 20 MB) | The Hyperliquid cache covers daily windows around +10% event days only, **not** a full hourly series for every coin. |
| **Point-in-time log** `~/.moonwalking/data/pit_context.sqlite` | **[V] exists, intact, running** (updated 2026-10-24) | 47.5 MB. **Started 2026-10-19 13:53 UTC, so it holds about 5 days.** 843 products in `symbol_registry` (515 online, 328 already delisted at the baseline); **no listing history before 2026-10-19** (the first pass wrote `BASELINE` rows, not listings); 1 listing, 6 status changes and 62 incidents logged since; **1,378 Hyperliquid passes at about 5-minute spacing, 245,284 per-asset snapshots, 178 assets (120 matched to Coinbase products by ticker, not verified identity).** |
| **Historical point-in-time universe** (who was listed on a past date) | **[V] not available for backtests** | The PIT log cannot reconstruct 2025 or earlier. The daily panel above includes delisted products and is the nearest substitute. |
| **Hyperliquid funding history** | **[V] available** | `fundingHistory`: 500 hourly rows per request, paged forward. All **133** of your coins that have a Hyperliquid perp return history; **123 go back at least a year** (earliest record 2023-05-12, median 2024-02-14, latest first record 2026-09-08). **91 of those also have at least 95% hourly candle coverage.** |
| **Prior study outputs** | **[V] in git** on `origin/claude/render-history-data` | `data/move-study/*.json` and `events_all.csv` (derived, not raw), and the scripts. Not re-run by me. |

**Consequence for this plan:** forward collection is the only way to build a
point-in-time record of anything not already in `pit_context.sqlite`; historical
backtests must use the daily panel (survivorship-free) or the hourly archive
(survivorship-biased), and must say which.

## 2. Existing work this plan must not duplicate or contradict

* **Point-in-time infrastructure already exists and runs** (`backend/pit_log.py`,
  `backend/pit_watch.py` on `claude/render-history-data`; scheduled task "Moonwalking PIT
  Watch" *(memory; the log's own timestamps confirm it is running)*). Stage A should use it
  for Hyperliquid and Coinbase listing data, and add a separate store only for providers it
  does not cover. **Do not touch the task, its code folder or the log.**
* **Preregistered studies** [V as documents; results **not re-verified** by me]:
  after +10% days coins trail peers at 1/3/7 days, concentrated in thin coins and
  high-volume spikes; price-geometry features (levels, profiles, patterns) behave like
  placebos; **funding at the close of +10% days does not separate spikes that hold from
  spikes that fade**; **perp-listing status does, for thin coins**. Their decisions
  (no per-coin probabilities or targets; RNDR and RENDER never joined) stay in force.
* **Vendor endpoint checks from 2026-10-19** [V by that session]: DeFiLlama `/protocols`
  200 but `/emissions` (unlocks) 402; Hyperliquid `fundingHistory` 200; OKX funding
  history 200; Bybit 403; Binance 451; CryptoPanic 403; GeckoTerminal 403; Santiment
  anonymous GraphQL reachable; Coinalyze 401 without a key; Coinbase status page keeps only
  the last 50 incidents. Plan limits and prices were **not** re-verified there.
* **Their sample-size analysis** [U, not re-derived]: for a 5-point difference in 7-day
  return with 80% power they report about 641 events (alpha 0.01) or 848 (alpha 0.002);
  shock events run at about 32-37 a month, so forward-only collection for event studies
  would take on the order of 17-26 months.

## 3. Stages

| Stage | Purpose | Starts when | Gate to leave | What it is **not** |
|---|---|---|---|---|
| **A. Research data collection** | Build the evidence base: forward point-in-time snapshots and licensed backfills for every candidate source | **Immediately**, as soon as the licence, cost and rate-limit rules in section 0 are met | None based on performance (collecting cannot be gated on the results it produces) | Not used in any product surface |
| **B. Shadow evaluation** | Compute candidate features and scores offline; run the pre-registered tests; update results weekly | Once a source has enough history to compute a feature without look-ahead | Pre-specified decision rule per hypothesis (section 6): supportive / inconclusive / ruled out | Not shown to users, not used in alerts |
| **C. Production eligibility** | Decide whether a feature may appear in the product, and how it is labelled | After B is supportive **and** forward confirmation over the matured horizon **and** licence permits **and** a retention design exists | Product, legal and cost review (yours) | Not automatic; never based on backfill alone |

Rules: Stage A never waits for Stage B. A source can stay in A indefinitely at no
cost. **Forward confirmation is required only to enter C.** Dropping a source from A
requires an inconclusive-or-null B result *and* a stated reason (cost, licence, coverage).

## 4. Data collection design (Stage A)

**Where.** Hyperliquid and Coinbase-listing data: the existing `pit_context.sqlite`
(read-only access for analysis). Other providers: a new append-only
`external_features.sqlite`, outside the repository runtime and the production volume.

| Column | Meaning |
|---|---|
| `provider`, `endpoint`, `metric` | What was collected |
| `coin_key` | Bare symbol **plus** the provider's own id (mapping kept in a separate table; symbols collide, e.g. 124 DeFiLlama symbols; RNDR and RENDER stay separate) |
| `value` | The number |
| `source_ts` | Time the provider says the value refers to |
| `ingest_ts` | When **we** fetched it (UTC) |
| `vintage` | `forward` (collected live) or `backfill` (history fetched later) |
| `raw_ref` | Hash and path of the cached raw response |

**Point-in-time rules.** Filter on `ingest_ts` (the repository's own PIT rule is to
filter on `first_seen_utc`). A forward value is usable at t only if `ingest_ts` plus a
stated latency is at or before t. **Backfilled history is treated as optimistic** (providers
revise and relabel): it may reject a hypothesis or justify keeping a source in A, but it
cannot move a source into C.

**Raw cache.** Save every response with its hash so any number can be reproduced.

**Storage [A]:** Hyperliquid funding for 133 coins at hourly resolution is about 1.2M
rows (roughly 100 MB); DeFiLlama daily series for about 180 coins a few hundred thousand
rows. Both are small for a local disk.

## 5. Source trial cards

Priors reflect existing evidence; they set the order, not the conclusion.

| # | Source | Stage A pull | Budget | Covers | Prior | Needs from you |
|---|---|---|---|---|---|---|
| 1 | **Hyperliquid funding history** (keyless) [V] | Per coin, 500 hourly rows per request, up to the full available history | About 2,400 requests for the latest year (133 coins x about 18); **full history is 5,594 requests (2.76M rows, about 250 MB), about 103 minutes at 1.1 s per request** [V: computed from each coin's measured first record] | 133 of 407 coins [V]; 123 with at least a year [V] | **Low [H]**: the prior study found no separating value at +10% days (Spearman about 0); this tests the general cross-section instead | Nothing |
| 2 | **DeFiLlama public API** [V free; `/emissions` is paid, 402] | `/protocols`, fees and TVL series for matched protocols | About 400-600 requests | **At most** 256 of 407 coins by symbol and 179 with fee data; both are upper bounds because 124 symbols are ambiguous [V, my measurement] | Medium for 30-90 day relative returns among DeFi coins [H] | Nothing |
| 3 | **Extend Coinbase candle history** (public) | Rebuild or extend the hourly archive; copy the daily panel to a stable folder | About 11,000 requests per extra year of hourly data | All listed coins; delisted only in the daily panel | Infrastructure, not a hypothesis | Nothing |
| 4 | **Santiment free tier** [V: 1,000 calls/month, 30-day lag; unverified whether one call returns a full series] | MVRV, dormancy, exchange flows for about 40-60 majors | About 300 of 1,000 monthly calls [A] | Majors only | Medium-low [H] | A free account and key |
| 5 | **DropsTab Builders** [V: free up to 3 months; limits and licence terms **not** verified] | One full unlock and vesting pull, stored locally | Unknown until granted | Unknown | **Highest motivation, lowest verified access** [H] | A truthful application |
| 6 | **Nansen** [V: free 100 trial credits with a daily top-up to 10; x402 at $0.01 basic, **$0.05 smart-money**] | Smart-money netflow, about 100 coins | About 200 calls = **about $10**; a $25 cap is sensible [A] | Majors and large DEX tokens [U] | Medium [H] | A funded wallet; your decision |
| 7 | **Santiment Pro trial** [U: 14 days; 5,000 calls] | Recent 30 days and hourly series | Within 5,000 calls | Majors | Only after 4 | Start the clock deliberately |

**Not trialled [U, from Gemini's research, not verified by me]:** Zerion (a portfolio
feature, not a predictor), Glassnode and CryptoQuant (BTC/ETH-centred, API gated),
LunarCrush (noisy, paid), CryptoDataDownload (duplicates free Coinbase history).

## 6. Pre-registered hypotheses and the review of acceptance thresholds

### 6.1 Hypotheses [H]

| ID | Hypothesis | Data | Horizons | Primary test |
|---|---|---|---|---|
| H1 | Cliff unlocks above 2% of circulating supply within 14 days precede negative BTC-residual returns | DropsTab | 7 and 14 days around the event | Event study against matched same-coin clean controls |
| H2 | Extreme funding (rolling z-score) predicts reversal in BTC-residual returns across **all coin-days**, incremental to a price/volume baseline | Hyperliquid | 24h, 7d | Incremental out-of-sample IC; **see `FIRST_EXPERIMENT_SPEC.md`** |
| H3 | Open-interest change times price predicts continuation or squeeze | Hyperliquid, **forward only** (no free OI history) | 24h | Forward-only IC |
| H4 | Rising protocol fees (30-day change) predict relative returns among DeFi coins | DeFiLlama | 30d, 90d | Cross-sectional rank IC |
| H5 | Smart-money netflow precedes positive residual returns | Nansen | 24-72h | Incremental IC |
| H6 | Regime features (MVRV, dormancy) improve regime classification; social volume adds nothing | Santiment | 7d | Incremental IC; **null expected for social volume** |

About 10 headline tests in total (6 hypotheses at 1-2 horizons). All are reported.

### 6.2 Review of the thresholds used in the first version

None of these is a universal statistical rule. Each is reclassified below.

| Threshold in v1 | Justification found | Problem | Revised treatment |
|---|---|---|---|
| Incremental IC at least **+0.03** | A common rule of thumb in quantitative practice; **no source verified** [U] | **Underpowered:** with block-mean sd 0.04-0.09 [A] the smallest effect detectable at 80% power is **0.073 (sd 0.09) or 0.032 (sd 0.04) over 12 blocks**, **0.035 / 0.016 over 52 blocks** (table A below). Economically, an IC of 0.03 gives a gross long-short decile spread of about 0.5% at 24h and 1.3% at 7d (normal approximation, table D), **below or near a 0.9% round-trip cost** | Not a pass/fail rule. Use a **minimum effect of interest** set from the cost scenario and horizon (table D), then a **power calculation** that states how many blocks are needed to detect it |
| **ICIR at least 0.5** "(t > 2)" | Gemini's claim [U] | ICIR 0.5 gives t = 0.5 x sqrt(K) = **1.73 for K = 12 blocks, 2.0 only at K = 16** | Drop as a gate; report ICIR as a descriptive number with K |
| **At least 65% of blocks positive** | Arbitrary | If the true effect is zero the chance of reaching it is **19% at K = 12, 8% at K = 26, 1.8% at K = 52** (table C): nearly uninformative at small K | Report the share and an exact binomial interval; no fixed cut-off |
| **t at least 3.0** | Harvey, Liu and Zhu (2016) [V citation]; derived for equity factors; the paper itself argues 3.0 may be too low | Not crypto-specific; ignores the actual number of tests | Use a **family-wise or false-discovery correction over the real pre-registered list (about 10 tests)**; quote 3.0 as a reference only |
| **Sign consistent in at least 2 of 3 BTC regimes** | Motivated by the scoring audit, where effects flipped | The three regimes have unequal sample sizes and a regime can contain very few independent blocks | Report each regime with its block count; treat sign flips as a robustness *finding*, and require the minimum block count before reading a regime at all |
| **Forward confirmation 8-12 weeks, at least half the size** | Arbitrary | Depends on horizon; see section 7. 8-12 weeks gives **about 7-11 weekly blocks for 7d (after embargo; 8-12 for 24h), about 1 for 30d, none for 90d** | Required **only for Stage C**, per horizon, using the matured-block counts in section 7 |
| **At least 100 events** for event studies | Arbitrary | The other session's analysis suggests **hundreds** are needed for a 5-point difference [U] | Require a power calculation per event study; below that the answer is "cannot decide" |

**Table A, minimum detectable mean IC** (two-sided alpha 0.05, 80% power, 2.80 x sd / sqrt(K), independent blocks):
| sd of block-mean IC | K = 12 | K = 26 | K = 52 | K = 104 |
|---|---|---|---|---|
| 0.04 [A] | 0.032 | 0.022 | 0.016 | 0.011 |
| 0.09 [A: the observed weekly sd of the current score's IC] | 0.073 | 0.049 | 0.035 | 0.025 |

**Table C, chance of at least 65% positive blocks if the true effect is zero:** K = 12:
0.194; K = 26: 0.084; K = 52: 0.018; K = 104: 0.001.

**Table D, economic reading of an IC** (normal approximation; horizon standard deviations
24h 5%, 7d 12%, 30d 25% are [A]): IC 0.03 gives a long-short decile spread of 0.53% /
1.26% / 2.63% and a long-only top-decile edge of 0.26% / 0.63% / 1.32%; IC 0.05 gives
0.88% / 2.11% / 4.39% and 0.44% / 1.05% / 2.19%.

### 6.3 Decision rule that replaces the fixed gates

For each pre-registered test the plan fixes, **before looking at outcomes**: (a) the
minimum effect of interest from the cost scenario and horizon; (b) the number of
independent blocks needed to detect it with 80% power; and (c) the **three-way
outcome**: **supportive** (interval excludes zero and the lower bound exceeds the
minimum effect, with the family-wise correction applied); **ruled out** (the interval's
upper bound is below the minimum effect); **inconclusive** (anything else, including too
few blocks). **Inconclusive is a legitimate result and keeps the source in Stage A.**

## 7. Schedule, corrected for outcome maturation

A forward observation is only usable once its outcome has matured. Starting collection
on day 0:

| Horizon | First outcome matures | Weeks until 12 non-overlapping blocks exist (plus an embargo of one horizon) | Blocks available at week 12 |
|---|---|---|---|
| 1 hour / 24 hours | Day 1 | About 2 / 2 | About 84 daily blocks |
| 7 days | Day 7 | About 13 | About 11 |
| 30 days | Day 30 | **About 56** | About 1 |
| 90 days | Day 90 | **About 168 (about 3.2 years)** | 0 |

Consequences: **a 12-week programme can confirm only 24-hour and 7-day outcomes.**
30-day claims need roughly a year of forward data; 90-day claims cannot be confirmed
forward within any plan shorter than years, so they must rest on **historical walk-forward
evidence from the daily panel** (2022-2026, about 19 non-overlapping 90-day blocks and about
58 non-overlapping 30-day blocks across 1,748 days, before embargoes and the
discovery/test split [A: arithmetic from the date range]) and are labelled
*historical only* until forward blocks accumulate.

| Phase | When | Work | Cost |
|---|---|---|---|
| 0 | Days 1-3 | Section 1 asset checks acted on (copy the daily panel to a stable folder); verify the PIT log is still running; build the Stage A store and fetch harness; rebuild the price/volume baseline | $0 |
| 1 | Week 1 | Sources 1-3; **start forward daily snapshots for every source (Stage A clock starts here and cannot be recovered)** | $0 |
| 2 | Weeks 2-3 | First experiment (`FIRST_EXPERIMENT_SPEC.md`); report with intervals and coverage | $0 |
| 3 | Weeks 3-6 | DropsTab (if granted) and the H1 event study; Santiment free (H6); optional Nansen | $0-$25 |
| 4 | Weeks 6-14 | Forward blocks accumulate; **Decision D1 at week 14** for 24h and 7d horizons only (about 8-12 weekly blocks after embargo) | $0 |
| 5 | Around week 30 | **Decision D2** for 30-day horizons (about 4-6 blocks: still likely inconclusive) | $0 |
| 6 | Month 14+ | **Decision D3** for 30-day (about 12 blocks) and a first look at 90-day | $0 |

The only time-sensitive items are the **DropsTab grant (up to about 3 months)** and any
**Santiment Pro trial (14 days) [U]**; start neither until the preceding phases justify it.

## 8. Evaluation protocol (consistent with the corrected scoring research)

* **Baseline M0 is rebuilt from the candle archive**, not BHABIT's current score, whose
  short-horizon relation is negative (scoring research C1) and whose 24-hour value is
  about zero (C2). M0: volatility-normalised returns at 1, 7 and 30 days, realised
  volatility, relative volume against the coin's own median, BTC beta and BTC-residual
  momentum. Add the prior studies' context features as stratifiers: **perp-listing status**
  and **thin coin after a high-volume spike** (scoring research C9).
* **Horizons:** 1h and 4h for fast inputs (funding, flows), 24h and 7d for all, 30d and 90d
  where a source is slow (fundamentals, unlocks). Never one blended number.
* **Labels:** BTC-residual, volatility-scaled forward returns with an explicit **entry
  assumption** (next bar's open, not the signal-time price) and cost scenarios 0, 0.2, 0.5,
  0.9 and 1.2%, each an assumption until your fee tier is known.
* **Statistics:** tie-aware rank correlation; incremental IC = correlation between the
  feature residualised on M0 and BTC and the forward residual return; **de-duplicate
  overlapping observations** (one per coin and horizon window); **calendar-block**
  uncertainty with the number of blocks stated; purged and embargoed walk-forward with
  embargo at least the horizon; at least 12 months and rising, flat and falling BTC regimes.
* **Controls:** matched same-coin controls **excluding any hour within 3 hours of a
  signal or event** (scoring research C3: 29% of unfiltered controls were themselves
  signal hours); BTC-neutral returns; placebo shuffles; negative controls.
* **Universe:** report results on the **covered subset** and say so; compare with M0 on the
  **same subset**; flag survivorship whenever the hourly archive is used instead of the
  daily panel.
* **Redundancy (replaces the correlation filter):** report correlations and variance
  inflation as **diagnostics**. Judge a feature by **nested out-of-sample comparison**
  (M0 versus M0 plus the feature, same folds), with regularisation, and by permutation
  importance. A feature highly correlated with M0 may still add information; a feature
  that adds none under this test is dropped because of that result, not because of its
  correlation.

## 9. What needs you (nothing here has been done)

1. A list of symbols you hold or care about (for coverage).
2. Your real fee tier or a fills export, to replace the assumed cost scenarios.
3. **A stable home for the daily panel** (currently in a temporary scratchpad), or
   approval to re-fetch it (about 3,000 public requests [A]).
4. The **DropsTab Builders application**, written truthfully (a solo-operated crypto
   analytics site under evaluation). The draft in the Gemini research claims an
   established team, an annual vendor-stack decision and a liquidations pipeline; **none of
   that is accurate**, and its contact addresses are unverified. It should not be sent
   unedited.
5. A Santiment free account (key kept out of the repository).
6. A Nansen x402 cap (suggested $25) or a decision to skip.
7. Approval to start, so no account, message or payment happens by default.

## 10. Ownership

| Workstream | Owner | Boundary |
|---|---|---|
| Vendor facts, pricing, limits, outreach wording | **Gemini** (as written; not edited here) | I only checked and flagged claims |
| 15-minute bars, cost-sensitivity grid, delayed-entry ledger | **Codex** | Pilot `50c8d873` stays on its own branch |
| PIT log, daily studies, funding study | **The `render-history-data` session** | Do not touch its task, folder or log |
| Matched controls, incremental IC, this plan | **Claude** | Docs only until a stage gate says otherwise |

## 11. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Backfilled history revised or relabelled | `vintage` column; backfill never moves a source into Stage C |
| Survivorship (today's coin list) | Prefer the daily panel (includes delisted); state which panel any result used |
| Symbol ambiguity | Map by provider id, not symbol |
| Multiple testing | Pre-registered list; correction over the real test count; report every test |
| Coverage looks like skill | Compare with M0 on the same subset |
| Free-tier licence blocks production use | Licence check before Stage C; "evaluate-only" flag |
| Underpowered tests read as findings | Section 6.3 three-way outcome; power stated up front |
| Fragile inputs (scratchpad panel) | Copy to a stable folder before use (section 9, item 3) |
| Shared IP rate limits | 1 request per second per host; off-peak |
| Cost creep | $0 default; written cap; no purchase without approval |

## 12. Definition of done for the trial

A single report that, for each source, states coverage as a percentage of the 407 coins
and of your holdings; gives incremental IC and decile spreads with block counts and
intervals under clean controls; shows regime behaviour with block counts; gives the
cost-scenario results; states the licence position and the verified/unverified status of
each vendor fact; and ends with one of **supportive / inconclusive / ruled out** per
hypothesis and horizon. The default expectation, given existing evidence, is that most
sources end as ruled out or inconclusive and one or two earn continued forward collection.
