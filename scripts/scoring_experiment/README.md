# Offline price/volume scoring baseline (research only)

Isolated from production: nothing here imports the application, opens a runtime store, or
uses the network. It reads Codex's verified daily panel (`scripts/scoring_data/` is reused
read-only and unchanged) and, for one exploratory check, two local read-only databases.
Requires Python 3.12 with numpy and pandas only (no scipy or scikit-learn).

Frozen design: [`docs/research/SCORING_BASELINE_PROTOCOL.md`](../../docs/research/SCORING_BASELINE_PROTOCOL.md)
(with dated amendments). Results and interpretation:
[`docs/research/SCORING_BASELINE_RESULTS.md`](../../docs/research/SCORING_BASELINE_RESULTS.md).

```powershell
python -m unittest discover -s tests -p test_scoring_experiment.py -v   # synthetic look-ahead, purge, label, control tests
python scripts/scoring_experiment/run.py build        # verifies the panel hashes, builds features and labels (~10 s)
python scripts/scoring_experiment/run.py discovery    # walk-forward 2023-01-01 .. 2024-12-23 (~15 min)
python scripts/scoring_experiment/run.py test         # refuses unless a matching discovery result exists (~30 min)
python scripts/scoring_experiment/recorded_signals.py # exploratory short-horizon check on recorded signals (~25 s)
python scripts/scoring_experiment/make_report.py > tables.md   # appended to docs/research/SCORING_BASELINE_RESULTS.md
```

`--min-history 60 --tag hist60` runs the whole pipeline with the shorter history rule
(sensitivity). Work files go to `~/.moonwalking/analysis/scoring_baseline/` (a local cache; the
pickle there is only ever written and read by `build` on this machine). Small JSON results,
and the latest-date score table are committed under
`docs/research/results/scoring_baseline/`.

| File | Role |
|---|---|
| `config.json` | every constant; its hash is stored with each result |
| `panel.py` | loads and hash-verifies the panel; past-only features; next-day-open labels; eligibility |
| `model.py` | purged monthly walk-forward ridge; exact feature contributions; 0-100 percentile score |
| `evaluate.py` | week-block bootstrap, IC, score buckets, staggered weekly sleeves, event rules and controls |
| `run.py` | build / discovery / test driver and sample score table |
| `recorded_signals.py` | exploratory check of the live `CONTINUATION FAVORED` and `REVERSAL RISK RISING` reads |
| `make_report.py` | renders the tables |

## What each output means

* **Score (1-100, per horizon):** the same-day percentile rank of the model prediction among
  eligible coins. Ordinal. Not a probability and not "bullish": above 50 means a higher
  predicted BTC-residual, volatility-scaled return than the median coin that day.
* **Factor contributions:** `rank-normal feature x ridge coefficient`; they sum exactly to
  the prediction before it is ranked.
* **Evidence coverage (0-100):** data sufficiency (share of the 90-day window with candles
  and share of the 11 inputs present). It says nothing about predictive confidence.
* **Risk rank:** same-day percentile of trailing 30-day volatility, with flags.
* **Verdicts** follow the protocol: *supportive*, *ruled out*, or *inconclusive*.

## Limits

Daily candles only (no intraday history is invented from them); a 2026 product-list
snapshot that includes inactive products but is not proven complete; backfilled data is not
a point-in-time availability record; costs are scenarios; the live BHABIT score cannot be
reconstructed from daily candles and is compared only where it was actually recorded.

## Funding comparison (separate protocol)

```powershell
python scripts/scoring_experiment/funding_fetch.py --map docs/research/results/funding_identity_audit_20261025/APPROVED_FUNDING_MAP.json --out <new folder>   # public keyless API, 1 request per 1.1 s, about 2 hours
python scripts/scoring_experiment/funding_fetch.py --summarize --out <folder>                                                                          # coverage and hashes, no network
python scripts/scoring_experiment/funding_run.py discovery
python scripts/scoring_experiment/funding_run.py test                                                                                                   # refuses without a matching discovery result
python scripts/scoring_experiment/make_funding_report.py > tables_funding.md
```

Design: `docs/research/FUNDING_COMPARISON_PROTOCOL.md`; results: `docs/research/FUNDING_COMPARISON_RESULTS.md`. Raw funding responses stay outside Git.
