# Elliott ABC chart engine: walk-forward evaluation results, 2026-11-15

**The primary cell (`1h/bullish/complete`) is underpowered (`n = 133`, `n_confluence = 17` against a declared minimum of 50 confluence events), and the primary Part B arm (`w_abc_conf` pooling 15m and 1h reads on 3m gainers) does not improve A1's daily net balance (`-5.95` points).** Under the [protocol](ELLIOTT_ABC_CHART_ENGINE_PROTOCOL_20261115.md) declared at `0e9adb3` before scoring:

- **Bare ABC geometry does not beat distance-matched placebos on 15m or 1h.** Across 133 bullish 1h completed counts, bare geometry hits the wave-B target first 42.1% of the time at 24h (`-0.147 R`) against 39.7% (`-0.133 R`) for distance-matched random placebos.
- **On 1h bullish counts, multi-indicator confluence separates winners from bare geometry, but only 17 events pass the 0.50 threshold.** The 17 confluence events hit target first 58.8% of the time at 24h (`+0.215 R`) against 39.7% (`-0.200 R`) for the 116 events without confluence: a `+19.17` point hit-rate lift (`[+1.91, +39.62]`) and `+0.415 R` return lift (`[+0.149, +0.750]`) at 24h, and `+27.79` points (`[+11.29, +49.05]`) / `+0.368 R` (`[+0.108, +0.728]`) at 12h. In `1h/bullish/zone` (`n = 336`, `conf = 17`), confluence averages `+0.313 R` against `-0.192 R` for random placebos (`+0.509 R` paired difference, `[-0.165, +1.251]`). Because `n_confluence = 17 < 50`, this is descriptive and underpowered under the reading rule.
- **On 4h bearish zone entries (`n = 95`, `conf = 19`), entering inside the projected wave-C zone beats both random and pivot placebos.** All 95 zone entries average `+0.392 R` at 24h (`+0.260 R` over random placebo `[+0.003, +0.545]`; `+0.440 R` over pivot placebo `[+0.157, +0.814]`), and the 19 confluence entries hit target first 42.1% of the time vs 13.8% for random placebo (`+26.32` points `[+7.50, +58.64]`).
- **On 15m bars, indicator confluence anti-selects.** In `15m/bullish/complete` (`n = 478`, `conf = 95`) and `15m/bullish/zone` (`n = 1,344`, `conf = 84`), confluence scores `-0.243 R` and `-0.435 R` at 24h.
- **In Part B, pooling noisy 15m reads with 1h reads hurts 3m gainers on equal-weighted daily means, though pooled runner rates nearly double.** On `confirmation_3m_up/up`, `w_abc_conf` selects 192 of 12,465 A1 flags (`6.2` flags/day). Pooled across all flags, `abc_with_confluence` nearly doubles the runner rate (`9.38%` vs `5.09%` for `no_structure`; `10.55%` vs `4.80%` on `ignition_1m/up`, where daily mean runner rate reaches `14.29%` vs `12.29%` crashers, `dN = +3.89 [-3.25, +11.30]`). However, on 3m gainers the equal-weighted daily net difference is `-5.95 [-17.45, +3.76]`, while bare `w_abc` (`1,172` flags) is `+1.58 [-1.89, +5.03]` (pooled net `-0.82%` vs `-2.45%` for `no_structure`).

## Part A: standalone signals across 100 liquid USD products (Oct 13 – Nov 12, 2026)

4,924 total signals across 100 non-pegged products (`279,723` 15m reads, `71,878` 1h reads, `18,000` 4h reads). All entries occur strictly at the close of `confirmed_at_ts`.

