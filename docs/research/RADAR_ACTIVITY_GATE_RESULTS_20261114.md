# Radar activity gate at entry: results, 2026-11-14

**The gate met its [predeclared rule](RADAR_ACTIVITY_GATE_PROTOCOL_20261114.md)
on 3m gainers.** Across 31 UTC days (2026-10-13 to 2026-11-12), requiring recent
dollar activity before flagging the largest percentage moves cut the crasher
rate of the flags by 2.89 percentage points and left the runner rate unchanged,
at nearly the same number of alerts. The flags still crash more often than they
run. This is a historical test on dates where no candle signal had been scored.
It is a candidate for prospective confirmation, not a confirmation, and no board
changes. Nothing from 2026-11-13 onward was loaded; the last entry read is
2026-11-12 23:59:58 UTC.

## Primary comparison: 3m gainers, test window, entry-time thresholds

Both rules use only the seven previous UTC days to set their thresholds.
Baseline: flag when the percentage move is in the trailing top quarter. Gated:
flag when three-minute dollar activity is above zero and at or above its
trailing median (about $121; daily range $76–$289), and the percentage move is
high enough among such entries to aim at the same quarter.

| | Baseline | Gated | Difference, 3-day block 95% interval | Rule |
|---|---:|---:|---|---|
| Runner rate of flags | 4.98% | 5.28% | +0.30 [−0.20, +0.76] | mean ≥ −0.50, lower ≥ −1.00: met |
| Crasher rate of flags | 10.54% | 7.64% | −2.89 [−4.08, −2.00] | mean ≤ −2.50, upper ≤ −1.50: met |
| Runner minus crasher | −5.56 | −2.36 | +3.19 [+2.15, +4.64] | reported |

Rates are equal-weighted daily means. The crasher rate fell on 30 of 31 days.

## Actual alert counts

| Rule | Alerts, 31 days | Share of 51,997 entries | Per day: mean (min–max) |
|---|---:|---:|---:|
| Baseline, entry-time | 12,773 | 24.56% | 412 (49–705) |
| Gated (median), entry-time | 12,465 | 23.97% | 402 (39–666) |
| Gated (any trade), entry-time | 12,526 | 24.09% | 404 (43–689) |

The entry-time rules match in total within 2.4% but not day by day: the median
daily gap is 11% and the largest 27%. Each day's alert count is in
[RESULTS.json](results/radar_activity_gate_20261114/RESULTS.json).

**Retrospective (full-day ranking).** Forcing an exact match, 12,989 alerts for
each rule by ranking within the whole UTC day, gives runners +0.12 [−0.26,
+0.51] and crashers −2.99 [−4.22, −2.09]. This ranking uses later entries and
could not run live. It shows the entry-time result does not come from the
gated rule raising fewer alerts.

## Runners missed and reversals avoided

Counts over the 31 days on 3m gainers.

| Flags | Alerts | Runners | Crashers |
|---|---:|---:|---:|
| Baseline, all | 12,773 | 653 | 1,301 |
| Gated, all | 12,465 | 661 | 942 |
| Raised by both | 4,967 | 401 | 651 |
| Baseline only (removed by the gate) | 7,806 | 252 | 650 |
| Gated only (added in their place) | 7,498 | 260 | 291 |

- **Net:** 359 fewer crashers (−28%) and 8 more runners.
- **The gate replaces 61% of the baseline's flags.** It removes 252 runners
  and adds back 260 from other entries. The runner rate is held by replacement,
  not because the removed flags had no runners.
- **As a veto with no replacement** it would drop 7,806 alerts, miss 252 of 653
  runners (39%) and avoid 650 crashers, 2.6 avoided per runner missed. The
  baseline's own ratio is 2.0 crashers per runner, so a veto alone is a weak trade.
- **Where the gain comes from.** Removed flags: 3.2% runners, 8.3% crashers.
  Added flags: 3.5% runners, 3.9% crashers. The flags both rules raise are the
  most volatile group, 8.1% runners and 13.1% crashers. The gate does not
  remove the flags most likely to crash; it swaps large moves on untraded coins
  for smaller moves on traded ones.

## Coverage: every recorded board entry, test window

