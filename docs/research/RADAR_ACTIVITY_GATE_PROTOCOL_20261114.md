# Radar activity gate at entry: protocol, 2026-11-14

**Status: predeclared before any outcome was computed under either rule below.**
[Step 2](RADAR_RUNNER_CANDLE_SCREEN_RESULTS_20261113.md) found that ranking board
entries by dollar activity flagged about as many runners as percentage change and
about half the crashers. That screen ranked by activity and used whole-day quotas.
This test asks the next question: with the board still ordered by percentage
change, does an activity gate applied at entry remove crashers without removing
runners, at the same alert burden? It is a historical test on dates where no
activity-conditioned outcome has been read. It confirms nothing and changes no
board. **Entries from 2026-11-13 00:00 UTC onward are sealed for confirmation; the
script refuses to load them.**

Two external designs were received on 2026-11-14 and reconciled into this one.
An outcome-blind coverage profile (no labels read) preceded this protocol. It
showed that 27–30% of eligible 3m-gainer entries have no trade in the three
closed minutes before entry, that the median three-minute dollar activity is
$120–$270, and that a $10,000 floor passes 7–12% of entries, too few for a 25%
budget. Those facts set the gates below.

## Data

- **Entries:** the frozen production capture for entry days up to 2026-10-17 and
  the local ledger capture for 2026-10-18 to 2026-11-12, under the frozen
  eligibility rules and the step 1 label rule (`gross_return_30m` finite,
  `outcome_15m` not `interrupted`).
- **Candles:** the one-minute archive (to 2026-10-12 17:59 UTC) and the
  2026-11-13 backfill (from 2026-10-12 18:00 UTC), merged. Only candles with open
  time before the seal are loaded.
- **Test window:** entry days 2026-10-13 to 2026-11-12, 31 UTC days. Outcomes on
  these dates have been read before for percentage-change flags (step 1 check,
  fresh replication, Codex runner screen). No candle signal has been scored on
  them; candles for these dates did not exist locally until the backfill.
- **Reference window:** 2026-09-14 to 2026-10-11, inside the dates step 2
  explored. In-sample for dollar activity. Reported beside the test window,
  never pooled with it, and not part of the decision.
- 2026-09-07 to 09-13 and 2026-10-06 to 10-12 only initialize trailing thresholds.

## Clock and activity

For an entry at `t`, `k = floor(t/60)·60 − 60` is the open time of the last
candle closed before entry, as in step 2. `D3` is the sum of `close·volume` over
the candles with open time `k−120`, `k−60` and `k`. A minute with no candle row
contributes zero. No entry is dropped for missing candles.

A minute is an **unknown gap** when no recorded fetch window for that product
contains it, or the only windows containing it returned no candles. Otherwise a
missing row is a fetched minute without trades. An entry has an unknown gap when
any of its three minutes does. In the primary analysis an unknown gap counts as
zero; the sensitivities below show what that choice does.

## Rules compared

`B0 = abs(start_change_pct)`, the baseline of steps 1 and 2. Every threshold for
UTC day `d` on a board comes from that board's eligible entries on the seven
previous UTC days, `W`. A day is scored only when all seven are present.

- **Baseline rule A0:** flag when `B0 ≥ Q75(B0 in W)`.
- **Gate M (primary):** pass when `D3 > 0` and `D3 ≥ median(D3 in W)`.
- **Gate Z (secondary):** pass when `D3 > 0`, any trade in the three closed minutes.
- **Gated rule A1(G):** flag when the entry passes gate `G` and
  `B0 ≥ Q_{1 − 0.25/p}(B0 among entries in W that pass G)`, where `p` is the share
  of `W` passing `G` under day `d`'s gate threshold. If `p ≤ 0.25` every passing
  entry is flagged. This aims both rules at 25% of entries without using any
  entry from day `d`.

The board's order is never changed. Each rule's realized alert count is
reported per board, in total and per day, because the two will not match exactly.

**Retrospective exact match.** A second comparison takes exactly
`floor(0.25·N_d)` entries per board and day for each rule: the largest `B0`
overall, and the largest `B0` among gate-passing entries. It ranks within the
whole day, so it uses later entries. It is labelled *retrospective (full-day
ranking)* wherever it appears and decides nothing.

## Outcomes and metric

Runner and crasher are the step 1 definitions. For each board and UTC day with
at least 20 eligible entries and at least one flag from each rule: `Y` is the
runner rate of a rule's flags and `C` their crasher rate; `ΔP = Y(A1) − Y(A0)`,
`ΔC = C(A1) − C(A0)`, `ΔN = ΔP − ΔC`. Days with no runner are kept. Days are
weighted equally. Intervals are 95%, from 5,000 resamples of blocks of three
consecutive scored days (a shorter final block is kept), seed 20261116. The
plain daily bootstrap of steps 1 and 2 is reported beside it, with the daily
standard deviations of `ΔP` and `ΔC` for sizing a confirmation.

**Runners missed and reversals avoided** are reported as counts over the window:
runners and crashers among the flags A0 raised and A1 did not, among the flags
A1 raised and A0 did not, and among flags both raised; the net change in each;
and, for the gate as a pure veto with no replacement, the runners and crashers
among A0 flags that fail the gate.

## Coverage report

By board and window, starting from **every recorded board entry**: the count
recorded, the count rejected by each eligibility reason, and the count eligible;
then, for recorded and for eligible entries, how many of the three closed
minutes traded (0, 1, 2, 3), how many entries have an unknown gap, and gate pass
rates. Nothing is left out of this table.

## Sensitivities (descriptive)

1. **Unknown gaps:** counted as zero (primary); those entries removed from both
   rules; those entries treated as passing the gate.
2. **No zero-filling at all:** both rules restricted to entries whose three
   closed minutes all traded, with thresholds from that subset.
3. **Candle delay:** `k` moved one minute earlier.
4. **Step 2's own activity score:** `ln(1 + D3)·(traded minutes in k−840..k)/15`
   in place of `D3` in gate M.

## Decision rule

One primary comparison: gate M against A0 on **3m gainers** in the **test
window**, causal thresholds, unknown gaps as zero. The gate survives to a
prospective confirmation if both hold:

1. mean `ΔP ≥ −0.50` percentage points with the block lower bound `≥ −1.00`;
2. mean `ΔC ≤ −2.50` percentage points with the block upper bound `≤ −1.50`.

Otherwise it does not advance. Gate Z, the other two boards, the reference
window, the retrospective match and the sensitivities are reported under the
same arithmetic but cannot advance anything on their own. If gate M fails and
something else looks better, that is a new hypothesis needing its own
declaration. Nothing here is tuned after outcomes are read.

## Limits known in advance

Outcomes are last-trade checkpoints from the ledger. A candle is assumed usable
the moment it closes; sensitivity 3 delays it. Eligibility needs matured labels,
so both rules are scored on the same label-available entries. The test window's
baseline outcomes are not new; only the paired difference is. The backfill was
fetched after the fact from the public candle endpoint.
