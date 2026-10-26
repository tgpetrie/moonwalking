# Funding comparison: frozen protocol

Written 2026-10-26 on branch `claude/funding-comparison` (from `codex/scoring-funding-audit-20261025` at
`d7b1cfa`). **Frozen before any funding value was joined to any return or label.** Before this was committed,
the only funding data inspected was the structure of one coin's collected history (AAVE: 28,534 hourly rows, 2023-07-18 to
2026-10-18, no duplicate stamps, two missing hours). No score, IC or event was computed from funding. Changes after this commit go
under "Amendments" with a reason. Research only: no production code, store, purchase or merge.

Legend: **[V]** verified; **[U]** unverified; **[A]** assumption; **[H]** hypothesis.

## 1. Question

Does adding Hyperliquid funding to the corrected price/volume baseline improve the out-of-sample ranking of next-day and
next-week BTC-residual returns, **on identical coins, dates and rows**? Prior [H]: no. The baseline on the 133-candidate cut
had 7-day IC +0.011 (interval including zero), so there is little for funding to add at 7 days; an earlier event-day study on another
branch (not re-verified) found no separating value from funding. The earlier 133-candidate baseline figures
(+0.053 and +0.011) do **not** apply here; the baseline is recomputed on the matched rows (section 4).

## 2. Inputs

* **Map:** `docs/research/results/funding_identity_audit_20261025/APPROVED_FUNDING_MAP.json` (127 Coinbase products, exact
  Hyperliquid names, price-unit factor 1 or 1,000, **funding multiplier 1 for all**). The five held products (AI, DOOD, GRASS, PONS,
  USELESS), BTC (benchmark) and the original 133-entry file stay separate and are not used.
* **Prices, features and labels:** exactly the corrected baseline (`scripts/scoring_experiment`, config unchanged,
  `SCORING_BASELINE_PROTOCOL.md` with corrections C1-C3). No baseline code or setting changes.
* **Funding:** `fundingHistory` responses stored byte-for-byte with request, capture time and SHA-256 in
  `~/.moonwalking/data/hl_funding_20261025/raw/<product>/page_NNNN.json` (local, not in Git). Fields: `fundingRate` (hourly, as
  reported), `premium`, `time` (ms). Requested to 2026-10-19 00:00 UTC inclusive.

## 3. Timing, gaps and the funding features (fixed now)

**What the timestamp means [V from documentation, residual [U]].** Funding is paid hourly; the rate is the average premium
sampled every five seconds over the hour plus an interest term, so a value cannot be known before its hour has elapsed. Stored stamps fall a few
milliseconds after the hour (for example 00:00:00.105). The documentation does not say whether a stamp marks the end or the start of
the averaging hour [U]. The design therefore does not rely on it:

* **Primary (lagged by one day):** the day-d decision uses only the funding prints stamped on UTC day d-1 (stamps from
  d-1 00:00:00 up to but excluding d 00:00:00). Even if a stamp marks the start of its hour, all of its information was available
  more than 23 hours before the decision time (00:00 UTC on d+1).
* **Sensitivity (same day):** prints stamped on UTC day d (00:00 through 23:00). The 23:00 print would be known only at the decision instant if the
  stamp marks the hour start; this variant is therefore reported as less conservative.
* **Entry** remains the open of d+1. Labels, eligibility and the baseline are unchanged.

**Daily value.** The mean hourly `fundingRate` over the day's prints, **only if the day has at least 20 of 24 prints**; otherwise the day is
missing. **No forward-fill** across missing hours, before the first observed print, or after the market stops returning funding. Identical duplicate stamps are
dropped; conflicting duplicates exclude that day. All counts are reported. The rate is used as reported for every product (the audit
established that the four `k` contracts need no rate multiplier).

**Primary feature `fz`.** For decision day d with lagged funding day L = d-1: the z-score of the daily mean on day L against the daily means of the 30 days
L-29..L (needs at least 25 valid days among them and non-zero standard deviation). It is then converted to a within-day rank-normal
score among **matched** coins (same convention as the other 11 inputs) and called `z_fz`. Warm-up is therefore at least 30 days of own funding history. Descriptive
alternatives (not part of the primary tests): the daily mean level (`z_fl`, rank-normal) and the 7-day mean level.