| | 3m gainers | 1m gainers | 3m losers |
|---|---:|---:|---:|
| Recorded entries | 54,169 | 61,834 | 54,315 |
| Not eligible: required features missing | 908 | 855 | 1,063 |
| Not eligible: frozen-contract label unavailable | 543 | 585 | 543 |
| Not eligible: 30m label unavailable or interrupted | 525 | 574 | 469 |
| Not eligible: snapshot missing | 154 | 6 | 147 |
| Not eligible: inside the 30-minute end purge | 42 | 38 | 37 |
| **Eligible** | **51,997** | **59,776** | **52,056** |
| Recorded, traded minutes of the last three: 0 / 1 / 2 / 3 | 16,710 / 18,861 / 8,242 / 10,356 | 18,764 / 19,231 / 9,843 / 13,996 | 16,877 / 18,681 / 8,257 / 10,500 |
| Eligible, traded minutes of the last three: 0 / 1 / 2 / 3 | 15,830 / 18,132 / 8,033 / 10,002 | 17,879 / 18,571 / 9,604 / 13,722 | 16,005 / 17,917 / 8,003 / 10,131 |
| Recorded entries with an unknown candle gap | 2 | 2 | 5 |
| Eligible entries passing the median gate / any-trade gate | 49.3% / 69.6% | 49.3% / 70.1% | 49.2% / 69.3% |

No entry was dropped for missing candles. 30% of entries had no trade in the
three closed minutes before entry and 19% had a trade in all three.

## What counting missing candles as zero does

- **Unknown gaps do not matter here.** An unknown gap is a minute no recorded
  fetch covered. In the test window that is 2 of 51,997 eligible 3m-gainer
  entries. Counting them as zero, removing them, or letting them pass the gate
  gives the same result to two decimals. In the reference window 2.3% of
  entries have one; there the crasher difference is −2.16 as zero, −2.13
  removed and −1.90 when they pass.
- **Fetched minutes without trades are the whole effect.** Restricting both
  rules to the 19% of entries with a trade in all three minutes, so nothing is
  zero-filled, reverses the runner result: runners 9.73% → 6.74% (−3.00 [−4.07,
  −1.93]) with crashers 14.39% → 8.18%. Among coins that are already trading,
  asking for more dollars removes runners. The gate works by separating traded
  from untraded coins, at a threshold near $120 over three minutes, and should
  not be read as "more activity is better".

## Other declared comparisons (cannot advance anything)

Test window, entry-time thresholds, differences in percentage points.

| Comparison | Runners | Crashers |
|---|---|---|
| 3m gainers, any-trade gate | +0.14 [−0.19, +0.47] | −1.45 [−2.12, −0.88] |
| 3m gainers, candle delayed one more minute | +0.19 [−0.30, +0.64] | −3.03 [−4.28, −2.02] |
| 3m gainers, step 2's activity score | +0.36 [−0.12, +0.80] | −2.84 [−3.81, −2.02] |
| 1m gainers, median gate | +0.57 [+0.07, +1.03] | −2.32 [−3.00, −1.76] |
| 3m losers, median gate | +0.37 [−0.17, +0.82] | −3.45 [−4.56, −2.49] |
| Reference window (in-sample), 3m gainers, median gate | +1.19 [+0.73, +1.58] | −2.16 [−2.72, −1.66] |

The any-trade gate gives about half the crasher reduction and would not meet
the rule. 1m gainers falls short of the −2.50 mean. The in-sample reference
window shows the same net change (+3.34 against +3.19) split differently: more
runner gain, less crasher reduction.

## Limits

- **Still more crashers than runners.** Gated flags run 5.28% of the time and
  crash 7.64%. The gate improves an alert; it does not make one favorable.
- **One short day carries weight.** 2026-11-02 has 221 entries against a usual
  1,700 and its crasher rate fell from 20.4% to 7.7% on 49 and 39 alerts. Days
  are weighted equally, as declared. Without that day the mean crasher
  difference is −2.57 and the runner difference +0.29. This was computed after
  the result and its interval was not recomputed. Pooled over all alerts the
  crasher rate is 10.19% against 7.56%.
- **Not prospective.** Outcomes on these dates had been read before for
  percentage-change flags. Only the paired difference is new. Candles were
  fetched after the fact and assumed usable when they close; the one-minute
  delay check holds.
- **Last-trade outcomes**, with the stored 15-minute extremes' known overshoot.
- **The gate changes which coins are flagged**, toward smaller moves on traded
  coins. Whether that is the alert a user wants is a product question this test
  does not answer.

## For sizing a confirmation

Daily standard deviations of the paired differences on 3m gainers in the test
window: runners 1.32 points, crashers 2.43 points. The crasher bound is the
binding one. Entries from 2026-11-13 onward remain unread and need a further
candle fetch before they can be scored.

## Provenance

Protocol `91ec1d4`, script and nine synthetic checks `a4cc38b`, both committed
before the run. Frozen production capture, local capture and backfill hashes
verified by the script. All numbers, the reference window, the other boards and
per-day records are in
[RESULTS.json](results/radar_activity_gate_20261114/RESULTS.json).
