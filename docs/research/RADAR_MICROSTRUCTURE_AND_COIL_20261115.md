# Radar microstructure gate and pre-pump coil screen: results, 2026-11-15

**Neither new mechanism earned a place in the fresh confirmation.** Under the
[protocol](RADAR_MICROSTRUCTURE_AND_COIL_PROTOCOL_20261115.md) declared before
scoring:

- **The dollar-activity gate replicates.** With causal seven-day thresholds on
  3m gainers it raised the runner rate and cut the crasher rate in both
  windows. Its screen-window crasher cut (−1.89 points) is below the −2.50 bar
  carried over from the Nov 14 test, so it does not meet that rule on these
  dates.
- **The absorption multiple does not preserve runners.** Adding it roughly
  halves the crasher rate but removes 1.1 to 1.5 points of runner rate that the
  dollar gate alone keeps, and in the check window its flags run less often than
  plain percentage change. It gets there by flagging small moves on heavily
  traded coins.
- **The coil and the grind do not beat the `+0.30%` baseline.** On live-board
  graduation no early-watch rule, the baseline included, does better than an
  arbitrary active coin.

Exploration on dates already explored (September 7 to October 11). Nothing is
confirmed and no board, score or collector changed.

## Checks against published numbers

The run reproduces the earlier screens exactly before adding anything new:
131,684 and 60,659 eligible entries; step 2's percentage-change rates on all
three boards (3m gainers 4.98% runners, 9.53% crashers in the screen window and
3.77% / 8.48% in the check window); and the Nov 14 gate reference on 3m
gainers, September 14 to October 11 (runners +1.19, crashers −2.16).

## Part A: gates on the board, 3m gainers, causal thresholds

Every threshold for a day comes from the seven previous UTC days. Rates are
equal-weighted daily means of the flagged rows, in percent. `ΔP` and `ΔC` are
differences from A0 in points with three-day block 95% intervals.

**Screen, September 14 to 30 (17 days, 29,894 entries)**

| Arm | Flags | Runners | Crashers | Net | ΔP | ΔC |
|---|---:|---:|---:|---:|---|---|
| A0 percentage change | 8,514 | 5.04 | 9.93 | −4.89 | | |
| A1 dollar gate | 8,421 | 6.56 | 8.04 | −1.48 | +1.52 [+1.22, +1.75] | −1.89 [−2.19, −1.64] |
| A1-30 wider gate | 8,574 | 6.22 | 8.74 | −2.52 | +1.19 [+0.92, +1.55] | −1.18 [−1.46, −0.88] |
| A2 dollar + absorption | 7,724 | 5.49 | 5.74 | −0.24 | +0.46 [+0.12, +0.77] | −4.19 [−5.82, −2.96] |

**Check, October 1 to 11 (11 days, 19,161 entries)**

| Arm | Flags | Runners | Crashers | Net | ΔP | ΔC |
|---|---:|---:|---:|---:|---|---|
| A0 percentage change | 4,190 | 3.87 | 9.47 | −5.60 | | |
| A1 dollar gate | 4,105 | 4.54 | 6.90 | −2.35 | +0.68 [+0.39, +0.95] | −2.57 [−3.16, −1.86] |
| A1-30 wider gate | 4,053 | 4.38 | 8.24 | −3.87 | +0.51 [+0.09, +0.79] | −1.22 [−1.52, −1.03] |
| A2 dollar + absorption | 4,624 | 3.03 | 3.86 | −0.83 | −0.83 [−1.00, −0.67] | −5.60 [−6.85, −4.35] |

Causal thresholds do not hit the 25% budget exactly: A2 raised 9% fewer flags
than A0 in the screen window and 10% more in the check window. The same-day
quota below forces identical counts and tells the same story.

**Reading against the declared rule.**

- **A1 does not hold.** Five of six checks pass. The screen crasher cut of
  −1.89 misses the −2.50 mean. Runners improved in both windows and the check
  crasher cut is −2.57.
- **A1-30 does not hold.** About half of A1's crasher cut in both windows.
- **A2 does not hold.** It meets every screen check, then loses 0.83 points of
  runner rate in the check window against a limit of −0.50.
- **Absorption does not add to the dollar gate.** A2 against A1: crashers
  −2.30 [−3.59, −1.19] and −3.03 [−4.03, −2.21], runners −1.06 [−1.49, −0.68]
  and −1.51 [−1.66, −1.28]. It trades about two crashers for each runner.

No arm's flags run more often than they crash. A2 comes closest: 430 runners
against 441 crashers in the screen window, 141 against 182 in the check window.

### A3: the dollar gate as a veto, no replacement

