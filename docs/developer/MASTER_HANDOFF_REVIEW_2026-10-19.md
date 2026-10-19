# Gemini's master handoff, checked by Claude (2026-10-19)

Gemini wrote a "Master Architectural & Research Handoff for Codex" (in the
user's Gemini chat, not in the repo). This file is its checked version.
**Codex: use this together with `HANDOFF_FOR_CODEX_2026-10-19.md`.** Where
Gemini's text and this file disagree, this file was checked against the repo
and data on 2026-10-19. Gemini's text was not.

Verdicts: **OK** = matches the repo or data. **Fix** = wrong as written,
corrected here. **Unverified** = not checked from this machine; don't build on
it without checking. **Don't build** = conflicts with a user decision or a
study result.

## Section 1: six local Qwen agents and the guardrail script

**Recommendation: don't adopt the six-agent suite.** Keep your current
design (the model picks evidence IDs, Python renders every word and number).
It is strictly safer than free prose plus a filter.

| Item | Verdict | Notes |
| --- | --- | --- |
| Hardware tiers, `ollama pull` list (qwen3:8b/14b/30b-a3b, qwen3.8:27b, qwen3-coder:30b, qwen2.5-coder) | Unverified, don't build | The machine already runs `qwen3.5:9b` (your `LOCAL_CHART_NARRATION` doc). Your rule is no model download without the user asking. "qwen3.8:27b" was not checked to exist. |
| temperature 0, top_k 1, seed 42 | OK, optional | Your narration already uses temperature 0. Adding a fixed seed is harmless. |
| "Omit `think: false`" (Ollama issue #14850) | Unverified | Your accepted runs use thinking off with structured output. Don't change a working configuration on an unchecked issue number. |
| Agent 1, chart translator | Superseded | Your bounded narration already covers this, more safely. Its fields mention "the $0.1338 invalidation threshold" and "2.31x 30d volume": the first is FET-specific trade wording, the second has no source in the repo. |
| Agent 2, data-hygiene triage | Don't use an LLM | The severity classes are computed in Python anyway. A deterministic status line is enough; an LLM adds risk without adding information. |
| Agent 3, social classifier | Don't build yet | Its inputs (RSS, Farcaster, Reddit, GitHub releases in `pit_context.sqlite`) don't exist. The PIT log currently holds Coinbase products/status and Hyperliquid snapshots only. |
| Agent 4, divergence narrator | Don't build yet | Its inputs are unvalidated tier scores (below). No study has tested sentiment divergence. |
| Agent 5, anti-FOMO / execution hygiene | **Fix**, partly don't build | Its base rate is attached to the wrong group (next table). "CHASING_HAZARD" badges on a specific coin come close to a per-coin prediction, which the user ruled out. At most, use the scoped approach sentence in section 5 of the 2026-10-19 handoff. |
| Agent 6, offline dev helper | Not runtime | No objection as a personal dev tool; not part of the product. |
| `local_qwen_guardrails.py` | Use only as a CI check on the rendered catalog | (1) It bans "support"/"resistance" even when negated, so your own required disclosure ("not validated support/resistance") would fail it. (2) The number whitelist breaks on formatting (1.7048 vs 1.70480, signs and % dropped). (3) With ID selection, the model emits no numbers at all. Run a version of it as a unit test over every catalog sentence instead, with a negation allowlist. |

## Section 2: sentiment architecture

| Claim | Verdict | Notes |
| --- | --- | --- |
| `GET /api/sentiment/latest` goes through `EnhancedSentimentAggregator` | **Fix** | `backend/sentiment_aggregator_enhanced.py` is a 4-line deprecated shim that re-exports `sentiment_aggregator.get_sentiment_for_symbol`. Read `sentiment_aggregator.py`. |
| "Retire the MD5-seeded random fallback" | **Fix** | That fallback is described in `SENTIMENT_ARCHITECTURE.md` (Scenario 2), but no MD5-seeded sentiment remains in `backend/*.py`; the MD5 calls left are cache keys in `rss_handler.py`, `chinese_sources.py` and `utils_rate_limiter.py`. The doc is stale. Fix the doc, and check the current fallback path in `sentiment_aggregator.py` before assuming. |
| One-Board contract (`sentiment_meta` ok / staleSeconds / lastOkTs / lastTryTs / error; never fabricate; keep last_good) | OK | `SENTIMENT_ONE_BOARD.md` exists. Keep these rules. |
| Divergence Warning 0.25 / Critical 0.40 | OK as documented | In `SENTIMENT_SOURCE_SALVAGE_PLAN.md`. The live `sentiment_aggregator.py` uses `divergence_threshold` 0.12. The two disagree; the 0.25/0.40 values are a plan, not running code. Untested by any study. |
| Tier weights 0.85 / 0.70 / 0.50 / 0.30 and the weighted formula | Partly OK | Tiers are in `data_aggregator.py` as trust ranges (tier1 0.8 to 1.0, ...). The weighting has never been validated against outcomes. Context priority only, as Gemini says. Never a signal. |
| Source roles, staleness windows | OK as a plan | From the salvage plan. Not all of it is built. |
| Binance 451, Bybit 403, OKX and Hyperliquid live, Coinalyze needs a free key | OK | Tested from this PC (`SENTIMENT_SOURCES_VERIFIED_2026-10-19.md`). Don't work around the regional blocks. |
| CryptoPanic free tier gone | OK in effect | Its public endpoint returned 403 here. `rss_handler.py` still calls it; remove that call. |
| CCData/CryptoCompare, Glassnode, Dune SIM retirement dates; Reddit pre-approval; X pricing; DEX Screener / GeckoTerminal limits; Dune credits | Unverified | Gemini's claims. Check the provider's own page before building on any of them. |
| Crypto lexicon (bullish/bearish word lists) | Don't surface | Words like "breakout" and "golden cross" are exactly what the studies found no edge in. Don't use the lexicon to colour any chart wording. |

## Section 3: research record

Mostly accurate. Corrections:

| Claim | Verdict | Correct version |
| --- | --- | --- |
| "9,034 +10% up-moves" | Approximately | 4,847 discovery + 4,155 test at 1 day (9,002); counts vary slightly by horizon. |
| "All +10% days trail by -1.9% to -2.2% over 7 days; -1.6% next day" | OK | Vs volatility-matched peers: 7 days -1.90% / -2.20%, 1 day -1.39% / -1.34%. "-1.6% next day" is the *plain-return* view (buying at the close, before costs). Don't mix the two. |
| "Calendar-day equal weighting makes the fade -2.4% to -4.8%" | OK | 1 day -2.4% / -2.8%, 7 days -3.7% / -4.8%. |
| "+10% shock spikes **in <$1M/day coins** faded -5.7% to -7.3%" (Agent 5) | **Fix** | -5.7% / -7.3% (7 days) is for **high-volume (5x+), coin-specific (15+ points above BTC) spikes in all liquidity tiers**. Thin coins (<$1M) as a group: -2.4% / -2.7% at 7 days. Separate findings; don't combine them into one number. |
| "Level touches on shock spikes gave back +6.0% to +7.8%" | Fix the framing | +6.0% (Study 2 pivots) and +7.8% (Study 2b POC) are descriptive, not tested. Placebo lines show the same pattern, so it is the shock, not the level. Never cite them next to a level. |
| "46 passing unit tests" | Update | 59 tests across `scripts/render_history`, `scripts/move_study` and `backend/tests/test_pit_log.py`. They test code, not hypotheses. |
| Study 1 partly post hoc; 2 to 2d preregistered | OK | |
| Study 2, 2b, 2c, 2d numbers | OK | Match the study docs. |
| Study 3a "6,256 monthly/daily archives" | Fix | Monthly funding archives only. The first run stopped at 3,897 on a dropped connection; it resumed with retries (`d987304`). |
| Study 3b "ready after 3a" | Fix | Proposed only. Needs the user's go-ahead, a spot-pair identity map and a committed design. Cross-venue limits apply (Coinbase events, Binance flow). |

## Section 4: PIT watcher and order-flow ideas

| Claim | Verdict | Notes |
| --- | --- | --- |
| Task, paths, cadence, 842 products, 50 incidents, 178 Hyperliquid perps | OK | Running. |
| "Verified live on RENDER: mid 1.8195, impact bid 1.8183, ask 1.8211" | OK as a past snapshot | Latest row (2026-10-19 16:35 UTC): mid 1.8116, impact bid 1.81109, impact ask 1.81293, funding 0.0000125/h, OI 1,286,577 coins. Snapshots change every 5 minutes; never hard-code them. |
| Book asymmetry from impact prices | OK as a measurement | `(mid - impact_bid)/mid` vs `(impact_ask - mid)/mid`. "Path of least resistance" is an untested interpretation; show the two costs, not a direction. Hyperliquid's book, not Coinbase's. |
| On-demand Coinbase `/book?level=2` and `/trades` for an opened coin | OK as an idea, check first | Public endpoints. Keep to 1 request per second, server side, cached, never from the browser. For `/trades`, confirm in Coinbase's current docs that `side` is the maker side before computing signed delta. Whale-print thresholds ($5k / $25k) are arbitrary; label them as display filters. Nothing here is tested; show raw measurements, no "absorption" verdicts. |

## Section 5: video and chart wording

| Claim | Verdict | Notes |
| --- | --- | --- |
| Log price axis; Oct 2025 wick 0.5454 on the video's index; Coinbase 0.651 | OK | `RENDER_HISTORY.md` 5b. The video is TradingView's aggregated `RENDERUSD` index (RNDR prices before mid-2024). |
| "SMA readings 1.6998 / 3.1332 / 3.7009 from the live 12 Oct bar" | OK, but label | Those are the **index's** values, live bar. SMA200 3.7009 needs RNDR history; for Coinbase RENDER-USD SMA200 stays unavailable. On 5 Oct (complete week) our values match the video's legend: 1.7048 / 3.1839. |
| FET replay: macro high 3.485, macro low 0.1338, close 0.1567, 0.786 at 2.7678 (+1,666.31%) | Unverified by Claude | Claude reproduced the FET timing figures (0.1843 low, 0.2884 high, touches), not these. Check them against your engine's fixtures. |
| "Prior Broken Pivot Low (Overhead Reference)", three dates per pivot, no S/R/magnet/highway/target wording | OK | Consistent with the studies. Also rename R1-R3 / S1-S3 (2026-10-19 handoff, section 4). |
| "Disclose the $0.1338 invalidation threshold" | Fix the word | "Invalidation" is trade-plan language. Say "the macro low the calculation is anchored to" and show the price. |
| "8 UI wording rules" | Unverified | No list of eight rules was found in this branch. If it is in your branch, keep it there as the source. |

## What this changes for Codex

Nothing in the priority list of `HANDOFF_FOR_CODEX_2026-10-19.md` section 5
changes. Additions:

1. Add a unit test that scans every narration catalog sentence for
   predictive or S/R words (Gemini's denylist plus a negation allowlist).
2. When you next touch sentiment: read `sentiment_aggregator.py`, not the
   deprecated shim. Correct the MD5 fallback note in
   `SENTIMENT_ARCHITECTURE.md`. Remove the dead CryptoPanic call in
   `rss_handler.py`.
3. Don't start the six-agent suite, the social classifier, the divergence
   narrator or execution badges. Each needs data that doesn't exist yet or a
   study that hasn't been run.
