# Claude to Codex handoff, 2026-10-19

Supersedes the summary in `HANDOFF_FOR_CODEX_2026-10-18.md` (still valid for
detail). Branch `claude/render-history-data` at `91d6035`, based on pinned
`56f1b418`. Nothing is merged to main or deployed. Every public request was
unauthenticated and at most one per 1.1 s. All live stores and the candle
archive were read from copies; no original script or store was changed.

Reviewed against your branch `codex/macro-chart-20261018` at `fb59304`
(next-run map, local narration, AMP worker).

Gemini's separate "master handoff" (six local agents, sentiment
architecture, research record) is checked line by line in
`MASTER_HANDOFF_REVIEW_2026-10-19.md`. Use that file, not Gemini's text.

## 1. What Claude built

| Area | Files | State |
| --- | --- | --- |
| RENDER/RNDR history and contract | `data/render-history/`, `docs/developer/RENDER_HISTORY.md`, `market-history.schema.json` | done, validated |
| Video parity (61 bars read from the video) | `RENDER_HISTORY.md` 5b, `data/render-history/video_reference_bars.json` | done |
| Study 1: +10% / -10% days | `MOVE_STUDY.md`, `scripts/move_study/continuation_vs_reversal.py`, `robustness.py` | done |
| Study 2: weekly pivots, macro anchors, Fibs | `LEVEL_STUDY.md`, `level_study.py` | done, preregistered |
| Study 2b: swing volume profiles | `VOLUME_PROFILE_STUDY.md`, `volume_profile_study.py` | done, preregistered |
| Study 2c: hourly absorption, macro-low breakdowns | `ABSORPTION_STUDY.md`, `absorption_study.py` | done, preregistered |
| Study 2d: profile shapes, balance breakouts, ledges | `PROFILE_SHAPE_STUDY.md`, `profile_shape_study.py` | done, preregistered |
| Study 3a: perp funding at +10% days | `FUNDING_STUDY.md`, `fetch_funding.py`, `funding_study.py` | done, preregistered |
| COTI-USD analysis | `COTI_ANALYSIS_2026-10-19.md` | done |
| Sentiment sources checked from this PC | `SENTIMENT_SOURCES_VERIFIED_2026-10-19.md` | done |
| Point-in-time (PIT) log and watcher | `backend/pit_log.py`, `backend/pit_watch.py`, `PIT_LOG.md` | running |

Tests: `python -I -m pytest -o addopts="" scripts/render_history scripts/move_study backend/tests/test_pit_log.py -q`
(59 pass). `-o addopts=""` because `pytest.ini` asks for pytest-cov.

## 2. Decisions with the user (keep)

1. RNDR and RENDER are separate series, never joined, even as a labelled
   composite. **SMA200 is unavailable for RENDER-USD** until the week of
   2027-12-13 (138 of 200 complete weeks now). Show it as unavailable, with
   the reason.
2. No all-time low or high is claimed from Coinbase data
   (`is_all_time_low` is always false).
3. No probabilities, targets or dates for a coin, from any study.
4. No venue or token stitching. Other venues' data stays in its own labelled
   series.

## 3. What the studies settled

All outcomes are forward returns minus volatility-matched peers on the same
day. Discovery 2022 to 2024, test 2025 to 2026-10-17 (hourly studies:
2025-10 to 2026-03 vs 2026-04 onward). Bonferroni in discovery, confirmed in
test, same sign.

| Study | Result | Chart consequence |
| --- | --- | --- |
| 1 | After a +10% day coins trail peers about 1.4, 2.1, 2.1% at 1/3/7 days, both periods and every year (about 9,000 events, 492 products incl. delisted). Concentrated in thin coins (under $1M/day) and high-volume coin-specific spikes (7 days -5.7% / -7.3%). Low-volume, market-driven rises barely fade. -10% days: nothing. | Approach wording only (section 5). Not a per-coin prediction. The volatility-matched control was added after the first run (disclosed), so Study 1 is not fully preregistered. |
| 2 | Weekly highs/lows, macro anchors, Fib 0.5/0.618/0.786 behave like placebo lines (0 of 24). | Never call levels support/resistance or imply a reaction. |
| 2b | POC, VAH, VAL, HVN, LVN behave like placebos (0 of 22), also on hourly-built profiles. | No "magnet", "highway" or S/R labels. |
| 2c | Hourly absorption candles: nothing replicates. Breakdowns through the macro low lag placebo breakdowns by about 1 point over 14 days (-0.83 / -1.06), but on years that suggested it. | If shown at all: small tendency, awaiting confirmation on data from 2026-10-18 onward. |
| 2d | P/b shapes, 3-day balance breakouts, volume ledges: nothing (0 of 22). | No continuation-signal labels. |
| 3a | Perp funding at the close of a +10% day does not separate spikes that hold from spikes that fade (negative vs crowded: fails). **Perp listing does, for thin coins:** spot-only thin coins gave back 2 to 3 points more over 7 days than perp-listed ones (-3.2% vs -1.1% discovery, -5.0% vs -1.7% test; replicates). Not causal. | Optional context: whether the coin has a Binance/Hyperliquid perp, with the scoped sentence in `FUNDING_STUDY.md`. Never show funding as a squeeze or continuation signal. |
| Causes (Gemini, 80 events) | The news/no-news split vanishes once only sources published before the move count. | Don't show cause categories. |

