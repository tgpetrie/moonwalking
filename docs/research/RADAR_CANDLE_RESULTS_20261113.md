# Radar candle results · November 13

The [exploratory protocol](RADAR_CANDLE_SCREEN_20261113.md) was committed
with its driver at `4aa233e` before scoring. The screen used complete UTC
days September 7–October 11, a fixed 60s candle publication lag, and the
existing Coinbase archive. The replay loaded 5,737,981 traded minute bars
from 405 archived USD products in its bounded input span including
warmup and maturation. No fresh confirmation outcomes were read.

## Step 2 · board continuation

All nine board/candidate combinations lost runner precision to raw
percentage move on the same entries in both windows. The table reports
the matched runner precision difference in percentage points for
September 7–27 / September 28–October 11. These are standalone comparisons.

| Board | Volatility-adjusted move | Estimated dollar activity | BTC-relative move |
| --- | ---: | ---: | ---: |
| 1m gainers | −4.74 / −2.26 | −5.59 / −3.80 | −3.78 / −2.80 |
| 3m gainers | −4.83 / −3.61 | −4.90 / −4.24 | −2.41 / −1.31 |
| 3m losers | −7.30 / −5.49 | −6.16 / −6.07 | −4.10 / −3.67 |

All nine descriptive 35-day block intervals had upper bounds below zero.
On 3m gainers, 5,667 / 61,090 entries had the strict volatility baseline,
14,140 had the three activity candles, and 16,641 had both coin and BTC
endpoints. The corresponding product-day counts were 851, 2,113, and
2,416 out of 4,148. The production episode index already conditions on
5m/15m checkpoint observability. Every input-matched row in this window
also had the three sustained-label checkpoints and both extrema.

The matched raw-move baseline was stronger than its full-roster read. For
example, on the initial 3m-up BTC-relative subset, raw move found 9.15%
runners versus 5.16% on the full cohort. BTC-relative flags found 6.74%
runners and 7.83% reversals on that subset. The result demonstrates why
the unmatched comparison would be misleading. No candidate passed the
declared gate. Leave the board's percentage-change order and directional
labels as they stand.

## Early watch · minute-candle replay

| Input-matched comparison | Flags graded / issued | Sustained runner | Sustained reversal | Successful synthetic graduates |
| --- | ---: | ---: | ---: | ---: |
| Raw 3m move, volume-pace cohort | 2,072 / 2,250 | 10.86% | 10.47% | 215 |
| Volume pace | 2,117 / 2,272 | 9.45% | 8.03% | 192 |
| Raw 3m move, volatility cohort | 2,063 / 2,236 | 10.71% | 10.28% | 212 |
| Volatility-adjusted move | 2,113 / 2,270 | 7.67% | 6.81% | 152 |

Each arm could issue at most one flag per 5m cutoff, with its own product
cooldown. The two input-matched cohorts supplied candidates at 2,468
and 2,459 of 10,080 cutoffs. Cooldowns caused modest differences in realized
flag count. Median lead among successful synthetic graduates was 2 minutes
in every arm. The unscored flags, overlapping waves, simulated universe,
and assumed data availability limit the inference. Lower reversal rates
came with fewer runners. The raw-move arms had nearly equal runner and
reversal rates. Before a product decision, a separate predeclared replay
could compare the raw outside-top-eight rule with simple matched controls,
tie down the actual desired flag budget, and test the lead distribution
against timestamped live board entries. This first replay supplies no
confirmation or delivery measurement.

## Checks

The frozen board capture and eligibility hashes verified. Synthetic
probes covered the closed-bar availability boundary, a missing volatility
bar, a missing outcome bar, and synthetic graduation timing.

```powershell
python scripts/scoring_experiment/screen_radar_candles_20261113.py board
python scripts/scoring_experiment/screen_radar_candles_20261113.py early
```
