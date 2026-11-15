# Radar microstructure gate and pre-pump coil screen: protocol, 2026-11-15

**Status: exploration, declared before any outcome under these rules was
computed.** The assignment of 2026-11-15 fixed the formulas. This note records
them with every choice the assignment left open, so the run cannot drift after
outcomes are read. It confirms nothing and changes no board, score or collector.

The dates are not fresh. September 7 to October 11 was explored by both step 2
screens, and the Nov 14 activity-gate test reported its dollar gate on September
14 to October 11 as an in-sample reference. Part A's dollar-activity arm is
therefore a replication of a known result. The new questions are the absorption
multiple (Part A) and the coil and grind rules (Part B).

## Data

- **Board entries:** the frozen production capture
  (`live_movers_contract_20261027_production/board_episodes.sqlite`), frozen
  eligibility (`freeze_live_contract.classify`, `CONTRACT_PRODUCTION.json`) plus
  the step 1 label rule (`gross_return_30m` finite, `outcome_15m` not
  `interrupted`). This is the index behind
  `RADAR_RUNNER_CANDLE_SCREEN_RESULTS_20261113.md`. The run refuses unless it
  finds 131,684 entries for September 7 to 30 and 60,659 for October 1 to 11.
- **Candles:** `candle_archive.sqlite`, one-minute bars, read-only.
- **Windows:** screen September 7 to 30, check October 1 to 11, never pooled.
- No entry is dropped for missing candles. A minute with no candle row had no
  trade and contributes zero volume and zero dollars.

## Part A: gates on the board

**Clock.** For an entry at `t`, `m0 = floor((t − 60)/60)·60` is the open time of
the last candle closed before entry, as in the step 2 runner screen. `t` is
`entered_ts`.

**Features.**

- `D3` is the sum of `close·volume` over the bars opening at `m0−120`, `m0−60`
  and `m0`.
- `K3 = D3 / max(|pct_3m|, 0.10)`, with `pct_3m` from the entry snapshot, on
  every board.
- Over the 60 bars opening at `m0−3720 .. m0−180`, for each traded bar
  `K1 = close·volume / max(|close/open − 1|·100, 0.05)`. The one-minute return
  is the bar's own open-to-close move, so it needs no neighbouring bar.
- `A_mult = K3 / median(K1)` when at least 10 of those 60 bars traded, otherwise
  `0`. Rows with `A_mult = 0` fail the absorption gate and stay in the
  denominator.

**Rank.** `B0 = abs(start_change_pct)`, the board's displayed move. This is the
"percentage change" baseline of steps 1 and 2, so arm A0 reproduces their
published rates. The snapshot move (`d·pct_3m` on the 3m boards, `d·pct_1m` on
the 1m board) is a sensitivity.

**Arms.** `gate(x)` means `D3 > 0` and `D3 ≥ x`.

| Arm | Rule |
|---|---|
| A0 | largest `B0` |
| A1 | pass `gate(median D3)`, then largest `B0` |
| A1-30 | pass `gate(30th percentile of D3)`, then largest `B0` (declared sensitivity) |
| A2 | pass `gate(median D3)` and `A_mult ≥ 1.5`, then largest `B0`; unfilled budget goes to the highest `D3·A_mult` among rows that pass the dollar gate only |
| A3 | A0's flags that pass `gate(median D3)`, no replacement |

**Same-day quota (comparable with step 2; uses later entries).** Per board and
UTC day with `N` entries, each arm takes `floor(0.25·N)` rows. Ties break by
larger `B0`, then smaller id. Medians and percentiles come from the same day.
Days need 20 entries and 2 runners, the step 2 rule.

**Causal trailing seven days.** Every threshold for day `d` comes from that
board's entries on days `d−7 .. d−1`, `W`; a day is scored only when all seven
exist. Scored days are September 14 to 30 and October 1 to 11.

- A0: `B0 ≥ Q75(B0 in W)`.
- A1, A1-30: pass the gate at `W`'s threshold and
  `B0 ≥ Q_{1 − 0.25/p}(B0 among W rows that pass)`, `p` the pass share in `W`; if
  `p ≤ 0.25` every passing entry is flagged. This is the Nov 14 rule.
- A2: the same with the strict gate when its share `p2 > 0.25`. Otherwise every
  strict-pass entry is flagged, and the `floor(0.25·|W|) − (strict passes in W)`
  best dollar-gate-only rows of `W`, ordered by `D3·A_mult` then `B0`, set a
  cutoff pair; today's dollar-gate-only rows at or above that pair are flagged.
- A3: A0's causal flags that pass the gate at `W`'s median.
- Days need 20 entries and at least one flag from each compared arm. Days with
  no runner are kept.

Realized flag counts are reported for every arm, in total and per day.

**Outcomes.** Step 1 runner and crasher definitions, unchanged: runner is
`gross_return_15m ≥ 1.00`, `gross_return_5m > −0.50` and
`max(max_favorable_15m, gross_return_30m) ≥ 1.50`; crasher is the mirror.