| Window | A0 flags dropped | Crashers avoided | Runners missed | Runner recall |
|---|---:|---:|---:|---:|
| Screen | 4,935 of 8,514 | 385 of 830 (46%) | 125 of 429 (29%) | 71% |
| Check | 2,571 of 4,190 | 181 of 397 (46%) | 52 of 167 (31%) | 69% |

The veto removes 3.1 to 3.5 crashers per runner missed, but it also removes
about 60% of the alerts. The flags it keeps are the most volatile group (8.5%
runners, 12.6% crashers in the screen window), so the surviving flags crash
*more* often than A0's. The gain in A1 comes from the replacements, as the
Nov 14 test found.

### Same-day quota, 3m gainers (identical flag counts, uses later entries)

| Window | Flags per arm | A0 | A1 | A2 | A1 ΔP / ΔC | A2 ΔP / ΔC |
|---|---:|---|---|---|---|---|
| Screen, Sep 7–30 | 10,474 | 4.98 / 9.53 | 6.38 / 7.60 | 5.11 / 5.40 | +1.39 / −1.93 | +0.13 / −4.13 |
| Check, Oct 1–11 | 4,786 | 3.77 / 8.48 | 4.25 / 6.16 | 3.15 / 3.86 | +0.48 / −2.32 | −0.63 / −4.62 |

Cells are runner / crasher rates. Every A1 and A2 crasher interval excludes
zero. A2's runner interval spans zero in the screen window [−0.57, +0.82] and is
below zero in the check window [−0.97, −0.34].

### Other boards, causal thresholds

| Board | Window | A1 ΔP | A1 ΔC | A2 ΔP | A2 ΔC |
|---|---|---|---|---|---|
| 1m gainers | Screen | +1.00 [+0.74, +1.25] | −1.41 [−2.20, −0.81] | −0.01 [−0.43, +0.44] | −3.59 [−5.09, −2.34] |
| 1m gainers | Check | +0.46 [+0.29, +0.66] | −2.03 [−2.64, −1.36] | −0.95 [−1.32, −0.70] | −4.71 [−5.07, −4.30] |
| 3m losers | Screen | +0.66 [+0.24, +1.25] | −1.01 [−1.68, −0.50] | −0.45 [−1.00, +0.24] | −2.49 [−3.67, −1.25] |
| 3m losers | Check | +0.47 [−0.40, +1.20] | −2.66 [−3.81, −1.44] | −1.30 [−2.29, −0.30] | −5.72 [−8.17, −3.57] |

Same pattern on every board: the dollar gate adds runners and removes crashers;
absorption removes more crashers and gives the runners back.

### What the gates select (added after the results were read; uses no outcome)

Median displayed move and median three-minute dollars of each arm's causal
flags on 3m gainers, screen window:

| Flags | Median move | Median 3m dollars |
|---|---:|---:|
| All entries | 0.41% | $294 |
| A0 | 0.86% | $98 |
| A0 flags the gate drops | 0.89% | $0 |
| A1 | 0.55% | $2,512 |
| A2 | 0.34% | $11,402 |

More than half the flags the gate removes had no trade at all in the three
closed minutes. A2's typical flag is a smaller move than the typical board
entry, on a coin trading about forty times the board median. `A_mult` divides
by the size of the move, so requiring a high value selects small moves by
construction. Its lower crasher rate and lower runner rate are what a
lower-volatility selection would produce, and this screen cannot separate
"absorbed" from "small".

### Other declared cells

- 27% of 3m-gainer entries had no closed-minute trade; 58 to 60% had the ten
  traded baseline minutes `A_mult` needs; 21% reach `A_mult ≥ 1.5`. The strict
  gate passes about 20% of entries, under the 25% budget, so 22% of A2's screen
  flags and 14% of its check flags are backfills.
- Moving the candle clock one minute earlier leaves the picture unchanged (A1
  +1.60 / −1.89 and +0.59 / −2.81; A2 +0.66 / −3.90 and −0.56 / −5.45).
- Ranking by the snapshot move instead of the displayed move gives identical
  flags; the two rank the entries the same way.

## Part B: early watch before the board

10,080 five-minute cutoffs, 405 products, one flag per cutoff per arm.

| Arm | Flags | Graded | Runners (of graded) | Reversals | Live graduation | Median live lead |
|---|---:|---:|---:|---:|---:|---:|
| Baseline, `+0.30%` 3m move | 3,790 | 1,633 (43%) | 13.90% | 10.84% | 10.77% | 487 s |
| B1 coil + volume breakout | 1,850 | 177 (10%) | 17.51% | 3.95% | 6.38% | 404 s |
| B2 absorption grind | 3,569 | 861 (24%) | 8.83% | 6.50% | 10.48% | 412 s |

**Matched cutoffs, arm minus baseline, points with three-day block intervals**