| Cell (`timeframe/bias/signal`) | Signals (All / Conf) | Planned RR (median) | 24h Target First (All / Conf / Placebo) | 24h Mean R (All / Conf / Placebo) | Conf minus Without (24h R, 95% block CI) |
|---|---:|---:|---|---|---|
| `1h/bullish/complete` (primary) | 133 / 17 | 0.88 | 42.1% / 58.8% / 39.7% | -0.147 / +0.215 / -0.133 | +0.415 [+0.149, +0.750] |
| `1h/bullish/zone` | 336 / 17 | 1.14 | 29.5% / 41.2% / 26.1% | +0.042 / +0.313 / -0.192 | +0.285 [-0.332, +0.958] |
| `1h/bearish/complete` | 138 / 66 | 0.88 | 50.0% / 59.1% / 50.8% | +0.221 / +0.280 / +0.154 | +0.113 [-0.387, +0.494] |
| `1h/bearish/zone` | 299 / 64 | 0.99 | 29.1% / 29.7% / 40.6% | -0.057 / -0.021 / +0.251 | +0.046 [-0.264, +0.354] |
| `4h/bearish/complete` | 25 / 12 | 0.44 | 48.0% / 50.0% / 47.8% | +0.098 / +0.091 / +0.087 | -0.014 [-0.478, +0.470] |
| `4h/bearish/zone` | 95 / 19 | 1.00 | 34.7% / 42.1% / 13.8% | +0.392 / +0.400 / +0.133 | +0.010 [-0.513, +0.882] |
| `4h/bullish/complete` | 23 / 5 | 0.52 | 26.1% / 20.0% / 34.1% | -0.166 / -0.605 / -0.066 | -0.561 [-1.050, +0.091] |
| `4h/bullish/zone` | 67 / 2 | 2.03 | 10.4% / 0.0% / 6.8% | +0.081 / +0.079 / -0.141 | -0.002 [-0.575, +0.767] |
| `15m/bearish/complete` | 571 / 347 | 0.78 | 57.6% / 54.2% / 59.8% | +0.022 / -0.026 / +0.081 | -0.122 [-0.250, +0.001] |
| `15m/bearish/zone` | 1,415 / 306 | 1.05 | 49.9% / 48.7% / 49.0% | +0.173 / +0.169 / +0.147 | -0.006 [-0.143, +0.134] |
| `15m/bullish/complete` | 478 / 95 | 0.83 | 51.9% / 41.1% / 49.3% | -0.065 / -0.243 / -0.107 | -0.222 [-0.419, -0.038] |
| `15m/bullish/zone` | 1,344 / 84 | 1.13 | 39.6% / 26.2% / 37.4% | -0.055 / -0.435 / -0.085 | -0.405 [-0.672, -0.119] |

### Diagnosis of Part A mechanics

1. **Confirmation lag compresses planned reward-to-risk on `complete` signals.** Waiting for a full `2.2 x ATR(14)` reversal bar close to confirm wave C consumes a substantial fraction of the move back to the wave-B target, leaving a median planned reward-to-risk of `0.78–0.88` on 15m/1h `complete` signals versus `1.00–2.03` on `zone` entries.
2. **Higher-timeframe trend weighting (`0.30`, subtracted when opposing) restricts bullish 1h confluence during macro pullbacks.** Across the Oct 13 – Nov 12 window, bearish 1h counts reached confluence 66 times (`47.8%` of 138 counts), whereas bullish 1h counts reached confluence only 17 times (`12.8%` of 133 counts).
3. **Timeframe separation.** Confluence adds value on 1h bullish counts (`+0.415 R` over non-confluence) and 4h bearish zone counts, but degrades performance on 15m bars where short-horizon RSI/MACD divergences trigger prematurely inside impulsive intraday trends.

## Part B: Instant Radar A1 flags conditioned on chart structure

Reproduces `confirm_a1_gate_20261115.py` exactly (`51,997` entries, `12,773` A0 / `12,465` A1 flags, `+0.30 / -2.89` points).

### Equal-weighted daily differences vs all A1 flags