## 4. Matched rows and models

A **matched row** is an eligible baseline row (date, product) that is in the approved map **and** has a non-missing `fz` under the primary lag. Every model
below is fitted and evaluated on exactly those rows; days with fewer than 20 matched coins are excluded from every model's
IC (counted). The matched cross-section is much smaller than the full baseline universe and starts later (funding begins 2023-05), so the
walk-forward fits begin when at least 5,000 labelled training rows exist before the embargo cutoff (the baseline rule); that date, the
number of matched rows, coins per day and weeks in each phase are reported before any comparison.

| Model | Inputs | Training and evaluation rows |
|---|---|---|
| **M0-matched (the comparator)** | the 11 baseline inputs, same ridge, grid, purge and monthly refit | matched rows only |
| **M1** | the 11 inputs + `z_fz` | the same matched rows, same folds, same penalties grid |
| M0-full (context) | the baseline model fitted on the full eligible universe (as in the baseline results) | scored on the matched rows only |
| Funding alone (descriptive) | `z_fz` as a single ranking | matched rows |

Splits as the baseline: discovery decision days through 2024-12-23 (walk-forward predictions begin once the training rule is met), test 2025-01-01 to
2026-10-10, 7-day embargo of labels. Discovery runs first and may freeze only the sign conventions below; no feature, window, threshold or penalty
changes after it. The test phase is run once; the driver refuses without a matching discovery result, as in the baseline.

## 5. Tests

**Two primary tests** (1-day and 7-day), Bonferroni level 0.025 each (97.5% intervals):
**incremental IC = mean over weeks of the daily (IC of M1 minus IC of M0-matched)** on identical days, week-block bootstrap, plus the 4-week moving-block
interval, the per-weekday non-overlapping check, and block counts. Minimum effect of interest **+0.02** (from `FIRST_EXPERIMENT_SPEC.md`; cost arithmetic there).

* **Supportive:** test difference at least +0.02, interval excludes zero, discovery difference positive, and the sign of the `z_fz` coefficient the same in discovery and test fits.
* **Ruled out:** the upper bound of the test interval is below +0.02.
* **Inconclusive:** anything else, including too few blocks. A negative difference (the added input hurts out of sample) is reported as such and is
  not "supportive". Funding's sign may be positive or negative (two-sided); the ridge learns it, and the coefficient sign is recorded.

**Secondary (descriptive, not tested for significance beyond intervals):** (a) incremental IC by residualisation: each day regress `z_fz` on the M0-matched prediction
(with intercept) and take the IC of the residual with the label; (b) funding alone and the level feature; (c) extreme-funding events,
`fz >= +2` and `fz <= -2` on the raw rolling z, against clean same-coin controls and the same-day matched universe (same
control rules as the baseline), sign frozen from discovery; (d) by BTC 30-day trend regime (terciles frozen from discovery; not interpreted under 15 blocks), by
calendar year, and by a thin-coin split.

**Sensitivities (all reported):** same-day funding window; excluding the 11 currently delisted Hyperliquid markets; excluding the four `k`-contract markets; excluding thin
coins.

## 6. Exclusions and reporting

Per product: first and last funding stamp, rows, missing hours, duplicates, days with a valid feature, matched rows. Overall: products with no funding
history, rows lost to warm-up, to the 20-print rule and to the 20-coin day rule. Input hashes (map, per-page SHA-256, baseline manifest). Nothing is
inferred across gaps. Held and benchmark products are listed, not silently dropped.

## 7. What a result would and would not mean

A supportive result would justify forward funding collection and a second look at a longer, point-in-time sample; it is not a score change, a probability,
a trade rule or a validated forecast. The backfilled funding is not a point-in-time record of what was available at the time. The universe is the audited mapping of
currently known Coinbase/Hyperliquid pairs, and the matched subset is selected by having a Hyperliquid perpetual. A null or negative result is a finding.

## 8. Not in scope

Open interest, liquidations, Binance funding, other sources, costs/portfolio sizing, any production change, any claim about probabilities.

## Amendments

(none yet)