| Arm | Window | Runners | Reversals | Live graduation |
|---|---|---|---|---|
| B1 (1,062 cutoffs) | Screen | +6.95 [−1.92, +16.61] | −7.28 [−11.47, −4.04] | −6.30 [−7.79, −4.34] |
| B1 | Check | +4.02 [−8.59, +22.60] | −2.75 [−9.59, +5.54] | +1.80 [−0.27, +3.40] |
| B2 (2,095 cutoffs) | Screen | −3.99 [−8.12, −0.69] | −4.44 [−6.57, −1.54] | −1.49 [−3.99, +0.45] |
| B2 | Check | −5.60 [−15.81, +1.66] | −7.54 [−12.08, +0.34] | +0.69 [−2.33, +5.12] |

**Neither arm beats the baseline on either grade under the declared rule.**

- **B1's sustained-runner rate rests on 177 graded flags out of 1,850.** A flag
  is graded only when the coin trades in every one of the next 15 minutes, which
  depends on what happened after the flag. B1 flags quiet coins, so 90% of its
  flags are ungraded and the rest are a selected group. Its runner difference
  spans zero in both windows. Counting per flag issued, 31 of B1's 1,850 flags
  were graded sustained runners (1.7%) against 227 of the baseline's 3,790
  (6.0%). The true rates lie between the two counts.
- **B1's flags reach the live board less often**: 5.3% against 11.7% in the
  screen window, 8.5% against 8.6% in the check window (all cutoffs).
- **B2 finds fewer runners and fewer reversals** than the baseline and the same
  share of live graduations.
- **Live lead.** Among flags that graduated, the median time to the live board
  was about 8 minutes for the baseline and about 7 for B1 and B2. No collector
  gap over 600 seconds fell in the window, so every flag was live-observable.
  About 4% of baseline flags were already on a live gainers board when raised.

### Base rate for live graduation (added after the results were read)

The declared grade has no reference point, so one was added: every product in
the early-watch universe at every cutoff, flagged or not.

| Group | Product-cutoffs | Enter a live gainers board within 15 minutes |
|---|---:|---:|
| Any universe product | 942,559 | 12.23% |
| Any baseline candidate | 30,241 | 13.25% |
| Baseline's top pick | 3,790 | 10.77% |
| B2's top pick | 3,569 | 10.48% |
| B1's top pick | 1,850 | 6.38% |

An active coin outside the synthetic top eight reaches a live gainers board in
the next 15 minutes about one time in eight whatever the rule says. The
baseline's pick does slightly worse than that, and its median lead of 8 minutes
is what entries spread evenly over 15 minutes would give. On this grade the
early watch shows no foresight yet, for the new rules or the old one.

## What to carry forward

- **Fresh confirmation:** carry the dollar gate (A1, median threshold) as the
  Nov 14 test already proposed. This screen adds a second in-sample replication
  and no reason to change it. Do not add the 30% threshold; it gives about half
  the effect.
- **Absorption:** do not add `A_mult ≥ 1.5` as a gate. If it is tested again it
  needs a comparison matched on move size, so that it is not credited for
  picking smaller moves.
- **Early watch:** do not carry B1 or B2. Before any further early-watch rule,
  the grade needs fixing: compare against the universe base rate, and replace
  the every-minute-traded requirement with a grade that does not depend on
  later activity.

## Limits

- Dates already explored by both step 2 screens and the Nov 14 reference
  window; the dollar-gate rows are a replication, not new evidence.
- The reading rule's −2.50 crasher bar came from the Nov 14 test and was set for
  a different window. A1 misses it here on one of six checks.
- Last-trade outcomes from the ledger; a candle is assumed usable when it
  closes (Part A) or 60 seconds later (Part B).
- `A_mult` compares three minutes of dollars per 3m move with one minute of
  dollars per 1m move, so `1.5` is not literally "1.5 times normal".
- Part B is a minute-candle replay. Lead times are measured from the cutoff and
  cannot show when a live alert would have been delivered.
- The two post hoc tables were added after the declared results were read. They
  describe inputs and a base rate and tune nothing; the rerun left every
  declared number unchanged.

## Provenance

Protocol, script and 26 synthetic checks at `67d7629`, committed before any
outcome was computed. Declared results at `5315de1`, unmodified output of that
script. The following commit adds the two post hoc tables and two more checks;
every other field of
[RESULTS.json](results/radar_microstructure_coil_20261115/RESULTS.json) is
identical to `5315de1` except the script hash. Seed 20261117, 5,000 resamples.
Frozen capture, contract and eligibility hashes verified by the script; the
candle archive hash is recorded in the results.

```powershell
~\.moonwalking\venv\Scripts\python.exe scripts/scoring_experiment/screen_microstructure_and_coil_20261115.py
~\.moonwalking\venv\Scripts\python.exe -m pytest -q tests/test_screen_microstructure_and_coil_20261115.py
```
