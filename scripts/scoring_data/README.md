# Offline daily-input checkpoint

`freeze_daily_panel.py` preserves the existing `fetch_daily_all.py` output and
checks it before a scoring experiment. It uses the Python standard library only.
It does not fetch prices, import the application, or open any runtime store.

```powershell
python scripts/scoring_data/freeze_daily_panel.py freeze --source <daily_all> --destination <new-checkpoint-directory> --archive <candle_archive.sqlite> --candidate-map <hl_first_funding.json>
python scripts/scoring_data/freeze_daily_panel.py verify --destination <checkpoint-directory>
python -m unittest discover -s tests -p test_scoring_data_checkpoint.py -v
```

The destination must not exist. Repeating a freeze never replaces a checkpoint;
use `verify` instead. A failed freeze may leave a partial directory for inspection.
Exit status 0 means integrity verification and the 99% cross-check gate passed;
2 means the copied inputs verify but the cross-check needs review; 1 means failure.

## Layout and interpretation

- `raw/`: byte-for-byte copies of all source JSON, including `products.json` and
  the source's lowercase `manifest.json`.
- `metadata/funding_candidates.json`: a hashed copy of the original funding
  availability map. These are provisional ticker matches, not verified identities.
- `MANIFEST.json`: SHA-256 hashes, sizes and per-product candle metadata.
- `QUALITY_REPORT.json`: gaps, invalid/conflicting rows, funding-candidate coverage,
  and a comparison against the hourly archive.

The separate `raw/` directory is necessary on Windows: `manifest.json` and
`MANIFEST.json` cannot coexist in the same directory.

Research must respect the source manifest's UTC floor/end, use only completed
days, and deduplicate identical window-boundary candles. The inspector excludes
conflicting duplicate days instead of silently choosing a version. It neither
fills missing days nor decides that missing candles mean no trades.

Daily close comparisons include only UTC days with all 24 aligned hourly candles.
The allowed relative close difference is 0.001 (0.1%). Partial hourly days are
reported separately; they cannot establish a daily-close mismatch. The native
daily response is Coinbase's `[time, low, high, open, close, volume]` format.

All raw research data stays outside Git. This checkpoint proves preservation
and reports numerical agreement. It does not establish complete historical
listing coverage, provider identity, point-in-time availability, or prediction
quality. RNDR and RENDER remain separate products.