**Metric.** Equal-weighted daily means of each arm's flagged-row runner rate and
crasher rate, net balance, `ΔP` and `ΔC` against A0, and A2 against A1. 95%
intervals from 5,000 resamples, seed 20261117: plain daily, and blocks of three
consecutive scored days. A3 reports crashers avoided and runner recall as counts
and shares of A0's.

**Sensitivities, descriptive:** the snapshot move as rank; `m0` one minute
earlier (the other step 2 screen's clock).

**Reading rule, 3m gainers, causal thresholds.** An arm *holds* against A0 when,
in the screen window, mean `ΔP ≥ −0.50` points with block lower bound `≥ −1.00`
and mean `ΔC ≤ −2.50` points with block upper bound `≤ −1.50`, and in the check
window `ΔP ≥ −0.50` and `ΔC < 0`. Absorption *adds to the dollar gate* when A2
against A1 has screen mean `ΔC < 0` with block upper bound below zero and
`ΔP ≥ −0.50`, and the check window has the same signs. Holding on these dates
advances nothing by itself; it decides what a fresh test should carry.

## Part B: early watch before the board

**Grid.** Every fifth minute from September 7 00:00 to October 11 23:55 UTC,
10,080 cutoffs. At cutoff `T` the last usable bar opens at `m0 = T − 120s`: it
closed 60 seconds before the decision. This is the clock of the Nov 13 early
watch replay in `RADAR_CANDLE_SCREEN_20261113.md`, whose ranking and grading
functions are imported unchanged.

**Universe, all arms.** Archived USD products excluding stablecoins; a trade in
bar `m0`; at least 30 traded minutes in the 24 hours and 5 in the hour ending at
`m0`; not in the synthetic top eight by 1m or 3m gain at `m0`.

**Arms.** One flag per cutoff, the top-ranked candidate not flagged by that arm
in the previous 60 minutes.

- **Baseline:** `r_3m ≥ +0.30%` with trades at `m0−1` and `m0−3`; rank by `r_3m`.
- **B1 coil:** `H_4h, L_4h` are the bar high and low over `m0−243 .. m0−3`,
  `H_24h, L_24h` over `m0−1443 .. m0−3`, both inclusive as written (241 and
  1,441 bars). `C_ratio = ln(H_4h/L_4h) / (sqrt(4/24)·ln(H_24h/L_24h))`.
  `V_pace = D_15m(m0−14 .. m0) / (D_4h(m0−254 .. m0−15)/16)`. Breakout is
  `close(m0) > H_4h`, or `close(m0) ≥ 0.9985·H_4h` with `r_3m ≥ +0.30%`.
  Require `C_ratio ≤ 0.75`, `V_pace ≥ 2.0` and breakout; rank by
  `V_pace / max(C_ratio, 0.05)`. A candidate with no trade in the 4h window, a
  zero 24h range or zero `D_4h` has an undefined feature and does not qualify.
- **B2 grind:** `r_15m = close(m0)/close(m0−15) − 1` in `[+0.20%, +1.20%]` with a
  trade at `m0−15`; `V_pace ≥ 2.5`;
  `(close(m0) − L_15m)/(H_15m − L_15m) ≥ 0.75` over bars `m0−14 .. m0`,
  undefined when `H_15m = L_15m`; rank by `V_pace`.

**Matched cutoffs.** For each of B1 and B2, the paired comparison is run only on
cutoffs where both that arm and the baseline have at least one qualifying
candidate before cooldown, each arm with its own cooldown. Each arm's replay
over all cutoffs is reported beside it.

**Grades.**

1. *Sustained runner / reversal*, the Nov 13 early-watch rule: measured from
   `close(m0)`, `+1%` at +15m, above `−0.5%` at +5m, and `+1.5%` within 15m or
   synthetic top-eight graduation within 10m; reversal is the mirror. A flag is
   graded only when all 15 forward minutes traded.
2. *Live board graduation:* the product starts a recorded episode on the live 1m
   gainers or 3m gainers board with `entered_ts` in `(T, T + 900]`. Lead is
   `entered_ts − T` in seconds for the first such entry. Every recorded episode
   counts, eligible or not. A flag is *live-observable* unless its window
   overlaps a gap of more than 600 seconds with no recorded entry on any board,
   which is treated as collector downtime. Flags for products already on either
   live board at `T` are counted separately.

**Metric.** Pooled rates per arm and window; differences against the baseline
with 95% intervals from 5,000 resamples of three-day blocks, seed 20261117.

**Reading rule, matched cutoffs.** An arm *beats the baseline* on a grade when
its screen-window rate is at least 1.00 point higher with the block lower bound
above zero and the check-window difference is positive; for the sustained grade
the runner-minus-reversal difference must also be positive in the screen window.

## Limits known in advance

In-sample dates; last-trade outcomes; whole-day ranking in the same-day mode;
a candle is assumed usable when it closes (Part A) or 60 seconds later (Part B);
the early watch is a minute-candle replay and cannot measure delivery time;
`A_mult` compares three minutes of dollars per 3m move with one minute of dollars
per 1m move, so `1.5` is a threshold on that ratio and not literally "1.5 times
normal".
