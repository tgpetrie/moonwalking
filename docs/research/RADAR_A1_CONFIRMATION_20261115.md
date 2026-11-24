# Radar A1 dollar gate on the backfilled window: results, 2026-11-15

**The dollar gate holds on October 13 to November 12, and holds in both halves.**
On 3m gainers it cut the crasher rate of the flags by 2.89 points and left the
runner rate unchanged (+0.30), at nearly the same number of alerts. The flags
still crash more often than they run.

**This is not a new out-of-sample result.** The same rule was declared and scored
on these same dates by the
[Nov 14 activity-gate test](RADAR_ACTIVITY_GATE_RESULTS_20261114.md) (on branch
`claude/instant-radar-fresh-replication-20261113`). This run re-implements it
from the frozen A0 and A1 definitions in
`screen_microstructure_and_coil_20261115.py` and reproduces it exactly: 51,997
entries, 12,773 and 12,465 flags, runners +0.30, crashers −2.89. What is new
here is the independent reproduction and the half split. No board changes.

## 3m gainers (primary), causal seven-day thresholds

Rates are equal-weighted daily means of the flagged rows, in percent.
Differences are A1 minus A0 in points with three-day block 95% intervals
(5,000 resamples, seed 20261117).

| Window | Entries | Flags A0 / A1 | A0 runners / crashers | A1 runners / crashers | Runner difference | Crasher difference |
|---|---:|---:|---|---|---|---|
| All, Oct 13 – Nov 12 (31 days) | 51,997 | 12,773 / 12,465 | 4.98 / 10.54 | 5.28 / 7.64 | +0.30 [−0.21, +0.75] | −2.89 [−4.02, −1.97] |
| First half, Oct 13 – 27 (15 days) | 25,812 | 6,446 / 6,061 | 5.81 / 9.52 | 6.05 / 7.80 | +0.24 [−0.26, +0.79] | −1.71 [−2.47, −1.11] |
| Second half, Oct 28 – Nov 12 (16 days) | 26,185 | 6,327 / 6,404 | 4.20 / 11.50 | 4.55 / 7.50 | +0.35 [−0.53, +1.09] | −4.00 [−5.64, −3.00] |

- **Rule met.** The Nov 14 rule asks for a runner difference of at least −0.50
  with lower bound at least −1.00, and a crasher difference of at most −2.50
  with upper bound at most −1.50. All four checks pass on the full window.
- **Stable in direction, not in size.** Both halves keep the runner rate and cut
  crashers, and the crasher rate fell on 30 of 31 days. The cut is −1.71 in the
  first half and −4.00 in the second. Taken alone the first half would miss the
  −2.50 bar, as the September screen window did (−1.89).
- **Counts over 31 days.** Runners 653 → 661, crashers 1,301 → 942, a net 359
  fewer crashers (−28%) from 308 fewer alerts.
- **Net balance** moves from −5.56 to −2.37 (+3.19 [+2.14, +4.62]). It stays
  negative in every window.

The Nov 14 report noted that one short day, 2026-11-02 (221 entries), carries
weight in the equal-weighted mean and that the crasher difference is −2.57
without it. That day is in the second half.

## Secondary boards, full window

| Board | Entries | Flags A0 / A1 | A0 runners / crashers | A1 runners / crashers | Runner difference | Crasher difference | Rule |
|---|---:|---:|---|---|---|---|---|
| 1m gainers | 59,776 | 14,800 / 14,303 | 4.22 / 9.03 | 4.79 / 6.71 | +0.57 [+0.06, +1.04] | −2.32 [−2.98, −1.77] | crasher mean short of −2.50 |
| 3m losers | 52,056 | 12,848 / 12,487 | 4.99 / 10.21 | 5.35 / 6.76 | +0.37 [−0.16, +0.81] | −3.45 [−4.54, −2.50] | met |

Both secondary boards keep the sign in each half: 1m gainers +0.46 / −1.82 then
+0.67 / −2.78; 3m losers +0.53 / −2.48 then +0.21 / −4.36. The crasher cut is
larger in the second half on all three boards.

## The crasher cut across every window scored so far, 3m gainers

| Window | Runner difference | Crasher difference | Status |
|---|---:|---:|---|
| Sep 14 – 30 | +1.52 | −1.89 | in-sample (step 2 explored these dates) |
| Oct 1 – 11 | +0.68 | −2.57 | in-sample |
| Oct 13 – 27 | +0.24 | −1.71 | declared before scoring on Nov 14 |
| Oct 28 – Nov 12 | +0.35 | −4.00 | declared before scoring on Nov 14 |

The direction has not failed in any window. The size ranges from −1.7 to −4.0
points, so a prospective test sized for −2.9 could meet a smaller effect.

## What this does and does not establish

- The gate's effect on these dates is real in the sense that two independent
  implementations give identical numbers from the frozen inputs.
- It is not prospective. Outcomes on these dates had been read before the gate
  was first scored, and have now been scored under this rule twice.
- Entries from 2026-11-13 00:00 UTC remain sealed and unread. The backfill has
  candles to 14:59 UTC that day, but the ledger capture used here ends on
  November 12, so a prospective confirmation still needs a new capture of board
  entries after the seal.
- Outcomes are last-trade checkpoints from the ledger. A candle is assumed
  usable when it closes; the Nov 14 one-minute-delay check held.

## Data and provenance

- Entries: frozen production capture to October 17, local ledger capture from
  October 18, step 1 eligibility. The script verifies the frozen capture,
  contract and eligibility hashes, the local capture hash and the backfill
  hash against its manifest, and refuses anything at or after the seal.
- Candles: the archive and the 2026-11-13 backfill, merged at the seam. The
  backfill fetched 497 products with every window `ok`; 407 of them have at
  least one candle. 4,726,150 one-minute candles in total, of which 4,630,592
  fall before the seal.
- Driver and five synthetic checks at `1fc67c5`, committed before the run. All
  numbers, daily intervals and counts are in
  [RESULTS.json](results/radar_a1_confirmation_20261115/RESULTS.json).

```powershell
~\.moonwalking\venv\Scripts\python.exe scripts/scoring_experiment/confirm_a1_gate_20261115.py
```