Bottom line: candle-built geometry (levels, ratios, profiles, patterns) adds
nothing beyond price and volume. The only robust signal is about the
approach: sharp, high-volume spikes in thin coins give back. Order flow
(taker side, book depth) was not testable from candles. The PIT log now
collects Hyperliquid book-depth proxies for later work.

## 4. Review of your `fb59304` (next-run map)

Good: nearby confirmed daily turns only, completed candles at the replay
cutoff, macro arithmetic collapsed and off by default, no probability or
date, nearest references required in narration. It answers the user's
"no future levels" complaint.

Requested changes:

1. **Drop the R1-R3 / S1-S3 labels.** R and S read as resistance and support,
   which Studies 2 and 2b found no evidence for. Suggest "Prior high 1-3" /
   "Prior low 1-3" (or H1/L1), keeping the existing "prior observations, not
   validated support/resistance" text.
2. **Daily 2-each-side pivots were not tested directly.** The studies used
   weekly pivots (Study 2) and daily swing legs (2b). Say so in the
   disclosure: "weekly-scale equivalents behaved like random lines at a
   similar distance in Coinbase USD 2022 to 2026."
3. **Add that limitation as a mandatory narration fact,** so the local model
   cannot leave it out (same mechanism as your required S1).
4. Keep the macro disclosure collapsed. The study gives no reason to promote
   recovery ratios.

## 5. What Codex can do now

In priority order; none of it needs Claude's files to change.

1. **The label and limitation changes above** (section 4).
2. **Approach context, when it applies.** If the last completed daily candle
   is +10% or more, show a dated, scoped note:
   "Sharp, high-volume rises in thinly traded coins have tended to give back
   part of the move over the following days (Coinbase USD, 2022 to 2026)."
   Use Study 1's rules for eligibility (columns from `build_panel` in
   `continuation_vs_reversal.py`, splits in `robustness.py`: `vol_ratio` =
   volume / prior 20-day median volume, at least 5x; liquidity = prior 20-day
   median dollar volume, thin under $1M; coin-specific = `ret1 - btc_ret`
   at least 0.15). When the rise is low-volume or
   market-wide, say the tendency was weak for such days, or show nothing.
   Never a number for this coin.
3. **RENDER acceptance from the validated files.** Use
   `data/render-history/series` and `weekly` (not live browser candles,
   which carry no completeness or cross-check). Fixture: `indicator_fixture`
   in `reference_parity.json`. SMA200 unavailable, as in section 2.
4. **Audit of `scripts/move_study/funding_study.py` against
   `FUNDING_STUDY.md`.** Study 3a has run (results in the doc), so this is now
   an audit, not a blind review. Most useful: check the one replicating result
   (F2, thin coins) for point-in-time leaks (window `(t, t+1]`), how
   `perp_status` is assigned, and symbol mapping (1000x prefixes, `kB`
   coins, the six excluded ticker collisions). Write findings to a file.
5. **Optional read-only PIT panel, later.** `~/.moonwalking/data/pit_context.sqlite`
   (open read-only, `mode=ro`) has Coinbase listings/status changes and
   Hyperliquid funding, open interest, mid and impact prices every 5 minutes.
   Show raw values with timestamps only. Study 3a found funding has no
   separating value, so never label funding as bullish, bearish or a squeeze.
   A "has a Binance/Hyperliquid perp" flag is defensible context (3a, F2).

Do not:
- touch the "Moonwalking Collector" task or port 5003, or the "Moonwalking
  PIT Watch" task and `~/.moonwalking/pit`;
- write to `pit_context.sqlite`, the candle archive or any live store;
- merge to main or deploy; merge older design branches; resume the cancelled
  broad consolidation (the Figma-ready design system stays as is);
- label anything support, resistance, magnet or signal on the strength of
  these studies.

## 6. Live infrastructure

- **PIT Watch task** (installed from `b379d66`): running. Every 5 minutes it
  polls Coinbase `/products`, the Coinbase status page and Hyperliquid
  `metaAndAssetCtxs`. State at 2026-10-19 16:15 UTC: 842 products in the
  registry (BASELINE), 50 incidents, 13 Hyperliquid passes, 2,314 per-asset
  snapshots (178 assets, 120 ticker-matched to Coinbase; tickers are not
  verified identities). One watcher restart at 15:25 UTC, recovered by the
  launcher. Logs in `~/.moonwalking/logs/pit-watch-*.log`.
- Positioning hooks in `sentiment_api.py` / `derivatives_positioning.py`
  write only when the service runs from this branch. The collector runs from
  `Moonwalking-Runtime`, which doesn't have them.
- **Collector:** untouched and running (health 200 when last checked).

## 7. In progress and open

- **Study 3a: done** (section 3 table, `FUNDING_STUDY.md`). Funding fails;
  perp listing replicates for thin coins.
- **Proposed Study 3b (not started, waits for the user):** Binance taker
  buy/sell delta from `data.binance.vision` kline archives on +10% days.
  Limits: cross-venue (Coinbase events, Binance flow, kept as separate
  series), and it needs a spot-pair identity map. After 3a this limit
  matters more: coins with no Binance listing, the spot-only thin coins that
  fade most, would be missing from 3b.
- Macro-low breakdown: first real out-of-sample check needs data after
  2026-10-18.
- A true all-time low needs a second, separately labelled source from 2020.
  Not started.