| Board | Arm | Arm Flags | Daily Runner Rate (Base / Arm) | Daily Crasher Rate (Base / Arm) | Daily dN (Arm minus A1, 95% block CI) |
|---|---|---:|---|---|---|
| `confirmation_3m_up/up` | `w_abc_conf` (primary) | 192 | 5.38% / 5.97% | 7.64% / 14.17% | -5.95 [-17.45, +3.76] |
| `confirmation_3m_up/up` | `w_abc` | 1,172 | 5.28% / 6.32% | 7.64% / 7.10% | +1.58 [-1.89, +5.03] |
| `confirmation_3m_up/up` | `w_trend` | 1,930 | 5.28% / 7.12% | 7.64% / 8.85% | +0.65 [-1.72, +2.84] |
| `confirmation_3m_up/up` | `w_no_opp` | 11,285 | 5.28% / 5.37% | 7.64% / 7.80% | -0.05 [-0.16, +0.06] |
| `ignition_1m/up` | `w_abc_conf` | 199 | 4.86% / 14.29% | 6.87% / 12.29% | +3.89 [-3.25, +11.30] |
| `ignition_1m/up` | `w_abc` | 1,389 | 4.79% / 4.82% | 6.71% / 7.12% | -0.38 [-2.76, +2.11] |
| `ignition_1m/up` | `w_trend` | 2,214 | 4.79% / 5.67% | 6.71% / 8.37% | -0.77 [-2.69, +0.90] |
| `confirmation_3m_down/down` | `w_abc_conf` | 450 | 5.32% / 2.28% | 6.78% / 4.10% | -0.37 [-3.62, +3.00] |
| `confirmation_3m_down/down` | `w_abc` | 1,243 | 5.35% / 3.95% | 6.76% / 6.65% | -1.29 [-3.96, +1.84] |

### Pooled A1 flag outcomes by structure class

| Board | Structure Class | Flags | Runners | Crashers | Pooled Runner Rate | Pooled Crasher Rate | Pooled Net |
|---|---|---:|---:|---:|---:|---:|---:|
| `confirmation_3m_up/up` | `abc_with_confluence` | 192 | 18 | 21 | 9.38% | 10.94% | -1.56% |
| `confirmation_3m_up/up` | `abc_geometry_only` | 980 | 52 | 60 | 5.31% | 6.12% | -0.82% |
| `confirmation_3m_up/up` | `trend_impulse` | 758 | 66 | 84 | 8.71% | 11.08% | -2.37% |
| `confirmation_3m_up/up` | `no_structure` | 9,418 | 479 | 710 | 5.09% | 7.54% | -2.45% |
| `confirmation_3m_up/up` | `opposing_abc` | 1,117 | 46 | 67 | 4.12% | 6.00% | -1.88% |
| `ignition_1m/up` | `abc_with_confluence` | 199 | 21 | 24 | 10.55% | 12.06% | -1.51% |
| `ignition_1m/up` | `trend_impulse` | 825 | 59 | 83 | 7.15% | 10.06% | -2.91% |
| `ignition_1m/up` | `no_structure` | 10,730 | 515 | 719 | 4.80% | 6.70% | -1.90% |
| `ignition_1m/up` | `opposing_abc` | 1,359 | 54 | 79 | 3.97% | 5.81% | -1.84% |

## Implications for next iteration

1. **Drop 15m wave reads from Radar conditioning and chart overlays.** 15m ABC confluence signals underperform bare geometry in Part A and dilute 1h/4h structure in Part B.
2. **Trigger inside the projected Wave C Fibonacci zone on micro-reclaim rather than waiting for full `2.2 x ATR` ZigZag reversal.** Waiting for `complete` cuts planned RR below `0.90` and misses early RSI/Bollinger confluence.
3. **Separate higher-timeframe trend alignment from local turning-point confluence.** Treating opposing 4h EMA slope as a `-0.30` penalty suppresses valid 1h Wave C reversal setups at major swing lows (`n = 17`).

## Provenance

Protocol and driver committed at `0e9adb3` before scoring. Full numerical outputs and hashes are in [RESULTS.json](results/elliott_abc_20261115/RESULTS.json).
